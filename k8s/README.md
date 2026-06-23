# 🐳 Kubernetes Deployment Manifests

This directory contains the infrastructure-as-code required to run the K8s Agentic AI entirely inside your own cluster.

## 📄 Manifest Breakdown

1. **`namespace.yaml`**: Creates the `k8s-ai` isolated namespace for all components.
2. **`ollama.yaml`**: Deploys the local LLM runner as a Stateful deployment to ensure the AI remains completely private and entirely on-premise without reaching out to external APIs.
3. **`backend.yaml`**: Deploys the FastAPI intelligence core. 
    - **Important Details**: 
      - Maps the host system's `kubeconfig` (`/etc/rancher/k3s/k3s.yaml`) straight into the pod so the backend has native permission to run `kubectl` against its parent cluster (tuned for K3s).
      - Configures `KUBEOPS_ENABLE_VECTOR_STORE` to `"true"` by default to activate the ChromaDB Incident Memory backend for storing and retrieving past resolutions.
4. **`frontend.yaml`**: Deploys the Nginx-served React App and exposes it as a `NodePort` on port `30007`.

## 🚀 How to Deploy

Assuming you have built the images (see the root `README.md`):

```bash
# 1. Apply the isolating namespace first
kubectl apply -f namespace.yaml
kubectl config set-context --current --namespace=k8s-ai

# 2. Deploy your LLM 
kubectl apply -f ollama.yaml

# 3. Deploy the intelligence Core
kubectl apply -f backend.yaml

# 4. Deploy the UI
kubectl apply -f frontend.yaml
kubectl get pods
```

Once Ollama is running, remember to pull your model into the pod:
```bash
kubectl exec -n k8s-ai deploy/ollama -- ollama pull gemma:2b
```

You can then view your frontend at `http://<Node-IP>:30007`.

## 📈 Observability Stack

The `k8s/` directory includes a fully-integrated event-driven monitoring stack, exposed via NodePorts (no manual `kubectl port-forward` required for demo verification):

- **`prometheus.yaml`**: Discovers cluster faults and triggers `alert.rules`. Exposed as a `NodePort` service on port `32001`.
- **`alertmanager.yaml`**: Routes firing alerts to the KubeOps-AI webhook listener. Exposed as a `NodePort` service on port `32002`.
- **`grafana.yaml`**: Visualizes cluster health with pre-provisioned dashboards. Exposed as a `NodePort` service on port `32000` (Default credentials: `admin` / `admin`).
- **`antigravity-listener.yaml`**: The bridge that catches Alertmanager webhooks and triggers the AI backend `POST /webhook/alert` endpoint.

Deploy the observability suite:
```bash
kubectl apply -f prometheus.yaml
kubectl apply -f alertmanager.yaml
kubectl apply -f grafana.yaml
kubectl apply -f antigravity-listener.yaml
```
