"""
app/tools/cluster_context.py — Live Cluster Context Collector

Runs a battery of diagnostic kubectl commands against the affected
namespace and pod, returning structured context for the LLM.  Every
command here maps to an RBAC-permitted verb+resource in k8s/rbac.yaml:

  get/list  → pods, pods/status, services, endpoints, nodes, nodes/status,
              events, configmaps, persistentvolumeclaims, deployments,
              replicasets, statefulsets, daemonsets, ingresses,
              networkpolicies, horizontalpodautoscalers, jobs, cronjobs,
              storageclasses
  get/list  → metrics.k8s.io/pods, metrics.k8s.io/nodes (kubectl top)
  get       → pods/log  (kubectl logs)

No create, delete, exec, apply, or patch commands are issued.
"""

import logging
from typing import Optional

from app.tools.kubectl import run_kubectl

logger = logging.getLogger(__name__)

# Maximum lines to keep per command output to stay within token budgets.
_MAX_LINES = 80


def _truncate(text: str, max_lines: int = _MAX_LINES) -> str:
    """Keep the last *max_lines* lines so the most recent state is visible."""
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    return (
        f"[... truncated {len(lines) - max_lines} older lines ...]\n"
        + "\n".join(lines[-max_lines:])
    )


def _run_safe(command: str, label: str) -> Optional[str]:
    """Run a kubectl command, returning its output or None on failure."""
    try:
        ok, output = run_kubectl(command)
        if ok and output and output != "Command executed successfully.":
            return _truncate(output)
    except Exception as exc:
        logger.debug("cluster_context: %s failed: %s", label, exc)
    return None


def gather_cluster_context(
    namespace: str = "k8s-ai",
    pod: Optional[str] = None,
) -> str:
    """Collect live cluster diagnostics for the LLM.

    Args:
        namespace: Target namespace (defaults to ``k8s-ai``).
        pod:       Specific pod name when available (from webhook alert).

    Returns:
        A formatted multi-section string with real cluster state.
        Sections whose commands failed (RBAC denial, timeout, etc.)
        are silently omitted so the output is always clean.
    """
    ns = namespace or "k8s-ai"
    sections: list[str] = []

    # ── 1. Pod overview (get, list → pods — RBAC: core/pods/get,list) ────
    out = _run_safe(
        f"kubectl get pods -n {ns} -o wide",
        "pod-overview",
    )
    if out:
        sections.append(f"=== Pods in namespace '{ns}' ===\n{out}")

    # ── 2. Events (get, list → events — RBAC: core/events/get,list) ──────
    out = _run_safe(
        f"kubectl get events -n {ns} --sort-by=.lastTimestamp",
        "events",
    )
    if out:
        sections.append(f"=== Recent Events in '{ns}' ===\n{out}")

    # ── 3. Deployments (get, list → apps/deployments — RBAC allowed) ─────
    out = _run_safe(
        f"kubectl get deployments -n {ns} -o wide",
        "deployments",
    )
    if out:
        sections.append(f"=== Deployments in '{ns}' ===\n{out}")

    # ── 4. Services (get, list → core/services — RBAC allowed) ───────────
    out = _run_safe(
        f"kubectl get svc -n {ns} -o wide",
        "services",
    )
    if out:
        sections.append(f"=== Services in '{ns}' ===\n{out}")

    # ── 5. PVCs (get, list → core/persistentvolumeclaims — RBAC allowed) ─
    out = _run_safe(
        f"kubectl get pvc -n {ns}",
        "pvcs",
    )
    if out:
        sections.append(f"=== PersistentVolumeClaims in '{ns}' ===\n{out}")

    # ── 6. Resource usage (get, list → metrics.k8s.io/pods — RBAC allowed)
    out = _run_safe(
        f"kubectl top pods -n {ns}",
        "top-pods",
    )
    if out:
        sections.append(f"=== Resource Usage (pods) in '{ns}' ===\n{out}")

    # ── 7. Node health (get, list → core/nodes — RBAC allowed) ───────────
    out = _run_safe(
        "kubectl get nodes -o wide",
        "nodes",
    )
    if out:
        sections.append(f"=== Cluster Nodes ===\n{out}")

    # ── 8. Node resource usage (get, list → metrics.k8s.io/nodes) ────────
    out = _run_safe(
        "kubectl top nodes",
        "top-nodes",
    )
    if out:
        sections.append(f"=== Node Resource Usage ===\n{out}")

    # ── Pod-specific deep-dive (only when pod name is known) ─────────────
    if pod and pod != "unknown":
        # 9. Describe pod (get → pods — RBAC allowed)
        out = _run_safe(
            f"kubectl describe pod {pod} -n {ns}",
            "describe-pod",
        )
        if out:
            sections.append(f"=== Describe Pod '{pod}' ===\n{out}")

        # 10. Pod logs (get → pods/log — RBAC allowed)
        out = _run_safe(
            f"kubectl logs {pod} -n {ns} --tail=50",
            "pod-logs",
        )
        if out:
            sections.append(f"=== Logs for Pod '{pod}' (last 50 lines) ===\n{out}")

        # 11. Previous container logs for CrashLoopBackOff
        out = _run_safe(
            f"kubectl logs {pod} -n {ns} --previous --tail=30",
            "pod-logs-previous",
        )
        if out:
            sections.append(
                f"=== Previous Container Logs for Pod '{pod}' (last 30 lines) ===\n{out}"
            )

    if not sections:
        return "(No cluster context could be collected — kubectl may not be available.)"

    return "\n\n".join(sections)
