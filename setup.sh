#!/usr/bin/env bash
# =============================================================================
#
#   ██╗  ██╗██╗   ██╗██████╗ ███████╗ ██████╗ ██████╗ ███████╗       █████╗ ██╗
#   ██║ ██╔╝██║   ██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝      ██╔══██╗██║
#   █████╔╝ ██║   ██║██████╔╝█████╗  ██║   ██║██████╔╝███████╗      ███████║██║
#   ██╔═██╗ ██║   ██║██╔══██╗██╔══╝  ██║   ██║██╔═══╝ ╚════██║      ██╔══██║██║
#   ██║  ██╗╚██████╔╝██████╔╝███████╗╚██████╔╝██║     ███████║      ██║  ██║██║
#   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝     ╚══════╝      ╚═╝  ╚═╝╚═╝
#
#   KubeOps-AI — Interactive Cluster Setup
#   Autonomous Kubernetes AI Operations Platform
# =============================================================================
# PURPOSE:
#   One-command interactive setup that:
#     1. Runs preflight checks (kubectl, docker, curl)
#     2. Lets you choose your LLM provider (Ollama or NVIDIA NIM)
#     3. Securely stores your NVIDIA API key as a Kubernetes Secret
#     4. Deploys the full stack with progress indicators
#     5. Verifies all pods are healthy and prints access URLs
#
# USAGE:
#   chmod +x setup.sh
#   ./setup.sh [NODE_IP]
#
#   NODE_IP defaults to 127.0.0.1 when not provided.
# =============================================================================

set -euo pipefail

# ─── Defaults ─────────────────────────────────────────────────────────────────
NAMESPACE="k8s-ai"
NODE_IP="${1:-127.0.0.1}"
BACKEND_IMAGE="hardik0811/kubeops-ai-backend:latest"
FRONTEND_IMAGE="hardik0811/kubeops-ai-frontend:latest"
FRONTEND_PORT="30007"
GRAFANA_PORT="32000"
PROMETHEUS_PORT="32001"
ALERTMANAGER_PORT="32002"

# ─── Colors & Formatting ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ─── UI Helpers ───────────────────────────────────────────────────────────────

clear_screen() { printf '\033[2J\033[H'; }

print_logo() {
  echo -e "${CYAN}"
  cat << 'LOGO'
  ██╗  ██╗██╗   ██╗██████╗ ███████╗ ██████╗ ██████╗ ███████╗       █████╗ ██╗
  ██║ ██╔╝██║   ██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝      ██╔══██╗██║
  █████╔╝ ██║   ██║██████╔╝█████╗  ██║   ██║██████╔╝███████╗      ███████║██║
  ██╔═██╗ ██║   ██║██╔══██╗██╔══╝  ██║   ██║██╔═══╝ ╚════██║      ██╔══██║██║
  ██║  ██╗╚██████╔╝██████╔╝███████╗╚██████╔╝██║     ███████║      ██║  ██║██║
  ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝     ╚══════╝      ╚═╝  ╚═╝╚═╝
LOGO
  echo -e "${NC}"
  echo -e "${BOLD}${CYAN}  Autonomous Kubernetes AI Operations Platform${NC}"
  echo -e "${DIM}  Interactive Cluster Setup & Installer${NC}"
  echo ""
}

divider()  { echo -e "${CYAN}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }
banner()   { echo ""; divider; echo -e "  ${BOLD}$1${NC}"; divider; }
step()     { echo -e "\n  ${GREEN}▶${NC} ${BOLD}$1${NC}"; }
substep()  { echo -e "    ${CYAN}→${NC} $1"; }
ok()       { echo -e "    ${GREEN}✔${NC}  $1"; }
info()     { echo -e "    ${YELLOW}ℹ${NC}  $1"; }
warn()     { echo -e "    ${YELLOW}⚠${NC}  $1"; }
error()    { echo -e "    ${RED}✖${NC}  $1" >&2; }
prompt()   { echo -e -n "  ${MAGENTA}?${NC}  $1 "; }

# ─── Wait Helpers ─────────────────────────────────────────────────────────────

wait_for_pod() {
  local label="$1"
  local timeout="${2:-180}"
  substep "Waiting for pod ${BOLD}${label}${NC} to be Ready (timeout: ${timeout}s)…"
  if kubectl wait pod \
      -n "${NAMESPACE}" \
      -l "${label}" \
      --for=condition=Ready \
      --timeout="${timeout}s" > /dev/null 2>&1; then
    ok "Pod ${label} is Ready"
  else
    warn "Pod ${label} did not become Ready within ${timeout}s — check: kubectl get pods -n ${NAMESPACE}"
  fi
}

spinner_wait() {
  local msg="$1"
  local seconds="${2:-5}"
  local spinchars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
  local i=0
  local end=$(( $(date +%s) + seconds ))
  while [ "$(date +%s)" -lt "$end" ]; do
    local char="${spinchars:$(( i % ${#spinchars} )):1}"
    printf "\r    ${CYAN}%s${NC}  %s" "$char" "$msg"
    sleep 0.1
    (( i++ )) || true
  done
  printf "\r    ${GREEN}✔${NC}  %s\n" "$msg"
}

# =============================================================================
# PHASE 0 — WELCOME & PREFLIGHT
# =============================================================================

clear_screen
print_logo

echo -e "  ${DIM}Node IP: ${NODE_IP}${NC}"
echo -e "  ${DIM}Namespace: ${NAMESPACE}${NC}"
echo ""

banner "PHASE 0 — Preflight Checks"

step "Checking required tools…"

check_tool() {
  if command -v "$1" &>/dev/null; then
    ok "$1 found  $(command -v "$1")"
  else
    error "$1 is NOT installed or not in PATH"
    echo ""
    echo -e "  ${RED}Please install ${BOLD}$1${NC}${RED} before running this script.${NC}"
    exit 1
  fi
}

check_tool kubectl
check_tool docker
check_tool curl

step "Verifying kubectl can reach the cluster…"
if kubectl cluster-info &>/dev/null; then
  ok "kubectl is connected to a cluster"
  substep "$(kubectl cluster-info 2>&1 | head -1)"
else
  error "kubectl cannot reach a cluster. Check your kubeconfig."
  exit 1
fi

step "Checking for existing ${NAMESPACE} namespace…"
if kubectl get namespace "${NAMESPACE}" &>/dev/null; then
  info "Namespace ${NAMESPACE} already exists — continuing (idempotent)"
else
  info "Namespace ${NAMESPACE} will be created"
fi

# =============================================================================
# PHASE 1 — LLM PROVIDER SELECTION
# =============================================================================

banner "PHASE 1 — Choose Your LLM Provider"

echo -e "  KubeOps-AI supports two AI backends. Choose one:"
echo ""
echo -e "  ${BOLD}${GREEN}[1]${NC} ${BOLD}Local Ollama${NC} ${DIM}(Free · Fully Private · Runs inside your cluster · CPU-compatible)${NC}"
echo -e "      Deploys a TinyLlama model inside the cluster."
echo -e "      No internet access needed after the initial image pull."
echo -e "      Recommended for: demos, air-gapped clusters, cost-sensitive setups."
echo ""
echo -e "  ${BOLD}${CYAN}[2]${NC} ${BOLD}NVIDIA NIM API${NC} ${DIM}(Cloud · Fast · Requires NVIDIA API Key)${NC}"
echo -e "      Uses NVIDIA's hosted NIM inference endpoint."
echo -e "      Model: nvidia/llama-3.3-nemotron-super-49b-v1 (overridable)"
echo -e "      Recommended for: production demos, best response quality."
echo ""

LLM_PROVIDER=""
while true; do
  prompt "Enter your choice [1/2]:"
  read -r choice
  case "${choice}" in
    1)
      LLM_PROVIDER="ollama"
      echo ""
      ok "LLM Provider set to: ${BOLD}Local Ollama${NC}"
      break
      ;;
    2)
      LLM_PROVIDER="nvidia"
      echo ""
      ok "LLM Provider set to: ${BOLD}NVIDIA NIM API${NC}"
      break
      ;;
    *)
      warn "Invalid choice. Please enter 1 or 2."
      ;;
  esac
done

# ─── NVIDIA API Key Collection ────────────────────────────────────────────────
NVIDIA_API_KEY=""
NVIDIA_MODEL="nvidia/llama-3.3-nemotron-super-49b-v1"

if [ "${LLM_PROVIDER}" = "nvidia" ]; then
  echo ""
  banner "PHASE 1b — NVIDIA API Key Setup"

  echo -e "  Your API key will be stored as a ${BOLD}Kubernetes Secret${NC} in the ${BOLD}${NAMESPACE}${NC} namespace."
  echo -e "  It is ${BOLD}never${NC} written to disk or any config file."
  echo ""
  echo -e "  ${DIM}Get your key at: https://build.nvidia.com/  (free tier available)${NC}"
  echo ""

  while true; do
    prompt "Paste your NVIDIA API key (input is hidden):"
    read -rs NVIDIA_API_KEY
    echo ""
    if [[ "${NVIDIA_API_KEY}" =~ ^nvapi- ]]; then
      ok "API key format looks valid (starts with nvapi-)"
      break
    elif [ -z "${NVIDIA_API_KEY}" ]; then
      warn "API key cannot be empty."
    else
      warn "Key does not start with 'nvapi-'. Are you sure it's correct?"
      prompt "Continue anyway? [y/N]:"
      read -r confirm
      if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        ok "Continuing with provided key."
        break
      fi
    fi
  done

  echo ""
  prompt "NVIDIA model to use [press ENTER for default: ${NVIDIA_MODEL}]:"
  read -r custom_model
  if [ -n "${custom_model}" ]; then
    NVIDIA_MODEL="${custom_model}"
    ok "Using custom model: ${NVIDIA_MODEL}"
  else
    ok "Using default model: ${NVIDIA_MODEL}"
  fi
fi

# =============================================================================
# PHASE 2 — CONTAINER IMAGE SELECTION
# =============================================================================

banner "PHASE 2 — Container Image Registry"

echo -e "  ${BOLD}Default images:${NC}"
echo -e "    Backend:   ${DIM}${BACKEND_IMAGE}${NC}"
echo -e "    Frontend:  ${DIM}${FRONTEND_IMAGE}${NC}"
echo ""
prompt "Use default images? [Y/n]:"
read -r use_defaults
if [[ "${use_defaults}" =~ ^[Nn]$ ]]; then
  prompt "Backend image (e.g. myrepo/kubeops-backend:v1):"
  read -r BACKEND_IMAGE
  prompt "Frontend image (e.g. myrepo/kubeops-frontend:v1):"
  read -r FRONTEND_IMAGE
  ok "Using custom images:"
  info "Backend:  ${BACKEND_IMAGE}"
  info "Frontend: ${FRONTEND_IMAGE}"
else
  ok "Using default images"
fi

# =============================================================================
# PHASE 3 — KUBERNETES SECRETS
# =============================================================================

if [ "${LLM_PROVIDER}" = "nvidia" ]; then
  banner "PHASE 3 — Creating Kubernetes Secrets"

  step "Creating namespace ${NAMESPACE} (idempotent)…"
  kubectl apply -f k8s/namespace.yaml

  step "Storing NVIDIA API key as Kubernetes Secret…"
  # Delete existing secret if present to allow key rotation
  kubectl delete secret nvidia-api-key -n "${NAMESPACE}" --ignore-not-found > /dev/null 2>&1

  kubectl create secret generic nvidia-api-key \
    --namespace "${NAMESPACE}" \
    --from-literal=api-key="${NVIDIA_API_KEY}"

  ok "Secret 'nvidia-api-key' created in namespace '${NAMESPACE}'"
  info "The key is base64-encoded in etcd. Use encryption-at-rest for production clusters."

  # Wipe the key from this shell's memory
  NVIDIA_API_KEY=""
else
  step "No secrets required for Ollama mode — skipping"
fi

# =============================================================================
# PHASE 4 — PATCH MANIFESTS FOR PROVIDER
# =============================================================================

banner "PHASE 4 — Configuring Manifests for ${LLM_PROVIDER^^} Mode"

# We patch backend.yaml LLM_PROVIDER value in-place using sed.
# This avoids needing kustomize or helm for this simple substitution.
BACKEND_MANIFEST="k8s/backend.yaml"

step "Patching ${BACKEND_MANIFEST} for LLM_PROVIDER=${LLM_PROVIDER}…"
# Patch LLM_PROVIDER value
sed -i.bak "s|value: \"ollama\".*# <- overridden to \"nvidia\" by setup.sh for NVIDIA path|value: \"${LLM_PROVIDER}\"              # <- overridden to \"nvidia\" by setup.sh for NVIDIA path|" "${BACKEND_MANIFEST}" 2>/dev/null || true

if [ "${LLM_PROVIDER}" = "nvidia" ]; then
  # Patch NVIDIA_MODEL value
  sed -i.bak "s|value: \"nvidia/llama-3.3-nemotron-super-49b-v1\"|value: \"${NVIDIA_MODEL}\"|" "${BACKEND_MANIFEST}" 2>/dev/null || true
  ok "Manifest patched for NVIDIA NIM (model: ${NVIDIA_MODEL})"
else
  ok "Manifest confirmed for Ollama mode"
fi
rm -f "${BACKEND_MANIFEST}.bak" 2>/dev/null || true

# =============================================================================
# PHASE 5 — DEPLOY THE FULL STACK
# =============================================================================

banner "PHASE 5 — Deploying KubeOps-AI to Cluster"

step "Creating namespace ${NAMESPACE}…"
kubectl apply -f k8s/namespace.yaml
ok "Namespace ready"

if [ "${LLM_PROVIDER}" = "ollama" ]; then
  step "Deploying Ollama local LLM runner…"
  kubectl apply -f k8s/ollama.yaml
  ok "Ollama deployment applied"
else
  step "NVIDIA mode selected — skipping Ollama deployment (saves ~2GB cluster RAM)"
  # Remove any old Ollama deployment if switching providers
  kubectl delete deployment ollama -n "${NAMESPACE}" --ignore-not-found > /dev/null 2>&1 || true
  kubectl delete service ollama -n "${NAMESPACE}" --ignore-not-found > /dev/null 2>&1 || true
  ok "Ollama resources cleaned up (if any)"
fi

step "Deploying FastAPI Backend (Intelligence Core)…"
kubectl apply -f k8s/backend.yaml
ok "Backend deployment applied"

step "Deploying React + Nginx Frontend (Operations Dashboard)…"
kubectl apply -f k8s/frontend.yaml
ok "Frontend deployment applied"

step "Applying ClusterRoleBinding for kubectl cluster access…"
kubectl apply -f k8s/clusterbinding.yaml
ok "ClusterRoleBinding applied"

# =============================================================================
# PHASE 5b — OBSERVABILITY STACK
# =============================================================================

banner "PHASE 5b — Deploying Observability Stack"

echo ""
prompt "Deploy Prometheus + Grafana + Alertmanager? [Y/n]:"
read -r deploy_obs
if [[ ! "${deploy_obs}" =~ ^[Nn]$ ]]; then

  step "Deploying Prometheus (metrics + alert rules)…"
  kubectl apply -f k8s/prometheus.yaml
  ok "Prometheus applied"

  step "Deploying Alertmanager (alert routing)…"
  kubectl apply -f k8s/alertmanager.yaml
  ok "Alertmanager applied"

  step "Deploying Grafana (pre-provisioned dashboards)…"
  kubectl apply -f k8s/grafana.yaml
  ok "Grafana applied"

  step "Deploying Antigravity Listener (webhook bridge)…"
  kubectl apply -f k8s/antigravity-listener.yaml
  ok "Antigravity Listener applied"

  OBSERVABILITY_DEPLOYED=true
else
  info "Skipping observability stack"
  OBSERVABILITY_DEPLOYED=false
fi

# =============================================================================
# PHASE 6 — POST-DEPLOY SETUP
# =============================================================================

banner "PHASE 6 — Post-Deploy Configuration"

if [ "${LLM_PROVIDER}" = "ollama" ]; then
  step "Waiting for Ollama pod to be ready…"
  wait_for_pod "app=ollama" 180

  step "Pulling TinyLlama model into the Ollama pod (may take 2-5 minutes)…"
  substep "Pulling tinyllama:latest…"
  kubectl exec -n "${NAMESPACE}" deploy/ollama -- ollama pull tinyllama:latest
  ok "TinyLlama model pulled successfully"
fi

step "Waiting for Backend pod to be ready…"
wait_for_pod "app=backend" 180

step "Waiting for Frontend pod to be ready…"
wait_for_pod "app=frontend" 120

step "Running health check on backend…"
spinner_wait "Allowing backend to initialize…" 10

# Try to health check via port-forward
kubectl port-forward -n "${NAMESPACE}" svc/backend 19999:8000 &
PF_PID=$!
sleep 4

HEALTH=$(curl -s --max-time 5 http://localhost:19999/health 2>/dev/null || echo "{}")
kill "${PF_PID}" 2>/dev/null || true

if echo "${HEALTH}" | grep -q '"ok"'; then
  ok "Backend health check passed ✅"
else
  warn "Health check returned unexpected response: ${HEALTH}"
  info "Backend may still be initializing. Check: kubectl logs -n ${NAMESPACE} deploy/backend"
fi

# =============================================================================
# PHASE 7 — SUMMARY
# =============================================================================

banner "Setup Complete! 🎉"

echo ""
echo -e "  ${BOLD}${GREEN}KubeOps-AI is up and running!${NC}"
echo ""

# LLM Provider badge
if [ "${LLM_PROVIDER}" = "nvidia" ]; then
  echo -e "  ${BOLD}LLM Engine:${NC}   ${CYAN}NVIDIA NIM${NC} (${NVIDIA_MODEL})"
else
  echo -e "  ${BOLD}LLM Engine:${NC}   ${GREEN}Local Ollama${NC} (tinyllama:latest)"
fi

echo ""
echo -e "  ${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "  ${BOLD}║                  Access Points                               ║${NC}"
echo -e "  ${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "  ${BOLD}║${NC}  ${BOLD}Dashboard${NC}      http://${NODE_IP}:${FRONTEND_PORT}                           ${BOLD}║${NC}"

if [ "${OBSERVABILITY_DEPLOYED}" = "true" ]; then
echo -e "  ${BOLD}║${NC}  ${BOLD}Grafana${NC}        http://${NODE_IP}:${GRAFANA_PORT}  ${DIM}(admin / admin)${NC}          ${BOLD}║${NC}"
echo -e "  ${BOLD}║${NC}  ${BOLD}Prometheus${NC}     http://${NODE_IP}:${PROMETHEUS_PORT}                          ${BOLD}║${NC}"
echo -e "  ${BOLD}║${NC}  ${BOLD}Alertmanager${NC}   http://${NODE_IP}:${ALERTMANAGER_PORT}                          ${BOLD}║${NC}"
fi

echo -e "  ${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "  ${BOLD}Useful commands:${NC}"
echo -e "    ${DIM}kubectl get pods -n ${NAMESPACE}${NC}                     # Check pod status"
echo -e "    ${DIM}kubectl logs -n ${NAMESPACE} deploy/backend -f${NC}         # Backend logs"
echo -e "    ${DIM}kubectl logs -n ${NAMESPACE} deploy/frontend -f${NC}        # Frontend logs"
echo ""

if [ "${LLM_PROVIDER}" = "ollama" ]; then
  echo -e "  ${BOLD}To pull a different model:${NC}"
  echo -e "    ${DIM}kubectl exec -n ${NAMESPACE} deploy/ollama -- ollama pull gemma:2b${NC}"
  echo ""
fi

echo -e "  ${BOLD}To run the feature demo:${NC}"
echo -e "    ${DIM}chmod +x demo_setup.sh && ./demo_setup.sh ${NODE_IP} --provider ${LLM_PROVIDER}${NC}"
echo ""

echo -e "  ${DIM}For full documentation, see SETUP.md and ARCHITECTURE.md${NC}"
echo ""
divider
echo ""
