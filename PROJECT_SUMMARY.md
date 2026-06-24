# KubeOps-AI: Project Summary & Architecture Guide

## 📌 Executive Summary

**KubeOps-AI** is an autonomous, event-driven Kubernetes troubleshooting and remediation platform. It acts as an intelligent "Agentic SRE" (Site Reliability Engineer) that constantly monitors your clusters, detects anomalies, infers root causes using a localized LLM, consults a historic memory of past incidents, and proposes one-click fixes through a unified dashboard.

Designed completely around cloud-native principles, the entire stack—from the AI models to the monitoring framework—is built to be deployed securely inside the same Kubernetes cluster it manages, ensuring zero data exfiltration of sensitive cluster logs.

---

## 🏗️ Architectural Components

The architecture consists of three major pillars: **The Intelligence Core**, **The UI Dashboard**, and **The Observability Stack**.

### 1. The Intelligence Core (Backend)
Built on **FastAPI (Python)**, this is the brain of the operation. It orchestrates the entire agentic loop.
- **Issue Discovery (`k8sgpt`)**: Scans the cluster state to find faulty resources (e.g., CrashLoopBackOff pods, Pending PVCs).
- **AI Reasoning (Dual LLM Support)**: Takes the raw failure data and asks either a locally hosted **Ollama** model (TinyLlama/Gemma 2B) or the cloud-based **NVIDIA NIM API** (70B+ parameter models) to explain the issue and formulate a fix. Selectable via `LLM_PROVIDER` environment variable.
- **Incident Memory (ChromaDB)**: Every successful resolution is embedded via `SentenceTransformers` and stored in ChromaDB. Before reasoning, the backend queries this database so the AI "learns" from past identical outages in your specific environment.
- **Guardrails**: A strict regex/semantic filter that intercepts any suggested `kubectl` commands. Destructive actions (like `delete namespace` or `rm -rf`) are automatically blocked.
- **RBAC (Defense-in-Depth)**: The backend pod runs under a dedicated `kubeops-ai-backend` ServiceAccount with a least-privilege `kubeops-ai-operator` ClusterRole. Destructive verbs (`delete`, `create`, `exec`) are blocked at the Kubernetes API level, complementing the Python guardrail.

### 2. The Operations Dashboard (Frontend)
Built using **React + Vite**, the frontend provides a sleek, dark-mode, glassmorphic UI (Scorpio Theme) utilizing pure CSS.
- **Approve & Run**: Instead of the AI executing commands blindly, it presents the diagnosis and proposed `kubectl` command to the administrator. The admin clicks "Approve & Run" to execute it safely.
- **Nginx Reverse Proxy**: Since React runs client-side and cannot resolve internal cluster DNS, Nginx serves the React files and proxies `/api` requests to the FastAPI backend.

### 3. The Event-Driven Observability Stack
The newest addition to the platform closes the loop from "Polling" to "Event-Driven" resolution.
- **kube-state-metrics**: Exports Kubernetes object state as Prometheus metrics (pod restart counts, deployment status, etc.). Required for alert rules to function.
- **Prometheus**: Automatically discovers cluster nodes, pods, and API servers. Scrapes kube-state-metrics for `kube_*` metrics. Contains pre-defined alerting rules (like `PodCrashLooping`).
- **Grafana**: Auto-provisioned with Prometheus datasources and standard K8s dashboards for complete visual observability.
- **Alertmanager**: Captures firing alerts from Prometheus and routes them to the webhook listener.
- **Antigravity Listener (Webhook Integrator)**: A dedicated Python FastAPI background task that catches Prometheus alerts, extracts key metadata (`status`, `namespace`, `pod`, `alertname`), and forwards the payload into KubeOps-AI's backend at `POST /webhook/alert` with exponential backoff and retry capabilities.

---

## 🔄 The Complete Event Lifecycle

1. **Detection**: A pod enters a `CrashLoopBackOff` state.
2. **Alerting**: Prometheus evaluates its `alert.rules`, triggers the `PodCrashLooping` alert, and sends it to Alertmanager.
3. **Routing**: Alertmanager forwards the JSON payload to the **Antigravity Listener**.
4. **Trigger**: The listener filters the payload and POSTs the metadata to the FastAPI Backend.
5. **Analysis**: The Backend invokes `k8sgpt analyze` specifically targeting the affected namespace to conserve resources.
6. **Reasoning**: The Backend queries ChromaDB for past fixes, combines it with the `k8sgpt` output, and prompts the local Ollama LLM.
7. **Resolution**: The AI determines the fix. The administrator opens the React Dashboard, sees the event, reviews the AI's explanation and suggested command, and clicks **Approve & Run**.
8. **Learning**: Upon successful execution, the Backend commits the `(Issue + Fix)` vector into ChromaDB for future reference.

---

## 🐳 Deployment Strategy

The entire platform is defined via declarative Kubernetes manifests found in the `k8s/` directory. It is 100% compatible with lightweight distributions like **K3s**.

- `namespace.yaml`: Sandboxes the environment in `k8s-ai`.
- `rbac.yaml`: Dedicated `kubeops-ai-backend` ServiceAccount + least-privilege `kubeops-ai-operator` ClusterRole. Verbs aligned with the Python guardrail.
- `ollama.yaml`: Deploys the LLM runner internally (Ollama mode only; skipped for NVIDIA).
- `backend.yaml`: Deploys FastAPI and ChromaDB. Uses the `kubeops-ai-backend` ServiceAccount for in-cluster Kubernetes API access — no kubeconfig mount needed.
- `frontend.yaml`: Exposes the React app via Nginx on a NodePort.
- `kube-state-metrics.yaml`: Exports Kubernetes object metrics for Prometheus.
- `prometheus.yaml`, `alertmanager.yaml`, `grafana.yaml`: Deploys the automated monitoring and alerting stack.
- `antigravity-listener.yaml`: Deploys the bridging script that links Alertmanager directly into the KubeOps-AI workflow.

## 🛠️ Technology Stack Overview
- **Languages**: Python, JavaScript, CSS
- **Frameworks**: FastAPI, React, Vite
- **AI/ML**: Ollama (TinyLlama / Gemma 2B) or NVIDIA NIM API, ChromaDB, SentenceTransformers
- **Infrastructure**: Kubernetes (K3s / K8s / Kind / Minikube), Prometheus, Grafana, Alertmanager, kube-state-metrics
- **Security**: RBAC (ServiceAccount + ClusterRole), Python Guardrails
- **CLI Tools**: K8sGPT, Kubectl
