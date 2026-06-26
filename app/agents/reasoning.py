"""
app/agents/reasoning.py — SRE Diagnostic Reasoning Agent

Builds a production-grade diagnostic prompt using:
  1. The structured diagnostic report (from RunWhen codebundle or kubectl fallback).
  2. Live cluster context collected via RBAC-compliant kubectl commands.
  3. Formatted historical incidents from ChromaDB vector store.

The LLM is instructed to produce a structured root-cause summary and exactly ONE 
safe remediation command.

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
    diagnostic_report: str,
    namespace: Optional[str] = None,
    pod: Optional[str] = None,
) -> str:
    """Analyze a Kubernetes issue using a verified diagnostic report, live cluster state and historical context.

    Args:
        diagnostic_report: Structured markdown report from RunWhen script or kubectl fallback.
        namespace: Target namespace (defaults to ``k8s-ai``).
        pod:       Specific pod name when available (from webhook alert).

    Returns:
        A structured diagnostic analysis from the LLM including root cause,
        evidence, and ONE safe remediation command.
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
        raw_past = search_similar(diagnostic_report)
        past_incidents = format_similar_incidents(raw_past)
    except Exception as exc:
        logger.warning("Failed to search vector store: %s", exc)
        past_incidents = "(No historical incident data available.)"

    # ── 3. Build the production SRE diagnostic prompt ────────────────────
    prompt = f"""You are a senior Kubernetes SRE performing root-cause analysis.

═══════════════════════════════════════════════════════
DIAGNOSTIC REPORT
═══════════════════════════════════════════════════════
{diagnostic_report}

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

Analyze the diagnostic report using the live cluster state and past incidents above.

IMPORTANT — kubectl verb restrictions (RBAC policy):
  ALLOWED: get, describe, logs, set, rollout, scale, annotate, label,
           top, cordon, uncordon, port-forward
  BLOCKED: delete, create, exec, apply, patch, edit

If past incidents match the current pattern, reference them explicitly
and explain whether the same fix applies.

Respond in this EXACT format:

Root Cause:
<one clear sentence identifying the most likely root cause>

Evidence:
<1-2 bullet points citing specific data from the diagnostic report or live state>

Recommended Fix:
<exactly ONE safe kubectl command using only ALLOWED verbs>
"""

    return query_llm(prompt)
