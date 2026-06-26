# KubeOps-AI — Setup & Installation Guide

> A complete guide to getting KubeOps-AI running in your Kubernetes cluster, covering both **Local Ollama** and **NVIDIA NIM** LLM backends.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Interactive Setup)](#quick-start)
3. [Path A — Local Ollama (Free & Private)](#path-a--local-ollama)
4. [Path B — NVIDIA NIM API (Cloud & Fast)](#path-b--nvidia-nim-api)
5. [Accessing the Platform](#accessing-the-platform)
6. [Running the Feature Demo](#running-the-feature-demo)
7. [Switching LLM Providers](#switching-llm-providers)
8. [Rebuilding Container Images](#rebuilding-container-images)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before running the setup script, ensure you have:

| Tool | Minimum Version | Purpose |
|---|---|---|
| `kubectl` | 1.24+ | Kubernetes cluster management |
| `docker` | 20.10+ | Container image builds (only if rebuilding) |
| `curl` | Any | Health checks and API tests |
| `jq` | Any | Optional — pretty-prints JSON in demo |

Your `kubectl` must be configured to point at a running cluster:

```bash
kubectl cluster-info   # Should return the control plane URL
```

> [!NOTE]
> **Supported cluster types**: K3s, K8s, Kind, Minikube. The backend uses an in-cluster ServiceAccount for Kubernetes API access — no kubeconfig mount or distribution-specific configuration is needed.

---

## Quick Start

The recommended way to deploy KubeOps-AI is the interactive `setup.sh` script. It handles everything automatically:

```bash
git clone https://github.com/barbaria888/KubeOps-AI.git
cd KubeOps-AI

chmod +x setup.sh
./setup.sh <YOUR_NODE_IP>
```

The script will:
1. ✅ Run preflight checks (kubectl, docker, curl, cluster connectivity)
2. 🤖 Ask you to choose an LLM provider (Ollama or NVIDIA NIM)
3. 🔑 Securely collect and store your NVIDIA API key (if NVIDIA chosen)
4. 🐳 Deploy all Kubernetes manifests with progress indicators
5. ⏳ Wait for pods to become ready
6. 🔍 Run a backend health check
7. 📋 Print all access URLs

---

## Path A — Local Ollama

**Best for:** Free usage, demos, air-gapped clusters, CPU-only nodes, privacy.

### How it works

When you select **Local Ollama** during `setup.sh`, the script:
- Deploys `k8s/ollama.yaml` — runs the Ollama LLM server inside the cluster
- Pulls `tinyllama:latest` into the Ollama pod automatically
- Configures `LLM_PROVIDER=ollama` in the backend deployment

### Manual steps (without setup.sh)

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Apply RBAC (ServiceAccount + least-privilege ClusterRole)
kubectl apply -f k8s/rbac.yaml

# 3. Deploy Ollama (local LLM runner)
kubectl apply -f k8s/ollama.yaml

# 4. Wait for Ollama to be ready
kubectl wait pod -n k8s-ai -l app=ollama --for=condition=Ready --timeout=180s

# 5. Pull the TinyLlama model
kubectl exec -n k8s-ai deploy/ollama -- ollama pull tinyllama:latest

# 6. Deploy backend and frontend
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml

# 7. Deploy kube-state-metrics (required for Prometheus alert rules)
kubectl apply -f k8s/kube-state-metrics.yaml
```

### Switching to a better model (optional)

TinyLlama is fast but basic. For better reasoning quality:

```bash
# Pull Gemma 2B (requires ~4 GB cluster RAM)
kubectl exec -n k8s-ai deploy/ollama -- ollama pull gemma:2b

# Update the backend to use it
kubectl set env deployment/backend -n k8s-ai OLLAMA_MODEL=gemma:2b

```

---

## Path B — NVIDIA NIM API

**Best for:** Best model quality, fast inference, production demos, access to 70B+ parameter models.

### Step 1 — Get an NVIDIA API Key

1. Go to [https://build.nvidia.com/](https://build.nvidia.com/)
2. Create a free account (or log in)
3. Navigate to **API Keys** in your account settings
4. Generate a new key — it starts with `nvapi-`

> [!IMPORTANT]
> Keep your API key secret. It is never written to any file by `setup.sh`. It is stored only as a Kubernetes Secret (`nvidia-api-key`) in your cluster's etcd.

### Step 2 — Run setup.sh

```bash
chmod +x setup.sh
./setup.sh <YOUR_NODE_IP>
```

When prompted, select **[2] NVIDIA NIM API** and paste your key. The script handles everything else.

### Manual steps (without setup.sh)

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Apply RBAC (ServiceAccount + least-privilege ClusterRole)
kubectl apply -f k8s/rbac.yaml

# 3. Create the Kubernetes Secret for your API key
kubectl create secret generic nvidia-api-key \
  --namespace k8s-ai \
  --from-literal=api-key="nvapi-xxxx..."

# 4. Patch backend.yaml to set LLM_PROVIDER=nvidia
# Edit k8s/backend.yaml and change:
#   value: "ollama"   →   value: "nvidia"
# under the LLM_PROVIDER env entry.
# Then apply:
kubectl apply -f k8s/backend.yaml

# 5. Deploy frontend (Ollama NOT needed)
kubectl apply -f k8s/frontend.yaml

# 6. Deploy kube-state-metrics (required for Prometheus alert rules)
kubectl apply -f k8s/kube-state-metrics.yaml
```

### Available NVIDIA NIM Models

All models listed at [https://build.nvidia.com/explore/reasoning](https://build.nvidia.com/explore/reasoning) are supported. Change the default by setting `NVIDIA_MODEL`:

```bash
kubectl set env deployment/backend -n k8s-ai \
  NVIDIA_MODEL=nvidia/llama-3.1-nemotron-70b-instruct
```

| Model | Speed | Quality | Notes |
|---|---|---|---|
| `nvidia/llama-3.3-nemotron-super-49b-v1` | Fast | ⭐⭐⭐⭐ | **Default** |
| `nvidia/llama-3.1-nemotron-70b-instruct` | Medium | ⭐⭐⭐⭐⭐ | Best reasoning |
| `z-ai/glm-5.1` | Fast | ⭐⭐⭐⭐ | Good alternative |
| `meta/llama-3.1-8b-instruct` | Very Fast | ⭐⭐⭐ | Free tier friendly |

---

## Accessing the Platform

After a successful setup, all services are exposed via NodePorts:

| Service | URL | Credentials |
|---|---|---|
| **KubeOps-AI Dashboard** | `http://<NODE_IP>:30007` | None |
| **Grafana** | `http://<NODE_IP>:32000` | `admin` / `admin` |
| **Prometheus** | `http://<NODE_IP>:32001` | None |
| **Alertmanager** | `http://<NODE_IP>:32002` | None |

Find your node IP:

```bash
kubectl get nodes -o wide   # Look at EXTERNAL-IP or INTERNAL-IP
```

---

## Running the Feature Demo

Once the platform is deployed, run the four-scenario demo:

```bash
chmod +x demo_setup.sh

# Ollama mode:
./demo_setup.sh <NODE_IP> --provider ollama

# NVIDIA mode:
./demo_setup.sh <NODE_IP> --provider nvidia

# Auto-detect from running cluster:
./demo_setup.sh <NODE_IP>
```

The demo walks through all four feature scenarios interactively, pausing between each one so you can verify the results in the dashboard.

---

## Switching LLM Providers

You can switch providers at any time without rebuilding images.

### Ollama → NVIDIA

```bash
# 1. Create the NVIDIA secret
kubectl create secret generic nvidia-api-key \
  --namespace k8s-ai \
  --from-literal=api-key="nvapi-xxxx..."

# 2. Switch provider env var
kubectl set env deployment/backend -n k8s-ai LLM_PROVIDER=nvidia

# 3. Optionally scale down Ollama to free resources
kubectl scale deployment/ollama -n k8s-ai --replicas=0
```

### NVIDIA → Ollama

```bash
# 1. Ensure Ollama is running
kubectl scale deployment/ollama -n k8s-ai --replicas=1
kubectl wait pod -n k8s-ai -l app=ollama --for=condition=Ready --timeout=180s
kubectl exec -n k8s-ai deploy/ollama -- ollama pull tinyllama:latest

# 2. Switch provider env var
kubectl set env deployment/backend -n k8s-ai LLM_PROVIDER=ollama
```

> [!NOTE]
> After switching, the backend pod automatically restarts and connects to the new provider. Watch progress with:
> ```bash
> kubectl rollout status deployment/backend -n k8s-ai
> ```

---

## Rebuilding Container Images

If you modify backend or frontend source code, rebuild and push:

```bash
# Backend (after changes to app/ or requirements.txt)
docker build -t hardik0811/kubeops-ai-backend:latest .
docker push hardik0811/kubeops-ai-backend:latest
kubectl rollout restart deployment/backend -n k8s-ai

# Frontend (after changes to frontend/src/)
cd frontend
npm run build
docker build -t hardik0811/kubeops-ai-frontend:latest .
docker push hardik0811/kubeops-ai-frontend:latest
kubectl rollout restart deployment/frontend -n k8s-ai
```

---

## Troubleshooting

### Pods stuck in `Pending`

```bash
kubectl describe pod <pod-name> -n k8s-ai
# Look for: resource constraints, node selector, PVC binding issues
```

### Backend crashloops

```bash
kubectl logs -n k8s-ai deploy/backend --previous
# Common causes:
#   - NVIDIA_API_KEY secret missing (if NVIDIA mode)
#   - RBAC ServiceAccount not applied (run: kubectl apply -f k8s/rbac.yaml)
#   - ChromaDB initialization failure
```

### NVIDIA API errors

```bash
kubectl logs -n k8s-ai deploy/backend | grep -i nvidia
# Check for: "NVIDIA_API_KEY is not set" or authentication errors
# Verify the secret exists:
kubectl get secret nvidia-api-key -n k8s-ai
```

### Dashboard shows "Cluster analysis warming up"

This means `KUBEOPS_LAZY_ANALYSIS=true`. Check:

```bash
kubectl get deployment backend -n k8s-ai \
  -o jsonpath='{.spec.template.spec.containers[0].env}' | python3 -m json.tool
```

Set to `false` if it should be running full analysis:

```bash
kubectl set env deployment/backend -n k8s-ai KUBEOPS_LAZY_ANALYSIS=false
```

### Ollama model pull fails

```bash
# Check Ollama pod status
kubectl get pod -n k8s-ai -l app=ollama
# Check logs
kubectl logs -n k8s-ai deploy/ollama
# Retry pull manually
kubectl exec -n k8s-ai deploy/ollama -- ollama pull tinyllama:latest
```

---

## Environment Variable Reference

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `"ollama"` or `"nvidia"` — selects the LLM backend |
| `NVIDIA_API_KEY` | _(from Secret)_ | NVIDIA NIM API key. Set via Kubernetes Secret. |
| `NVIDIA_MODEL` | `nvidia/llama-3.3-nemotron-super-49b-v1` | NVIDIA NIM model identifier |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA NIM API base URL |
| `NVIDIA_MAX_TOKENS` | `512` | Max tokens per NVIDIA response |
| `OLLAMA_URL` | `http://ollama:11434/api/generate` | Ollama API endpoint |
| `OLLAMA_MODEL` | `tinyllama:latest` | Ollama model to use |
| `OLLAMA_TIMEOUT_SECONDS` | `60` | Ollama request timeout |
| `KUBEOPS_ENABLE_FULL_AI` | `true` | Enable full LLM reasoning pipeline |
| `KUBEOPS_ENABLE_FULL_OLLAMA` | _(legacy alias)_ | Backward-compatible alias for `KUBEOPS_ENABLE_FULL_AI` |
| `KUBEOPS_LAZY_ANALYSIS` | `false` | Return immediately without analysis |
| `KUBEOPS_MAX_ANALYZED_ISSUES` | `1` | Max issues to analyze per request |
| `KUBEOPS_ENABLE_VECTOR_STORE` | `true` | Enable ChromaDB incident memory |

---

## RBAC Reference

The backend uses a dedicated ServiceAccount (`kubeops-ai-backend`) with a least-privilege ClusterRole (`kubeops-ai-operator`). The allowed Kubernetes API verbs are aligned with the Python guardrail:

| Guardrail Verb | Kubernetes RBAC Mapping |
|---|---|
| `get`, `describe` | `get`, `list`, `watch` on core, apps, batch, networking resources |
| `logs` | `get` on `pods/log` |
| `set image` | `patch`, `update` on `deployments`, `statefulsets`, `daemonsets` |
| `rollout` | `patch`, `update` on `deployments` |
| `scale` | `patch`, `update` on `deployments/scale`, `replicasets/scale`, `statefulsets/scale` |
| `annotate`, `label` | `patch`, `update` on `pods`, `nodes`, `services`, `namespaces` |
| `cordon`, `uncordon` | `patch`, `update` on `nodes` |
| `top` | `get`, `list` on `metrics.k8s.io` resources |
| `port-forward` | `create` on `pods/portforward` |

**Blocked** at both RBAC and guardrail level: `delete`, `create`, `exec`, `apply`, `edit`.
