"""
app/agents/action.py — Multi-Step Remediation Agent

Generates a prioritised list of kubectl commands: diagnostic first,
then remediation, then verification.  All commands are restricted to
the RBAC-allowed verbs defined in k8s/rbac.yaml:

  ALLOWED: get, describe, logs, set, rollout, scale, annotate, label,
           top, cordon, uncordon, port-forward
  BLOCKED: delete, create, exec, apply, patch, edit

The agent collects live cluster context so the LLM can produce
contextually accurate commands with real resource names instead of
generic placeholders like ``<pod-name>``.
"""

import logging
from typing import Optional

from app.tools.llm import query_llm
from app.tools.cluster_context import gather_cluster_context

logger = logging.getLogger(__name__)


def suggest_fix(
    issue: str,
    namespace: Optional[str] = None,
    pod: Optional[str] = None,
) -> str:
    """Generate a multi-step remediation plan for a Kubernetes issue.

    Args:
        issue:     Raw issue description from k8sgpt or kubectl fallback.
        namespace: Target namespace (defaults to ``k8s-ai``).
        pod:       Specific pod name when available (from webhook alert).

    Returns:
        A multi-line string of kubectl commands categorised as diagnostic,
        remediation, and verification steps.  The analyzer pipeline
        validates each command through the guardrail individually.
    """
    ns = namespace or "k8s-ai"

    # ── Collect live cluster context so the LLM uses real names ──────────
    try:
        cluster_ctx = gather_cluster_context(namespace=ns, pod=pod)
    except Exception as exc:
        logger.warning("action: failed to gather cluster context: %s", exc)
        cluster_ctx = "(Cluster context unavailable.)"

    # ── Fast-path: ImagePullBackOff has a well-known remediation ─────────
    if "ImagePullBackOff" in issue or "ErrImagePull" in issue:
        prompt = f"""The following Kubernetes issue involves an image pull failure:

{issue}

Live cluster state:
{cluster_ctx}

IMPORTANT — kubectl verb restrictions (RBAC policy):
  ALLOWED: get, describe, logs, set, rollout, scale, annotate, label,
           top, cordon, uncordon, port-forward
  BLOCKED: delete, create, exec, apply, patch, edit

Return a remediation plan in this EXACT format (one command per line):

DIAGNOSTIC:
kubectl describe pod <actual-pod-name> -n {ns}
kubectl get events -n {ns} --field-selector involvedObject.name=<actual-pod-name>

REMEDIATION:
kubectl set image deployment/<actual-deployment> <container>=<correct-image>:<tag> -n {ns}

VERIFICATION:
kubectl get pods -n {ns} -o wide
kubectl rollout status deployment/<actual-deployment> -n {ns}

Use the ACTUAL resource names from the cluster state above. Do not use placeholders.
"""

    # ── General remediation for all other failure types ──────────────────
    else:
        prompt = f"""A Kubernetes issue requires remediation:

{issue}

Live cluster state:
{cluster_ctx}

IMPORTANT — kubectl verb restrictions (RBAC policy):
  ALLOWED: get, describe, logs, set, rollout, scale, annotate, label,
           top, cordon, uncordon, port-forward
  BLOCKED: delete, create, exec, apply, patch, edit

Return a remediation plan in this EXACT format (one command per line).
Use the ACTUAL resource names from the cluster state above.

DIAGNOSTIC:
<1-3 kubectl commands to confirm the root cause>

REMEDIATION:
<1-3 kubectl commands to fix the issue, using only ALLOWED verbs>
(For example: kubectl set image, kubectl rollout restart, kubectl scale,
 kubectl annotate, kubectl label, kubectl cordon/uncordon)

VERIFICATION:
<1-2 kubectl commands to confirm the fix worked>

Rules:
- Use real pod/deployment/service names from the cluster state, not placeholders.
- Prefer diagnostic commands first.
- Only suggest mutating commands if the diagnosis is clear.
- Each command must start with 'kubectl' and use only ALLOWED verbs.
- If CrashLoopBackOff: suggest kubectl logs, kubectl describe, then kubectl rollout restart.
- If OOMKilled: suggest kubectl describe (check limits), kubectl top pods.
- If Pending: suggest kubectl describe pod (check events), kubectl get nodes.
- If node pressure: suggest kubectl top nodes, kubectl cordon.
"""

    return query_llm(prompt)
