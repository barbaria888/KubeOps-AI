import logging
import asyncio
from fastapi import FastAPI, BackgroundTasks, Request, Response
import httpx

app = FastAPI(title="Antigravity Alertmanager Listener")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("antigravity-listener")

DOWNSTREAM_URL = "http://backend.k8s-ai.svc.cluster.local:8000/webhook/alert"

async def process_alerts(payload: dict):
    """
    Parses the Alertmanager payload, extracts critical variables, and forwards
    firing alerts to the downstream KubeOps-AI backend with exponential backoff.
    """
    alerts = payload.get("alerts", [])
    
    for alert in alerts:
        status = alert.get("status")
        
        # 1. & 2. Data Parsing: Only execute if status == "firing"
        if status != "firing":
            continue
            
        labels = alert.get("labels", {})
        
        # Extract metadata
        alertname = labels.get("alertname", "UnknownAlert")
        namespace = labels.get("namespace", "default")
        pod = labels.get("pod") or labels.get("resource_name") or "unknown_resource"
        
        # 4. Resiliency: Explicit metadata tracing log
        logger.info(f"Trace [START]: Alert '{alertname}' FIRING in namespace '{namespace}'. Affected resource: {pod}")
        
        # 3. Downstream Payload Construction
        forward_payload = {
            "status": status,
            "alertname": alertname,
            "namespace": namespace,
            "pod": pod,
            "original_labels": labels
        }
        
        # 4. Resiliency: Exponential backoff retry (up to 3 retries)
        max_retries = 3
        base_delay = 2  # seconds
        
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        DOWNSTREAM_URL,
                        json=forward_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=10.0
                    )
                    response.raise_for_status()
                    logger.info(f"Trace [SUCCESS]: Successfully forwarded alert '{alertname}' to KubeOps-AI.")
                    break  # Break out of the retry loop on success
                    
            except httpx.HTTPError as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Trace [RETRY]: Downstream API unavailable. Retrying in {delay}s... "
                        f"(Attempt {attempt + 1}/{max_retries}). Error: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Trace [FAILED]: Exhausted all retries for '{alertname}'. Error: {e}")

@app.post("/webhook/alertmanager")
async def alertmanager_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    1. Hook / Receiver Definition:
    Receives incoming POST payloads from Alertmanager and offloads
    processing to background tasks for an immediate HTTP 200 OK.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        return Response(status_code=400, content="Invalid JSON")
        
    # Asynchronous execution trigger
    background_tasks.add_task(process_alerts, payload)
    
    # Immediate acknowledgment to Alertmanager
    return {"status": "accepted", "message": "Alert processing initiated"}

if __name__ == "__main__":
    import uvicorn
    # Direct execution block
    uvicorn.run(app, host="0.0.0.0", port=8080)
