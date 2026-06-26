import logging
import os

from app.tools.runwhen import RunWhenRunner
from app.tools.kubectl import run_kubectl
from app.agents.reasoning import explain_issue
from app.agents.action import suggest_fix
from app.agents.guardrail import validate_action, validate_action_list

logger = logging.getLogger(__name__)


def _safe_text(value):
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _fallback_explanation(description: str) -> str:
    return f"Cluster analysis reported: {description or 'No details were returned.'}"


def _fallback_action(description: str, namespace: str = "k8s-ai") -> str:
    """Return a sensible default kubectl command when AI is unavailable."""
    ns = namespace or "k8s-ai"
    if "ImagePullBackOff" in description or "ErrImagePull" in description:
        return f"kubectl describe pods -n {ns}"
    if "CrashLoopBackOff" in description:
        return f"kubectl logs --previous -l app -n {ns} --tail=50"
    if "OOMKilled" in description:
        return f"kubectl top pods -n {ns}"
    if "Pending" in description:
        return f"kubectl describe pods -n {ns}"
    if "NodeNotReady" in description or "node" in description.lower():
        return "kubectl get nodes -o wide"
    return f"kubectl get pods -n {ns} -o wide"


def _is_gibberish(text: str) -> bool:
    """Return True if the text looks like corrupted / non-English LLM output.

    Detects Mandarin, random Unicode, and other garbage that the model
    sometimes emits when it fails silently.  Threshold: if more than 30%
    of the characters are outside the printable ASCII range the response
    is treated as unusable.
    """
    if not text:
        return False
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    return (non_ascii / len(text)) > 0.30


def _looks_like_ai_error(value: str) -> bool:
    lowered = (value or "").strip().lower()
    if lowered.startswith(("error:", "ai error:", "404 client error", "500 server error")):
        return True
    # Catch gibberish / Mandarin output from corrupted LLM responses
    return _is_gibberish(value)


def _is_full_ai_enabled() -> bool:
    """Return True when the full LLM reasoning pipeline should run.

    Supports both the new canonical env var (KUBEOPS_ENABLE_FULL_AI) and the
    legacy name (KUBEOPS_ENABLE_FULL_OLLAMA) so existing deployments continue
    to work without any manifest changes.
    """
    # New canonical name takes precedence
    new_var = os.getenv("KUBEOPS_ENABLE_FULL_AI", "").lower()
    if new_var:
        return new_var == "true"
    # Legacy backward-compatible alias
    legacy_var = os.getenv("KUBEOPS_ENABLE_FULL_OLLAMA", "false").lower()
    return legacy_var == "true"


# ─── kubectl Fallback ────────────────────────────────────────────────────────

def _kubectl_fallback(namespace: str = None, pod: str = None) -> list:
    """Probe the cluster via kubectl when k8sgpt returned zero issues.

    k8sgpt only detects infrastructure-level faults visible through the
    Kubernetes API (e.g. ImagePullBackOff, CrashLoopBackOff).  If a pod is
    technically ``Running`` but throwing application-level errors, k8sgpt
    reports nothing.  This fallback pulls recent events and container state
    so the pipeline still has something to analyse.
    """
    fallback_issues = []
    ns = namespace or "default"

    # 1. Pull recent warning events from the namespace
    event_cmd = f"kubectl get events -n {ns} --field-selector type=Warning --sort-by=.lastTimestamp"
    ok, event_output = run_kubectl(event_cmd)
    if ok and event_output and event_output != "Command executed successfully.":
        fallback_issues.append({
            "description": f"[kubectl fallback] Recent warning events in namespace '{ns}':\n{event_output}",
        })

    # 2. If the webhook passed a specific pod name, inspect its container state
    if pod and pod != "unknown":
        state_cmd = (
            f"kubectl get pod {pod} -n {ns}"
            f" -o jsonpath='{{.status.containerStatuses[*].state}}'"
        )
        ok, state_output = run_kubectl(state_cmd)
        if ok and state_output and state_output != "Command executed successfully.":
            fallback_issues.append({
                "description": (
                    f"[kubectl fallback] Container state for pod '{pod}' "
                    f"in namespace '{ns}':\n{state_output}"
                ),
            })

        # 3. Grab the last 30 log lines — may reveal app-level stack traces
        log_cmd = f"kubectl logs {pod} -n {ns} --tail=30"
        ok, log_output = run_kubectl(log_cmd)
        if ok and log_output and log_output != "Command executed successfully.":
            # Only include if the logs contain something that looks like an error
            lowered = log_output.lower()
            if any(kw in lowered for kw in ("error", "exception", "fatal", "panic", "traceback")):
                fallback_issues.append({
                    "description": (
                        f"[kubectl fallback] Recent error logs for pod '{pod}' "
                        f"in namespace '{ns}':\n{log_output}"
                    ),
                })

    if not fallback_issues:
        logger.info("kubectl fallback found no actionable issues in namespace '%s'.", ns)

    return fallback_issues


# ─── Main Analysis Pipeline ──────────────────────────────────────────────────

def analyze_cluster(alertname: str = None, namespace: str = None, pod: str = None):
    """Run the full agentic analysis pipeline.

    Args:
        alertname: The Prometheus alert name to trigger the appropriate RunWhen script.
        namespace: When provided the analysis is scoped to this single
                   Kubernetes namespace (populated by the Prometheus webhook route).
        pod:       Optional pod name from the webhook alert, used by the
                   kubectl fallback to inspect container state and logs.
    """
    results = []
    max_issues = int(os.getenv("KUBEOPS_MAX_ANALYZED_ISSUES", "2"))
    lazy_mode = os.getenv("KUBEOPS_LAZY_ANALYSIS", "true").lower() == "true"

    if lazy_mode:
        return [{
            "issue": "Cluster analysis is warming up",
            "explanation": (
                "Lazy analysis is enabled, so the backend returns immediately "
                "while the LLM and K8sGPT are still starting."
            ),
            "suggested_action": "kubectl get pods -A",
            "safe": True,
        }]

    context = {"namespace": namespace, "pod": pod}
    runwhen_output = None
    if alertname:
        runwhen_output = RunWhenRunner.execute_diagnostic(alertname, context)

    results_list = []
    if runwhen_output:
        results_list.append({"description": runwhen_output})

    # ── kubectl fallback when RunWhen has no mapping ───────────────────────
    if not results_list:
        logger.info(
            "RunWhen script not found or returned no output. "
            "Falling back to targeted kubectl health checks..."
        )
        results_list = _kubectl_fallback(namespace=namespace, pod=pod)

    ns = namespace or "k8s-ai"

    for issue in results_list[:max_issues]:
        if not isinstance(issue, dict):
            issue = {"description": issue}

        description = _safe_text(issue.get("description", ""))

        explanation = _fallback_explanation(description)
        action = _fallback_action(description, namespace=ns)
        safe_actions_list = []

        if _is_full_ai_enabled():
            # ── AI Explanation (with live cluster context) ────────────
            try:
                ai_explanation = _safe_text(
                    explain_issue(description, namespace=ns, pod=pod)
                )
                if ai_explanation and not _looks_like_ai_error(ai_explanation):
                    explanation = ai_explanation
            except Exception:
                logger.debug("AI explanation failed, using fallback.", exc_info=True)

            # ── AI Remediation (multi-step plan) ─────────────────────
            try:
                ai_action_raw = _safe_text(
                    suggest_fix(description, namespace=ns, pod=pod)
                )
                if ai_action_raw and not _looks_like_ai_error(ai_action_raw):
                    # Try multi-command validation first
                    all_safe, validated_cmds = validate_action_list(ai_action_raw)
                    if validated_cmds:
                        # Use the first safe command as the primary action
                        # (backward compat with frontend)
                        action = validated_cmds[0]
                        safe_actions_list = validated_cmds
                    elif validate_action(ai_action_raw):
                        # Fallback: maybe the LLM returned a single command
                        action = ai_action_raw
            except Exception:
                logger.debug("AI action failed, using fallback.", exc_info=True)

        # ── Final guardrail check ────────────────────────────────────
        safe = validate_action(action)
        if not safe:
            action = _fallback_action(description, namespace=ns)
            safe = validate_action(action)
            safe_actions_list = []

        result_entry = {
            "issue": description,
            "explanation": explanation,
            "suggested_action": action,
            "safe": safe,
        }

        # Include multi-step plan when available (new field, backward compat)
        if safe_actions_list:
            result_entry["suggested_actions"] = safe_actions_list

        results.append(result_entry)

    return results
