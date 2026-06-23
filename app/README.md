# 🧠 Fast AI Backend

This directory contains the core intelligence of the K8s Agentic AI system. Built with **FastAPI**, it orchestrates the interaction between K8sGPT, your local Kubernetes cluster, a Vector Database, and the Ollama LLM.

## 📁 Directory Structure
```text
app/
├── main.py            # FastAPI Entry Point (Routes)
├── agents/            # Autonomous AI Agents
│   ├── analyzer.py    # Extracts issues from K8sGPT
│   ├── reasoning.py   # Asks Ollama to explain the issue (with Vector Context)
│   ├── action.py      # Generates a safe kubectl command
│   └── guardrail.py   # Blocks destructive commands
├── tools/             # Integrations
│   ├── k8sgpt.py      # K8sGPT subprocess runner
│   ├── kubectl.py     # Kubectl subprocess runner
│   ├── ollama.py      # Local LLM API connector
│   └── vector_store.py# ChromaDB Incident Memory
```

## 🔄 How the Pipeline Works

1. **Discovery (`GET /analyze` or Webhook `POST /webhook/alert`)**: The backend triggers `k8sgpt analyze`. Webhook alerts trigger a targeted namespace analysis (`--namespace <ns>`) via a FastAPI `BackgroundTask` to bypass global scanning. For every issue found, the text is sent to the **Reasoning Agent**.
2. **Context Retrieval**: The Reasoning Agent queries **ChromaDB** for similar historic incidents.
3. **LLM Generation**: Ollama (`gemma:2b`) is prompted with the issue + historic context to generate an explanation and a suggested fix.
4. **Validation**: The **Guardrail Agent** scans the suggested `kubectl` command. If it contains words like `delete`, `rm`, or `wipe`, it marks `safe: false`.
5. **Execution `POST /execute`**: If approved by the frontend, the command runs. If successful, the incident (Issue + Solution pair) is permanently saved into the Vector Database for future reference!

## 🚀 Running Locally

Create a virtual environment and start the server:
```bash
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
uvicorn app.main:app --reload --port 8000
```
*(The backend expects Ollama to be running on `http://localhost:11434` and `kubectl / k8sgpt` to be installed on your host).*

## 🔌 API Endpoints & Event-Driven Webhooks

The backend exposes the following endpoint routes:

| Route | Method | Description |
|---|---|---|
| `/` | `GET` | Home greeting endpoint. |
| `/health` | `GET` | Liveness/readiness check probe. |
| `/analyze` | `GET` | Runs a cluster-wide analysis. |
| `/execute` | `POST` | Validates and runs safe `kubectl` actions, then indexes them in Vector Memory. |
| `/webhook/alert` | `POST` | Intercepts alerts from the **Antigravity Listener**. Enqueues a `BackgroundTask` to analyze the specific `namespace` of the alert. |
| `/webhook/results` | `GET` | Returns cached results of webhook-triggered analyses for polling by the dashboard. |

### Webhook Flow Detail
1. `POST /webhook/alert` receives an `AlertPayload` (`status`, `alertname`, `namespace`, `pod`, etc.).
2. If `status == "firing"`, a FastAPI `BackgroundTask` is spawned to execute `analyze_cluster(namespace=...)`.
3. The resulting diagnosis is stored in an in-memory dictionary cache (`_webhook_results`) keyed by `(namespace, pod)`.
4. When `status == "resolved"`, the cache entry is immediately popped and cleared.
5. The React dashboard retrieves these results dynamically by calling `GET /webhook/results`.
