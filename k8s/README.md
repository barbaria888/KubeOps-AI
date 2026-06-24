# 🐳 Kubernetes Deployment Manifests

This directory contains the infrastructure-as-code required to run the KubeOps-AI platform entirely inside your own cluster.

## 📄 Manifest Breakdown

| Manifest | Purpose |
|---|---|
| `namespace.yaml` | Creates the `k8s-ai` isolated namespace for all components |
| `rbac.yaml` | **ServiceAccount** (`kubeops-ai-backend`) + **ClusterRole** (`kubeops-ai-operator`) + **ClusterRoleBinding**. Least-privilege permissions aligned with the Python guardrail |
| `backend.yaml` | Deploys the FastAPI intelligence core. Uses the `kubeops-ai-backend` ServiceAccount for in-cluster Kubernetes API access |
| `frontend.yaml` | Deploys the Nginx-served React App and exposes it as a NodePort on port `30007` |
| `ollama.yaml` | *(Ollama mode only)* Deploys the local LLM runner. Skipped in NVIDIA mode |
| `nvidia-secret.yaml` | Template for the NVIDIA API key Kubernetes Secret. Populated by `setup.sh` at runtime |
| `kube-state-metrics.yaml` | Exports Kubernetes object state as Prometheus metrics (`kube_*`). Required for alert rules to function |
| `prometheus.yaml` | Prometheus server with scrape configs and alert rules (e.g., `PodCrashLooping`). Exposed on NodePort `32001` |
| `alertmanager.yaml` | Routes firing alerts to the Antigravity Listener webhook. Exposed on NodePort `32002` |
| `grafana.yaml` | Pre-provisioned Grafana dashboards. Exposed on NodePort `32000` (credentials: `admin` / `admin`) |
| `antigravity-listener.yaml` | Webhook bridge: catches Alertmanager webhooks and triggers the backend `POST /webhook/alert` endpoint |
| `clusterbinding.yaml` | **DEPRECATED** — replaced by `rbac.yaml`. Kept as a placeholder with a deprecation notice |

## 🛡️ Security Model

The backend pod runs with a **dedicated ServiceAccount** (`kubeops-ai-backend`) bound to a **least-privilege ClusterRole** (`kubeops-ai-operator`). This provides defense-in-depth alongside the Python guardrail:

- **RBAC level**: Only `get`, `list`, `watch`, `patch`, `update` verbs are granted. `delete`, `create` (except `pods/portforward`), and `exec` are **not** available.
- **Guardrail level**: The Python filter blocks `delete`, `rm`, `wipe`, `format`, and shell injection patterns before any command reaches `kubectl`.

No `kubeconfig` file mount is needed — the backend uses the ServiceAccount token auto-mounted by Kubernetes at `/var/run/secrets/kubernetes.io/serviceaccount/`.

## 🚀 How to Deploy

Assuming you have built the images (see the root `README.md`):

```bash
# 1. Apply the isolating namespace
kubectl apply -f namespace.yaml

# 2. Apply RBAC (ServiceAccount + ClusterRole)
kubectl apply -f rbac.yaml

# 3. Deploy your LLM (Ollama mode only — skip for NVIDIA)
kubectl apply -f ollama.yaml
kubectl wait pod -n k8s-ai -l app=ollama --for=condition=Ready --timeout=180s
kubectl exec -n k8s-ai deploy/ollama -- ollama pull tinyllama:latest

# 4. Deploy the Intelligence Core
kubectl apply -f backend.yaml

# 5. Deploy the UI
kubectl apply -f frontend.yaml
kubectl get pods -n k8s-ai
```

You can then view your frontend at `http://<Node-IP>:30007`.

## 📈 Observability Stack

The `k8s/` directory includes a fully-integrated event-driven monitoring stack, exposed via NodePorts (no manual `kubectl port-forward` required for demo verification):

- **`kube-state-metrics.yaml`**: Exports Kubernetes object state (pod restarts, deployment status, etc.) as Prometheus metrics. **This is required for alert rules to work.**
- **`prometheus.yaml`**: Scrapes kube-state-metrics and evaluates `alert.rules` (e.g., `PodCrashLooping`). Exposed as a NodePort service on port `32001`.
- **`alertmanager.yaml`**: Routes firing alerts to the KubeOps-AI webhook listener. Exposed as a NodePort service on port `32002`.
- **`grafana.yaml`**: Visualizes cluster health with pre-provisioned dashboards. Exposed as a NodePort service on port `32000` (Default credentials: `admin` / `admin`).
- **`antigravity-listener.yaml`**: The bridge that catches Alertmanager webhooks and triggers the AI backend `POST /webhook/alert` endpoint.

Deploy the observability suite:
```bash
kubectl apply -f kube-state-metrics.yaml
kubectl apply -f prometheus.yaml
kubectl apply -f alertmanager.yaml
kubectl apply -f grafana.yaml
kubectl apply -f antigravity-listener.yaml
```
