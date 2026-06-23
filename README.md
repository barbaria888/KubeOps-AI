  # KubeOps-AI

  <div align="center">
    <img alt="Kubernetes" src="https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white"/>
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi"/>
    <img alt="React" src="https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB"/>
    <img alt="Python" src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54"/>
  </div>

  <br/>

  **K8s Agentic AI Dashboard** is a powerful, autonomous troubleshooting pipeline that leverages local AI (Ollama + Gemma 2b) to analyze your Kubernetes clusters, deduce root causes, suggest actionable fixes, and maintain an **Incident Memory** vector database. Features a full **Approve & Run** interface to fix issues safely in just one click.

  <img width="1672" height="941" alt="architecture-diagram" src="https://github.com/user-attachments/assets/5bf6f41a-b7f3-49ef-afda-40735a03e663" />

  ---

  ## ✨ Features

  - **🧠 Agentic AI Pipeline**: Combines K8sGPT for issue discovery with local LLMs (Ollama) to deeply analyze Kubernetes faults.
  - **📚 Incident Vector Memory**: Uses `ChromaDB` + `SentenceTransformers` to store historic issues and solutions. The reasoning agent references previous fixes.
  - **🛡️ Guardrails Built-in**: Pre-execution filters prevent catastrophic commands (e.g., `delete`, `wipe`) to protect cluster integrity.
  - **⚡ "Approve & Run" UI**: A beautiful Vite + React Dashboard where administrators review AI-generated reasoning before executing `kubectl` actions.
  - **🐳 Cloud-Native Ready**: Includes native Kubernetes Deployments, Services, and Dockerfiles to run directly within your clusters.

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
      B -->|Reasoning| E[Ollama / Gemma 2B]
      B -->|Execute| F[Kubectl Tool]
  ```

  ---

  ## 🛠️ Tech Stack

  - **Backend:** Python, FastAPI, Pydantic, ChromaDB, SentenceTransformers
  - **Frontend:** React, Vite, Axios
  - **AI / Tools:** Ollama (Gemma 2B model), K8sGPT, Native Kubectl bindings

  ---

  ## 🚀 Quick Start (Local Run)

  ### 1. Prerequisites
  - `kubectl` configured with cluster access.
  - `k8sgpt` installed on your machine.
  - [Ollama](https://ollama.ai/) installed.

  ### 2. Start the AI Model
  ```bash
  ollama serve
  ollama pull gemma:2b
  ```

  ### 3. Start the Backend
  ```bash
  python -v venv venv
  source venv/bin/activate
  pip install -r requirements.txt

  uvicorn app.main:app --reload
  ```

  ### 4. Start the Frontend
  ```bash
  cd frontend
  npm install
  npm run dev
  ```

  ---

  ## 🐳 Kubernetes Deployment

To deploy this entire stack into your Kubernetes cluster, head over to the `k8s/` folder.

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/ollama.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
# or simply
kubectl apply -f k8s/
```

*Note: Our backend deployment expects access to Kubeconfig. By default, it maps `/etc/rancher/k3s/k3s.yaml` for K3s clusters.*

### 🌐 Access Points
Once deployed, core services are exposed via NodePorts for direct access without port-forwarding:

| Service | Access URL | Credentials |
|---|---|---|
| **KubeOps-AI Dashboard** | `http://<NODE_IP>:30007` | _None_ |
| **Grafana** | `http://<NODE_IP>:32000` | `admin` / `admin` |
| **Prometheus** | `http://<NODE_IP>:32001` | _None_ |
| **Alertmanager** | `http://<NODE_IP>:32002` | _None_ |

### 🎭 Platform Demo Scenarios
An interactive bash script `demo_setup.sh` is provided to demonstrate the core features of the platform:

| Scenario | Feature Tested | Action flow |
|---|---|---|
| **1** | AI Pipeline & Approve/Run | Deploys invalid `nginx:baddytag` image &rarr; pod enters `ImagePullBackOff` &rarr; AI analyzes and proposes fix &rarr; User executes fix via Dashboard. |
| **2** | Guardrail Protection | Attempts to execute `kubectl delete namespace k8s-ai` via API &rarr; intercepted and blocked by backend guardrails. |
| **3** | Incident Vector Memory | Seeds ChromaDB with historical incidents &rarr; deploys replica broken pod &rarr; AI references memory and highlights past solution. |
| **4** | Event-Driven Alert Loop | Deploys a crash-looping pod &rarr; Prometheus triggers alert &rarr; Webhook propagates to backend &rarr; Dashboards update with live alerts. |

Execute the demo:
```bash
chmod +x demo_setup.sh
./demo_setup.sh <NODE_IP>
```

### ⚙️ Rebuilding & Redeploying
To build your own container images and rollout updates into the cluster:

```bash
# 1. Rebuild and deploy Backend
docker build -t hardik0811/kubeops-ai-backend:latest .
docker push hardik0811/kubeops-ai-backend:latest
kubectl rollout restart deployment/backend -n k8s-ai

# 2. Rebuild and deploy Frontend
cd frontend
npm run build
docker build -t hardik0811/kubeops-ai-frontend:latest .
docker push hardik0811/kubeops-ai-frontend:latest
kubectl rollout restart deployment/frontend -n k8s-ai
```

---

## 📝 License
MIT License

---

## 📈 Event-Driven Observability

The project includes an event-driven monitoring stack using **Prometheus**, **Alertmanager**, and **Grafana** integrated with the KubeOps-AI pipeline. 
- Prometheus discovers cluster faults and triggers alerts.
- The webhook listener intercepts alerts and posts them to `POST /webhook/alert`.
- Firing alerts initiate a FastAPI `BackgroundTask` to invoke a targeted `k8sgpt` analysis using `--namespace <ns>` to avoid false positives and speed up execution.
- Webhook results are cached in-memory and exposed via `GET /webhook/results` for React dashboard polling.
- Once an alert resolves (`status == "resolved"`), it is automatically cleared from the active memory cache.
