# K8s Agentic AI Architecture & Flow Guide

Welcome to the detailed architectural breakdown of the **KubeOps-AI Dashboard**. This document explains the purpose, components, and data flow of the entire system, combining insights from the Kubernetes deployments, FastAPI backend, and React frontend.

---

## 🎯 What is it used for?

The KubeOps-AI system is a **powerful, autonomous troubleshooting pipeline** designed to monitor, diagnose, and remediate issues within a Kubernetes cluster. 

Instead of an administrator manually hunting down failing pods or reading cryptic logs, this system automatically:
1. Discovers cluster issues using `RunWhen Skills Registry`.
2. Analyzes the root cause using your **chosen LLM** — either a private, local model (Ollama) or a powerful cloud model (NVIDIA NIM API).
3. Consults an "Incident Memory" (Vector Database) to remember past fixes.
4. Suggests a concrete `kubectl` command to fix the issue.
5. Provides a web-based UI where an admin can safely **Approve & Run** the remediation with one click.

---

## 🤖 LLM Provider Architecture

The system supports two LLM backends, selectable at deploy time via the `LLM_PROVIDER` environment variable. The unified `app/tools/llm.py` module routes all agent calls to the correct backend transparently.

```mermaid
graph TB
    subgraph "Agents"
        R[reasoning.py]
        A[action.py]
    end
    subgraph "LLM Router"
        L["app/tools/llm.py\nquery_llm()"]
    end
    subgraph "Backends"
        O["Ollama\n(LLM_PROVIDER=ollama)\nLocal, Free, Private"]
        N["NVIDIA NIM API\n(LLM_PROVIDER=nvidia)\nCloud, Fast, 70B+ models"]
    end

    R --> L
    A --> L
    L -->|"LLM_PROVIDER=ollama"| O
    L -->|"LLM_PROVIDER=nvidia"| N
```

### LLM Provider Comparison

| Feature | Local Ollama | NVIDIA NIM API |
|---|---|---|
| **Cost** | Free | Pay-per-token (free tier available) |
| **Privacy** | 100% on-premise | Cloud API call |
| **Speed** | Slower (CPU) | Very fast (GPU cloud) |
| **Model Quality** | TinyLlama / Gemma 2B | 70B+ parameter models |
| **Internet Required** | No (after image pull) | Yes |
| **Setup** | Auto (setup.sh pulls model) | NVIDIA API key required |


---

## 🔄 End-to-End System Flow

### 1. Manual Analysis & Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend as Nginx + React UI
    participant Backend as FastAPI Core
    participant Tools as RunWhen & Kubectl
    participant LLM as "Ollama OR NVIDIA NIM"
    participant DB as ChromaDB (Memory)

    %% Flow: Fetching Issues
    User->>Frontend: Open Dashboard
    Frontend->>Backend: GET /api/analyze
    Backend->>Tools: Fetch diagnostic data via RunWhen
    Tools-->>Backend: Return Raw Cluster Issues
    
    %% Flow: AI Reasoning
    Backend->>DB: Query for similar historic issues
    DB-->>Backend: Return past context
    Backend->>LLM: Prompt (Issue + Context) via query_llm()
    LLM-->>Backend: Generate Explanation & Fix Command
    
    %% Flow: Guardrail & UI Display
    Backend->>Backend: Guardrail Check (Safe / Unsafe)
    Backend-->>Frontend: Return Analyzed Issues (JSON)
    Frontend-->>User: Display Scorpio-themed Dashboard
```

### 2. Event-Driven Webhook Alert Flow

```mermaid
sequenceDiagram
    participant Cluster as K8s Cluster Pod
    participant Prom as Prometheus
    participant AM as Alertmanager
    participant AL as Antigravity Listener
    participant Backend as FastAPI Core
    participant Tools as RunWhen (Targeted)
    participant LLM as "Ollama OR NVIDIA NIM"

    Cluster->>Prom: Enters crash / failure state
    Prom->>AM: Fire Alert (alertname, namespace, pod)
    AM->>AL: Forward Webhook payload
    AL->>Backend: POST /webhook/alert {status: firing, namespace, pod}
    
    Note over Backend: Spawns FastAPI BackgroundTask
    Backend-->>AL: HTTP 200 (Accepted)
    Backend->>Tools: Execute mapped RunWhen script
    Tools-->>Backend: Return targeted namespace issues
    Backend->>LLM: Prompt via query_llm()
    LLM-->>Backend: AI explanation + fix command
    Note over Backend: Cache in-memory (_webhook_results)
```

### 3. Execution & Verification Loop Flow

```mermaid
sequenceDiagram
    participant User
    participant UI as React UI (App.jsx)
    participant Backend as FastAPI Core
    participant Tool as Kubectl

    User->>UI: Click "Approve & Run"
    UI->>Backend: POST /api/execute {command, issue}
    Backend->>Tool: Run `kubectl <command>`
    Tool-->>Backend: Command Execution Output
    Backend-->>UI: Return raw terminal output
    Note over UI: Display Inline Output Panel & Start Verification Loop
    
    Loop Every 5s (Up to 12 attempts / 60s)
        UI->>Backend: GET /api/analyze
        Backend-->>UI: Active issues list
        alt Issue resolved
            Note over UI: Clear loop, show success
        else Max attempts
            Note over UI: Show timeout warning
        end
    end
```

---

## 🖥️ The Frontend Approach

The frontend is a **React + Vite** application built for speed and aesthetics. 

> [!TIP]
> The UI uses a custom **Scorpio Theme** built entirely with pure, vanilla CSS. It avoids heavy external libraries like Tailwind or Bootstrap to keep the bundle size small while delivering a premium, dark-mode, glassmorphic aesthetic with neon accents.

### Routing & Communication
Because the React app runs in the user's browser, it cannot directly resolve internal Kubernetes DNS. To solve this:
- The frontend is served inside the cluster using an **Nginx** web server.
- Nginx is configured as a **Reverse Proxy**.
- The React app makes requests to `/api`, and Nginx intercepts these and securely forwards them to the internal FastAPI backend service.

### Remediation Verification Loop
After a user approves and executes a fix:
- An animated `Verifying fix… poll N/12` badge appears.
- A background `setInterval` polls the backend every 5 seconds.
- If the issue disappears from the issues list, the loop terminates and the UI updates automatically.
- A manual **Refresh button** and **Last refreshed** timestamp are always available in the header.

---

## 🧠 The Backend Approach

The backend is built with **FastAPI** (Python) and acts as the "Intelligence Core" of the system.

### Directory Structure & Roles
- **Agents (`app/agents/`)**:
  - `analyzer.py`: Orchestrates the pipeline. Maps alerts to RunWhen scripts. Uses multi-command validation (`validate_action_list`) and fallback actions.
  - `reasoning.py`: Invokes `gather_cluster_context()` for live cluster context, fetches similar incidents, and prompts the LLM for a multi-step analysis (Root Cause, Evidence, 5-8 Investigation Commands, Fix, Rollback).
  - `action.py`: Builds multi-step execution plans (DIAGNOSTIC → REMEDIATION → VERIFICATION) using live context.
  - `guardrail.py`: Blocks destructive commands. Validates multi-line actions with `validate_action_list` and filters blocked keywords (`delete`, `rm`, `wipe`, `format`, `exec`, `apply`, `edit`).
- **Tools (`app/tools/`)**:
  - `llm.py`: **Unified LLM router**. Configures the comprehensive `SRE_SYSTEM_PROMPT` containing RBAC-allowed verbs.
  - `cluster_context.py`: **Live Cluster Context Collector**. Runs RBAC-compliant diagnostic commands (`kubectl get pods`, `kubectl get events`, `kubectl top pods/nodes`, `kubectl describe pod`, `kubectl logs --tail=50 --previous`) and truncates outputs.
  - `ollama.py`: Ollama HTTP client (used when `LLM_PROVIDER=ollama`). Custom `num_predict: 1024` for full diagnostic output.
  - `runwhen.py`: Deterministic router that executes audited RunWhen CodeBundle scripts based on Prometheus alertnames.
  - `kubectl.py`: kubectl subprocess runner.
  - `vector_store.py`: ChromaDB Incident Memory client. Fetches top 5 incidents and formats them.

### Key Environment Variables

| Variable | Values | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` / `nvidia` | Selects the active LLM backend |
| `NVIDIA_API_KEY` | `nvapi-...` | From K8s Secret — never committed to code |
| `NVIDIA_MODEL` | Any NIM model ID | Default: `nvidia/llama-3.3-nemotron-super-49b-v1` |
| `OLLAMA_MODEL` | Any Ollama tag | Default: `tinyllama:latest` |
| `KUBEOPS_ENABLE_FULL_AI` | `true` / `false` | Enable LLM reasoning pipeline |

> [!IMPORTANT]
> **Incident Memory**: Every time a user successfully runs an action, the backend saves the `(Issue → Successful Command)` pairing into ChromaDB. The next time a similar issue occurs, the reasoning agent fetches this memory and feeds it to the LLM — the system **learns** from past outages regardless of which LLM backend is active.

### Webhook API
- `POST /webhook/alert`: Receives alert payloads. If `status == "firing"`, queues a BackgroundTask to analyze only the affected namespace.
- `GET /webhook/results`: Serves cached analysis results to the dashboard.
- `GET /health`: Liveness/readiness probe.

---

## 🐳 The Kubernetes (K8s) Approach

### Component Breakdown
1. **Namespace (`namespace.yaml`)**: Creates `k8s-ai` sandbox.
2. **RBAC (`rbac.yaml`)**: Dedicated `kubeops-ai-backend` ServiceAccount + least-privilege `kubeops-ai-operator` ClusterRole. Verbs are strictly aligned with the Python guardrail's allowed list. Destructive operations (`delete`, `create`, `exec`) are **not** granted.
3. **Ollama (`ollama.yaml`)**: *(Ollama mode only)* Deploys the local LLM server. Completely skipped in NVIDIA mode.
4. **Backend (`backend.yaml`)**: FastAPI intelligence core.
    - Uses `serviceAccountName: kubeops-ai-backend` for in-cluster Kubernetes API access.
    - Configures `LLM_PROVIDER`, `NVIDIA_API_KEY` (from Secret), `NVIDIA_MODEL`, `OLLAMA_URL` etc.
    - **initContainer** fetches the RunWhen CodeCollection git repository.
    - `KUBEOPS_ENABLE_VECTOR_STORE: "true"` — ChromaDB Incident Memory enabled by default.
    - NVIDIA API key injected from `nvidia-api-key` Secret via `valueFrom.secretKeyRef` (marked `optional: true` so Ollama mode pods still start).
5. **Frontend (`frontend.yaml`)**: Nginx + React UI via NodePort `30007`.
6. **nvidia-secret.yaml**: Template for the Kubernetes Secret. Populated by `setup.sh` at runtime.
7. **kube-state-metrics (`kube-state-metrics.yaml`)**: Exports Kubernetes object state as Prometheus metrics. Required for alert rules to function.

### Security Model — Defense in Depth

KubeOps-AI enforces two independent security layers:

| Layer | Allowed Verbs | Blocked Verbs |
|---|---|---|
| **RBAC ClusterRole** | `get`, `list`, `watch`, `patch`, `update` (scoped) | `delete`, `create` (except port-forward), `exec` |
| **Python Guardrail** | `get`, `describe`, `logs`, `set`, `rollout`, `scale`, `annotate`, `label`, `top`, `cordon`, `uncordon`, `port-forward` | `delete`, `rm`, `wipe`, `format`, `exec`, `apply`, `edit` |
Both layers enforce independently — even if one layer has a bug, the other provides a safety net.

### Connecting it all together
- **Frontend Pod** receives traffic on port `30007`.
- Nginx routes `/api` traffic internally to the **Backend Service** on port `8000`.
- Backend calls **Ollama Service** (internal port `11434`) OR **NVIDIA NIM API** (external HTTPS) based on `LLM_PROVIDER`.
- Backend uses its mounted ServiceAccount token (auto-injected at `/var/run/secrets/kubernetes.io/serviceaccount/`) to talk to the **Kubernetes API Server** — no kubeconfig file needed.

---

## 📈 The Observability Stack

All observability components are exposed via NodePorts for direct access:

| Component | NodePort | Role |
|---|---|---|
| **Prometheus** | `32001` | Scrapes kube-state-metrics, evaluates alert rules |
| **Alertmanager** | `32002` | Routes alerts to Antigravity Listener |
| **Grafana** | `32000` | Visual dashboards (`admin` / `admin`) |
| **kube-state-metrics** | Internal | Exports Kubernetes object state as Prometheus metrics |
| **Antigravity Listener** | Internal | Webhook bridge: Alertmanager → Backend |

### Event Flow
```
Pod Failure
  → kube-state-metrics (exports kube_pod_container_status_restarts_total)
  → Prometheus (evaluates alert rules, detects threshold breach)
  → Alertmanager (routes via webhook_configs)
  → Antigravity Listener (POST /webhook/alertmanager)
  → FastAPI Backend (POST /webhook/alert)
  → BackgroundTask: runwhen_diagnostic + query_llm()
  → _webhook_results cache
  → React Dashboard (polls GET /webhook/results)
  → Admin sees issue card → Approve & Run → Fix verified
```
