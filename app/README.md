# 🧠 Fast AI Backend

This directory contains the core intelligence of the KubeOps-AI system. Built with **FastAPI**, it orchestrates the interaction between K8sGPT, your local Kubernetes cluster, a Vector Database, and the active LLM backend (**Ollama** or **NVIDIA NIM**).

## 📁 Directory Structure
```text
app/
├── main.py            # FastAPI Entry Point — Routes & Webhook handlers
├── agents/            # Autonomous AI Agents
│   ├── analyzer.py    # Orchestrates the pipeline; scoped namespace support
│   ├── reasoning.py   # Builds contextual prompt + calls query_llm()
│   ├── action.py      # Generates safe kubectl command via query_llm()
│   └── guardrail.py   # Blocks destructive commands before execution
└── tools/             # Integrations
    ├── llm.py         # ⭐ Unified LLM router (Ollama ↔ NVIDIA NIM)
    ├── k8sgpt.py      # K8sGPT subprocess runner (supports --namespace)
    ├── kubectl.py     # Kubectl subprocess runner
    ├── ollama.py      # Ollama HTTP client (used when LLM_PROVIDER=ollama)
    └── vector_store.py # ChromaDB Incident Memory
```

## 🤖 LLM Abstraction Layer (`app/tools/llm.py`)

The new `llm.py` module is the heart of the dual-provider feature. All agents call a single function:

```python
from app.tools.llm import query_llm

result = query_llm("Explain this Kubernetes fault: ...")
```

Internally, `query_llm()` reads the `LLM_PROVIDER` env var and routes to the correct backend:

| `LLM_PROVIDER` | Backend | Notes |
|---|---|---|
| `ollama` | Local Ollama via HTTP | Default. Free, private. Requires Ollama pod. |
| `nvidia` | NVIDIA NIM API via `openai` SDK | Requires `NVIDIA_API_KEY` K8s Secret. |

## 🔄 How the Pipeline Works

1. **Discovery** (`GET /analyze` or `POST /webhook/alert`):
   - The backend runs `k8sgpt analyze`. Webhook alerts trigger a targeted namespace analysis (`--namespace <ns>`) via a FastAPI `BackgroundTask`.
   - For every issue found, the text is passed to the **Reasoning Agent**.

2. **Context Retrieval**: The Reasoning Agent queries **ChromaDB** for similar historic incidents.

3. **LLM Reasoning**: `query_llm()` is called with the issue + historic context. Depending on `LLM_PROVIDER`:
   - **Ollama**: Posts to the local Ollama HTTP API.
   - **NVIDIA NIM**: Calls the NVIDIA NIM endpoint using the `openai` SDK (`base_url=https://integrate.api.nvidia.com/v1`).

4. **Validation**: The **Guardrail Agent** scans the suggested `kubectl` command. Commands containing `delete`, `rm`, `wipe`, or shell injection patterns are marked `safe: false`.

5. **Execution** (`POST /execute`): If approved by the frontend, the command runs. On success, the `(Issue → Fix)` pair is stored in ChromaDB for future context.

## 🚀 Running Locally

```bash
# Clone and install
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt

# Run with Ollama (local)
export LLM_PROVIDER=ollama
uvicorn app.main:app --reload --port 8000

# Run with NVIDIA NIM
export LLM_PROVIDER=nvidia
export NVIDIA_API_KEY="nvapi-xxxx..."
uvicorn app.main:app --reload --port 8000
```

*(Backend expects Ollama on `http://localhost:11434` and `kubectl`/`k8sgpt` installed when using Ollama mode).*

## 🔌 API Endpoints

| Route | Method | Description |
|---|---|---|
| `/` | `GET` | Home greeting. |
| `/health` | `GET` | Liveness/readiness probe. |
| `/analyze` | `GET` | Cluster-wide analysis via active LLM backend. |
| `/execute` | `POST` | Validates and runs safe `kubectl` actions; indexes success in Vector Memory. |
| `/webhook/alert` | `POST` | Receives `AlertPayload` from Antigravity Listener; queues `BackgroundTask`. |
| `/webhook/results` | `GET` | Returns cached webhook-triggered analysis results for dashboard polling. |

### Webhook Flow Detail
1. `POST /webhook/alert` receives `{status, alertname, namespace, pod, ...}`.
2. If `status == "firing"` → spawns `BackgroundTask` → `analyze_cluster(namespace=...)`.
3. Result cached in `_webhook_results[(namespace, pod)]`.
4. If `status == "resolved"` → cache entry removed.
5. Dashboard polls `GET /webhook/results` to surface alerts.

## ⚙️ Key Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `"ollama"` or `"nvidia"` |
| `NVIDIA_API_KEY` | _(from K8s Secret)_ | NVIDIA NIM API key |
| `NVIDIA_MODEL` | `nvidia/llama-3.3-nemotron-super-49b-v1` | NIM model to use |
| `OLLAMA_URL` | `http://ollama:11434/api/generate` | Ollama endpoint |
| `OLLAMA_MODEL` | `tinyllama:latest` | Ollama model |
| `KUBEOPS_ENABLE_FULL_AI` | `true` | Enable full LLM reasoning (new canonical name) |
| `KUBEOPS_ENABLE_FULL_OLLAMA` | _(legacy alias)_ | Backward-compatible alias for above |
