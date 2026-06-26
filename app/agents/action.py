"""
app/agents/action.py — Single-Step Remediation Agent

Generates exactly one kubectl remediation command based on a structured
diagnostic report. All commands are restricted to the RBAC-allowed verbs 
defined in k8s/rbac.yaml:

  ALLOWED: get, describe, logs, set, rollout, scale, annotate, label,
           top, cordon, uncordon, port-forward
  BLOCKED: delete, create, exec, apply, patch, edit

The agent uses live cluster context to ensure the command uses real 
resource names instead of generic placeholders.
"""

import logging
from typing import Optional

from app.tools.llm import query_llm
from app.tools.cluster_context import gather_cluster_context

logger = logging.getLogger(__name__)


def suggest_fix(
    diagnostic_report: str,
    namespace: Optional[str] = None,
    pod: Optional[str] = None,
) -> str:
    """Generate a single remediation command for a Kubernetes issue.

    Args:
        diagnostic_report: Structured markdown report from RunWhen script or kubectl fallback.
        namespace: Target namespace (defaults to ``k8s-ai``).
        pod:       Specific pod name when available (from webhook alert).

    Returns:
        A single string containing exactly ONE kubectl command.
        The analyzer pipeline validates this command through the guardrail.
    """
    ns = namespace or "k8s-ai"

    # ── Collect live cluster context so the LLM uses real names ──────────
    try:
        cluster_ctx = gather_cluster_context(namespace=ns, pod=pod)
    except Exception as exc:
        logger.warning("action: failed to gather cluster context: %s", exc)
        cluster_ctx = "(Cluster context unavailable.)"

    prompt = f"""A Kubernetes issue requires remediation:

{diagnostic_report}

Live cluster state:
{cluster_ctx}

IMPORTANT — kubectl verb restrictions (RBAC policy):
  ALLOWED: get, describe, logs, set, rollout, scale, annotate, label,
           top, cordon, uncordon, port-forward
  BLOCKED: delete, create, exec, apply, patch, edit

Given this diagnostic report and live state, output exactly ONE safe kubectl 
remediation command.

Rules:
- Output ONLY the command, nothing else.
- Use real pod/deployment/service names from the cluster state, not placeholders.
- The command must start with 'kubectl' and use only ALLOWED verbs.
"""

    return query_llm(prompt)
