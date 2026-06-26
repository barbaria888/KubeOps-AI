"""
app/agents/reasoning.py — SRE Diagnostic Reasoning Agent

Builds a production-grade diagnostic prompt using:
  1. The raw issue description (from k8sgpt or kubectl fallback).
  2. Live cluster context collected via RBAC-compliant kubectl commands.
  3. Formatted historical incidents from ChromaDB vector store.

The LLM is instructed to produce a structured root-cause analysis with
an investigation workflow of 5-8 kubectl commands — going far beyond
a shallow ``kubectl get pods -A``.

All suggested commands are restricted to the RBAC-allowed verb set:
  get, describe, logs, set, rollout, scale, annotate, label, top,
  cordon, uncordon, port-forward.
"""

import logging
from typing import Optional

from app.tools.llm import query_llm
from app.tools.vector_store import search_similar, format_similar_incidents
from app.tools.cluster_context import gather_cluster_context

logger = logging.getLogger(__name__)


def explain_issue(
    issue: str,
    namespace: Optional[str] = None,
    pod: Optional[str] = None,
) -> str:
    """Analyze a Kubernetes issue using live cluster state and historical context.

    Args:
        issue:     Raw issue description from k8sgpt or kubectl fallback.
        namespace: Target namespace (defaults to ``k8s-ai``).
        pod:       Specific pod name when available (from webhook alert).

    Returns:
        A structured diagnostic analysis from the LLM including root cause,
        evidence, investigation commands, remediation, and rollback plan.
    """
    # ── 1. Collect live cluster context (RBAC-safe get/describe/logs) ────
    ns = namespace or "k8s-ai"
    try:
        cluster_ctx = gather_cluster_context(namespace=ns, pod=pod)
    except Exception as exc:
        logger.warning("Failed to gather cluster context: %s", exc)
        cluster_ctx = "(Cluster context unavailable.)"

    # ── 2. Retrieve and format historical incidents from ChromaDB ────────
    try:
        raw_past = search_similar(issue)
        past_incidents = format_similar_incidents(raw_past)
    except Exception as exc:
        logger.warning("Failed to search vector store: %s", exc)
        past_incidents = "(No historical incident data available.)"

    # ── 3. Build the production SRE diagnostic prompt ────────────────────
    prompt = f"""You are a senior Kubernetes SRE performing root-cause analysis.

═══════════════════════════════════════════════════════
CURRENT ISSUE
═══════════════════════════════════════════════════════
{issue}

═══════════════════════════════════════════════════════
LIVE CLUSTER STATE (namespace: {ns})
═══════════════════════════════════════════════════════
{cluster_ctx}

═══════════════════════════════════════════════════════
SIMILAR PAST INCIDENTS (from incident memory)
═══════════════════════════════════════════════════════
{past_incidents}

═══════════════════════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════════════════════

Analyze the issue using the live cluster state and past incidents above.

IMPORTANT — kubectl verb restrictions (RBAC policy):
  ALLOWED: get, describe, logs, set, rollout, scale, annotate, label,
           top, cordon, uncordon, port-forward
  BLOCKED: delete, create, exec, apply, patch, edit

Focus on real Kubernetes operational issues:
  - Pod failures (CrashLoopBackOff, ImagePullBackOff, ErrImagePull,
    OOMKilled, CreateContainerError, RunContainerError)
  - Scheduling failures (Pending pods, taints, node affinity, resource pressure)
  - Deployment issues (rollout stuck, replica mismatch, surge failures)
  - Networking (service endpoint mismatches, DNS, ingress misconfig)
  - Storage (PVC pending, mount failures, volume access modes)
  - Resource exhaustion (CPU/memory limits, node pressure, evictions)

Ignore informational findings like unused ConfigMaps or Secrets.

If past incidents match the current pattern, reference them explicitly
and explain whether the same fix applies.

Respond in this EXACT format:

Root Cause:
<one clear sentence identifying the most likely root cause>

Evidence:
<2-3 bullet points citing specific data from the live cluster state>

Investigation Commands:
1. <kubectl command> — <what it reveals>
2. <kubectl command> — <what it reveals>
3. <kubectl command> — <what it reveals>
4. <kubectl command> — <what it reveals>
5. <kubectl command> — <what it reveals>

(Provide 5-8 commands. Start with diagnostic commands like describe,
logs, get events. Only include mutating commands like set image or
rollout restart if the diagnosis is clear.)

Recommended Fix:
<specific remediation steps using only ALLOWED kubectl verbs>

Rollback Plan:
<what to do if the fix makes things worse>
"""

    return query_llm(prompt)
