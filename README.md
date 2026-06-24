  # KubeOps-AI

  <div align="center">
    <img alt="Kubernetes" src="https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white"/>
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi"/>
    <img alt="React" src="https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB"/>
    <img alt="Python" src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54"/>
    <img alt="NVIDIA" src="https://img.shields.io/badge/NVIDIA NIM-76B900?style=for-the-badge&logo=nvidia&logoColor=white"/>
    <img alt="Ollama" src="https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white"/>
  </div>

  <br/>

  **KubeOps-AI** is an autonomous Kubernetes troubleshooting platform that uses AI (your choice of **local Ollama** or **NVIDIA NIM cloud LLMs**) to analyze cluster faults, deduce root causes, suggest actionable fixes, and maintain an **Incident Memory** vector database. Features a full **Approve & Run** interface to remediate issues safely in one click.

  <img width="1536" height="1024" alt="Image" src="https://github.com/user-attachments/assets/045b17ed-4c3b-474e-8103-4cf480e25d7d" />

  ---

  ## ✨ Features

  - **🧠 Dual LLM Support**: Choose between **Local Ollama** (free, private, runs inside your cluster) or **NVIDIA NIM API** (cloud, fast, access to 70B+ parameter models). Switch at any time without rebuilding images.
  - **📚 Incident Vector Memory**: Uses `ChromaDB` + `SentenceTransformers` to store historic issues and solutions. The reasoning agent references previous fixes automatically.
  - **🛡️ Guardrails Built-in**: Pre-execution filters prevent catastrophic commands (e.g., `delete`, `wipe`) to protect cluster integrity.
  - **⚡ "Approve & Run" UI**: A beautiful Vite + React Dashboard where administrators review AI-generated reasoning before executing `kubectl` actions.
  - **🔔 Event-Driven Alerts**: Full Prometheus → Alertmanager → Webhook pipeline that surfaces diagnosed issues on the dashboard automatically.
  - **✅ Remediation Verification Loop**: After executing a fix, the dashboard polls every 5 seconds (up to 60 seconds) to automatically confirm the issue is resolved.
  - **🐳 Cloud-Native Ready**: Includes native Kubernetes Deployments, Services, and Dockerfiles to run directly within your clusters.
  - **🚀 One-Command Setup**: Interactive `setup.sh` handles LLM provider selection, API key secrets, deployment, and health checks automatically.

  <img width="936" height="467" alt="dashboard-empty" src="https://github.com/user-attachments/assets/d8667305-084f-4848-a4dc-7f657dfb6ba8" />

  ---

  <img width="843" height="473" alt="Image" src="https://github.com/user-attachments/assets/13f69da5-2611-431d-a3ee-d3eb8b81a77f" />

  ---

  ## 🏗️ Architecture

  ```mermaid
  graph LR
      A[React Dashboard] -->|REST API| B[FastAPI Backend]
      B -->|Query / Add| C[(ChromaDB Vector Store)]
      B -->|Analyze| D[K8sGPT Tool]
      B -->|LLM_PROVIDER=ollama| E[Ollama / TinyLlama]
      B -->|LLM_PROVIDER=nvidia| G[NVIDIA NIM API]
      B -->|Execute| F[Kubectl Tool]
      H[Prometheus] -->|Scrapes| I[kube-state-metrics]
      H -->|Fires alerts| J[Alertmanager]
      J -->|Webhook| K[Antigravity Listener]
      K -->|POST /webhook/alert| B
  ```

  ---

  ## 🛠️ Tech Stack

  - **Backend:** Python, FastAPI, Pydantic, ChromaDB, SentenceTransformers, OpenAI SDK
  - **Frontend:** React, Vite, Axios
  - **AI / LLMs:** Ollama (TinyLlama / Gemma 2B) **or** NVIDIA NIM API — user's choice
  - **Observability:** K8sGPT, Prometheus, Grafana, Alertmanager, kube-state-metrics
  - **Security:** RBAC (least-privilege ServiceAccount + ClusterRole aligned with guardrails)

  ---

  ## 🚀 Quick Start — Interactive Setup (Recommended)

  The easiest way to deploy KubeOps-AI is the interactive setup script:

  ```bash
  git clone https://github.com/barbaria888/KubeOps-AI.git
  cd KubeOps-AI

  chmod +x setup.sh
  NODE_IP=$(curl -s ifconfig.me) 
  ./setup.sh $NODE_IP
  ```

  The script will guide you through:
  1. ✅ Preflight checks (kubectl, docker, curl connectivity)
  2. 🤖 **LLM provider selection**: Local Ollama or NVIDIA NIM
  3. 🔑 API key collection (NVIDIA) — stored securely as a K8s Secret
  4. 🐳 Full stack deployment with progress indicators
  5. 📋 Access URL summary

  > **For the full installation guide** (including manual steps, model switching, and troubleshooting), see [SETUP.md](./SETUP.md).

  ---

  ## 🤖 LLM Provider Options

  | Option | Description | Best For |
  |---|---|---|
  | **Local Ollama** | TinyLlama or Gemma 2B runs inside the cluster. Free, private, no external API. | Air-gapped, demos, CPU nodes |
  | **NVIDIA NIM API** | Hosted inference on NVIDIA GPUs via the NVIDIA NIM platform. Fast, high-quality 70B+ models. | Production demos, best accuracy |

  ### Quick Start with Ollama (Local)

  ```bash
  # 1. Start the backend locally
  python -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  LLM_PROVIDER=ollama uvicorn app.main:app --reload

  # 2. Start frontend
  cd frontend && npm install && npm run dev
  ```

  ### Quick Start with NVIDIA NIM (Cloud)

  ```bash
  # 1. Set your NVIDIA API key
  export NVIDIA_API_KEY="nvapi-xxxx..."
  export LLM_PROVIDER="nvidia"

  # 2. Start the backend
  python -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  uvicorn app.main:app --reload

  # 3. Start frontend
  cd frontend && npm install && npm run dev
  ```

  > Get a free NVIDIA API key at [build.nvidia.com](https://build.nvidia.com/)

  ---

  ## 🐳 Kubernetes Deployment

  The recommended path is `setup.sh`. For manual deployment:

  ```bash
  kubectl apply -f k8s/namespace.yaml
  kubectl apply -f k8s/rbac.yaml                  # Least-privilege RBAC for backend
  kubectl apply -f k8s/backend.yaml
  kubectl apply -f k8s/frontend.yaml
  kubectl apply -f k8s/kube-state-metrics.yaml     # Required for Prometheus metrics

  # Ollama only (skip for NVIDIA mode):
  kubectl apply -f k8s/ollama.yaml
  ```

  > **Note:** The backend uses an in-cluster ServiceAccount (`kubeops-ai-backend`) for Kubernetes API access via RBAC. No kubeconfig file mount is needed — works on any distribution (K3s, K8s, Kind, Minikube).

  ### 🌐 Access Points
  All services are exposed via NodePorts — no `kubectl port-forward` needed:

  | Service | Access URL | Credentials |
  |---|---|---|
  | **KubeOps-AI Dashboard** | `http://<NODE_IP>:30007` | _None_ |
  | **Grafana** | `http://<NODE_IP>:32000` | `admin` / `admin` |
  | **Prometheus** | `http://<NODE_IP>:32001` | _None_ |
  | **Alertmanager** | `http://<NODE_IP>:32002` | _None_ |

  ### 🎭 Platform Demo Scenarios

  Once deployed, run all four platform scenarios:

  ```bash
  chmod +x demo_setup.sh
  ./demo_setup.sh <NODE_IP>                       # Auto-detects LLM provider
  ./demo_setup.sh <NODE_IP> --provider nvidia      # Force NVIDIA mode
  ./demo_setup.sh <NODE_IP> --provider ollama      # Force Ollama mode
  ```

  | Scenario | Feature Tested | What Happens |
  |---|---|---|
  | **1** | AI Pipeline & Approve/Run | Deploys invalid `nginx:baddytag` → `ImagePullBackOff` → AI diagnoses → Dashboard shows fix → User approves |
  | **2** | Guardrail Protection | Sends `kubectl delete namespace k8s-ai` via API → Blocked by guardrail |
  | **3** | Incident Vector Memory | Seeds ChromaDB → Deploys similar broken pod → AI cites past fix |
  | **4** | Event-Driven Alert Loop | Crash-looping pod → Prometheus → Alertmanager → Webhook → Dashboard updates |

  ### ⚙️ Rebuilding & Redeploying

  ```bash
  # Backend
  docker build -t hardik0811/kubeops-ai-backend:latest .
  docker push hardik0811/kubeops-ai-backend:latest
  kubectl rollout restart deployment/backend -n k8s-ai

  # Frontend
  cd frontend && npm run build
  docker build -t hardik0811/kubeops-ai-frontend:latest .
  docker push hardik0811/kubeops-ai-frontend:latest
  kubectl rollout restart deployment/frontend -n k8s-ai
  ```

  ---

  ## 📝 License
  MIT License

  ---

  ## 🛡️ Security — RBAC Model

  KubeOps-AI uses **defense-in-depth** with two complementary security layers:

  1. **Kubernetes RBAC** (`k8s/rbac.yaml`): A dedicated `kubeops-ai-backend` ServiceAccount with a least-privilege ClusterRole. Destructive verbs (`delete`, `create`, `exec`) are not granted at the API level.
  2. **Python Guardrails** (`app/agents/guardrail.py`): Pre-execution filter that blocks commands containing `delete`, `rm`, `wipe`, `format`, shell injection patterns, and non-allowed kubectl verbs.

  Even if the LLM suggests a destructive command, it is blocked by **both** layers.

  ---

  ## 📈 Event-Driven Observability

  The project includes an event-driven monitoring stack using **Prometheus**, **Alertmanager**, **kube-state-metrics**, and **Grafana** integrated with the KubeOps-AI pipeline.

  - **kube-state-metrics** exports Kubernetes object state as Prometheus metrics (e.g., pod restart counts, deployment status).
  - Prometheus scrapes kube-state-metrics and evaluates alert rules (e.g., `PodCrashLooping`).
  - Alertmanager routes firing alerts to the **Antigravity Listener** webhook.
  - The listener forwards the alert payload to `POST /webhook/alert` on the backend.
  - Firing alerts initiate a FastAPI `BackgroundTask` running targeted `k8sgpt` analysis (`--namespace <ns>`).
  - Webhook results are cached in-memory and exposed via `GET /webhook/results` for React dashboard polling.
  - When an alert resolves (`status == "resolved"`), the cached entry is automatically cleared.
