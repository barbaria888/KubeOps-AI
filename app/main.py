import logging

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from app.agents.analyzer import analyze_cluster
from app.tools.kubectl import run_kubectl
from app.agents.guardrail import validate_action
from app.tools.vector_store import store_issue

app = FastAPI(title="KubeOps-AI Backend")
logger = logging.getLogger(__name__)


# ─── Request / payload models ──────────────────────────────────────────────────

class CommandRequest(BaseModel):
    command: str
    issue: str = ""


class AlertPayload(BaseModel):
    """Payload forwarded by the Antigravity Listener from Alertmanager.

    Fields:
        status:    Prometheus alert status – 'firing' or 'resolved'.
        alertname: Human-readable alert name (e.g. 'PodCrashLooping').
        namespace: Kubernetes namespace that contains the affected resource.
        pod:       Name of the affected pod / resource.
        original_labels: Full label set from the Prometheus alert for tracing.
    """
    status: str
    alertname: str = "UnknownAlert"
    namespace: str = "default"
    pod: str = "unknown"
    original_labels: dict = {}


# ─── In-memory store for webhook-triggered analyses ───────────────────────────
# Keyed by (namespace, pod) so the UI can poll for the latest result.
_webhook_results: dict = {}


# ─── Background task ──────────────────────────────────────────────────────────

def _run_webhook_analysis(alertname: str, namespace: str, pod: str):
    """Triggered asynchronously when a firing Prometheus alert arrives.

    Runs the full RunWhen + LLM reasoning pipeline for the affected namespace
    and caches the result so the /analyze endpoint can surface it immediately.
    """
    logger.info(
        "Webhook analysis started | alert=%s namespace=%s pod=%s",
        alertname, namespace, pod,
    )
    try:
        results = analyze_cluster(alertname=alertname, namespace=namespace, pod=pod)
        _webhook_results[(namespace, pod)] = {
            "alertname": alertname,
            "namespace": namespace,
            "pod": pod,
            "results": results,
        }
        logger.info(
            "Webhook analysis complete | alert=%s issues_found=%d",
            alertname, len(results),
        )
    except Exception as exc:
        logger.exception("Webhook analysis failed for alert '%s': %s", alertname, exc)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "KubeOps-AI backend running"}


@app.get("/health")
def health():
    """Liveness / readiness probe endpoint."""
    return {"status": "ok"}


@app.get("/analyze")
def analyze():
    """Run a cluster-wide agentic analysis and return issues for the dashboard."""
    return analyze_cluster()


@app.post("/execute")
def execute(req: CommandRequest):
    """Execute a kubectl command that passed the guardrail check."""
    if not validate_action(req.command):
        return {"output": "❌ Command blocked by guardrail"}

    try:
        success, result = run_kubectl(req.command)

        # Store incident memory on successful execution
        if success and req.issue:
            store_issue(req.issue, req.command)

        return {"output": result}
    except Exception as exc:
        logger.exception("Unexpected execute() failure: %s", type(exc).__name__)
        return {"output": "Error: command execution failed unexpectedly."}


@app.post("/webhook/alert")
async def webhook_alert(payload: AlertPayload, background_tasks: BackgroundTasks):
    """Receive a firing alert from the Antigravity Listener and trigger analysis.

    The analysis is offloaded to a background task so this endpoint returns
    an immediate HTTP 200 to the listener (matching its timeout window).
    The result is cached in ``_webhook_results`` and served by /analyze.
    """
    logger.info(
        "Received webhook alert | alertname=%s status=%s namespace=%s pod=%s",
        payload.alertname, payload.status, payload.namespace, payload.pod,
    )

    if payload.status != "firing":
        # Clear any cached result when the alert resolves
        _webhook_results.pop((payload.namespace, payload.pod), None)
        return {
            "status": "ignored",
            "reason": f"Alert status is '{payload.status}', not 'firing'.",
        }

    background_tasks.add_task(
        _run_webhook_analysis,
        payload.alertname,
        payload.namespace,
        payload.pod,
    )

    return {
        "status": "accepted",
        "message": (
            f"Webhook analysis queued for alert '{payload.alertname}' "
            f"in namespace '{payload.namespace}'."
        ),
    }


@app.get("/webhook/results")
def webhook_results():
    """Return all cached webhook-triggered analysis results.

    The React dashboard polls this endpoint to surface event-driven incidents
    that were triggered by Prometheus → Alertmanager → Antigravity pipeline.
    """
    return list(_webhook_results.values())
