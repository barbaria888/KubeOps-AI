import os

from app.tools.k8sgpt import run_k8sgpt
from app.agents.reasoning import explain_issue
from app.agents.action import suggest_fix
from app.agents.guardrail import validate_action


def _safe_text(value):
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _fallback_explanation(description: str) -> str:
    return f"Cluster analysis reported: {description or 'No details were returned.'}"


def _fallback_action(description: str) -> str:
    if "ImagePullBackOff" in description or "ErrImagePull" in description:
        return "kubectl describe pod <pod-name>"
    if "CrashLoopBackOff" in description:
        return "kubectl logs <pod-name> --previous"
    return "kubectl get pods -A"


def _looks_like_ai_error(value: str) -> bool:
    lowered = (value or "").strip().lower()
    return lowered.startswith(("error:", "ai error:", "404 client error", "500 server error"))


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


def analyze_cluster(namespace: str = None):
    """Run the full agentic analysis pipeline.

    Args:
        namespace: When provided the analysis is scoped to this single
                   Kubernetes namespace (populated by the Prometheus webhook route).
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

    issues = run_k8sgpt(namespace=namespace)

    if not isinstance(issues, dict):
        issues = {"results": []}

    results_list = issues.get("results")
    if results_list is None:
        results_list = []

    for issue in results_list[:max_issues]:
        if not isinstance(issue, dict):
            issue = {"description": issue}

        description = _safe_text(issue.get("description", ""))

        explanation = _fallback_explanation(description)
        action = _fallback_action(description)

        if _is_full_ai_enabled():
            try:
                ai_explanation = _safe_text(explain_issue(description))
                if ai_explanation and not _looks_like_ai_error(ai_explanation):
                    explanation = ai_explanation
            except Exception:
                pass

            try:
                ai_action = _safe_text(suggest_fix(description))
                if ai_action and not _looks_like_ai_error(ai_action):
                    action = ai_action
            except Exception:
                pass

        safe = validate_action(action)
        if not safe:
            action = _fallback_action(description)
            safe = validate_action(action)

        results.append({
            "issue": description,
            "explanation": explanation,
            "suggested_action": action,
            "safe": safe
        })

    return results
