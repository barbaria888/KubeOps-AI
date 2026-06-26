#!/usr/bin/env bash
# =============================================================================
# KubeOps-AI — Full Platform Feature Demo Script
# =============================================================================
# PURPOSE:
#   Demonstrates four core platform scenarios:
#     1. AI Pipeline + Approve & Run (ImagePullBackOff)
#     2. Guardrail Protection (blocked unsafe commands)
#     3. Incident Vector Memory (ChromaDB past-fix recall)
#     4. Event-Driven Alert Loop (Prometheus → Webhook → Dashboard)
#
# PREREQUISITES:
#   • Run setup.sh first to deploy the full stack
#   • kubectl configured against a running K3s / K8s cluster
#   • curl  (for sending webhook test payloads)
#   • jq    (for parsing JSON responses)  — optional
#
# RUN:
#   chmod +x demo_setup.sh
#   ./demo_setup.sh [NODE_IP] [--provider ollama|nvidia]
#
#   NODE_IP defaults to 127.0.0.1 when not supplied.
#   --provider defaults to auto-detecting from the running backend pod.
# =============================================================================

set -euo pipefail

NAMESPACE="k8s-ai"
NODE_IP="${1:-127.0.0.1}"
FRONTEND_PORT="30007"
GRAFANA_PORT="32000"
PROMETHEUS_PORT="32001"
ALERTMANAGER_PORT="32002"

# ─── Parse --provider flag ────────────────────────────────────────────────────
LLM_PROVIDER=""
for arg in "$@"; do
  case "${arg}" in
    --provider=*) LLM_PROVIDER="${arg#*=}" ;;
    --provider)   shift; LLM_PROVIDER="${1:-}" ;;
  esac
done

# Auto-detect provider from running backend if not supplied
if [ -z "${LLM_PROVIDER}" ]; then
  LLM_PROVIDER=$(kubectl get deployment backend -n "${NAMESPACE}" \
    -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="LLM_PROVIDER")].value}' \
    2>/dev/null || echo "ollama")
  [ -z "${LLM_PROVIDER}" ] && LLM_PROVIDER="ollama"
fi

# ─── Colors ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

banner() {
  echo ""
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  $1${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

step() { echo -e "\n${GREEN}▶${NC} ${BOLD}$1${NC}"; }
info() { echo -e "  ${YELLOW}ℹ${NC}  $1"; }
ok()   { echo -e "  ${GREEN}✔${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }

wait_for_pod() {
  local label="$1"
  local timeout="${2:-120}"
  step "Waiting for pod with label '${label}' to be Ready (timeout: ${timeout}s)…"
  kubectl wait pod \
    -n "${NAMESPACE}" \
    -l "${label}" \
    --for=condition=Ready \
    --timeout="${timeout}s" || warn "Pod did not become Ready in time. Check: kubectl get pods -n ${NAMESPACE}"
}

# ─── LLM provider badge ───────────────────────────────────────────────────────
if [ "${LLM_PROVIDER}" = "nvidia" ]; then
  LLM_BADGE="${CYAN}NVIDIA NIM${NC}"
else
  LLM_BADGE="${GREEN}Local Ollama${NC}"
fi

# =============================================================================
# PRE-DEMO HEALTH CHECK
# =============================================================================
banner "Pre-Demo Health Check"

info "Active LLM Provider: ${LLM_BADGE}"
info "Node IP: ${NODE_IP}"
info "Namespace: ${NAMESPACE}"
echo ""

step "Checking that core pods are running…"
kubectl get pods -n "${NAMESPACE}" --no-headers 2>/dev/null || warn "Could not list pods"
echo ""

info "If any pods are in Pending/Error state, run setup.sh first."
echo ""
read -r -p "  Press ENTER to continue with the demo…"

# =============================================================================
# SCENARIO 1 — ImagePullBackOff → AI Diagnosis → Approve & Run
# =============================================================================
banner "SCENARIO 1 — ImagePullBackOff (Bad Image Tag)"

info "Feature demonstrated: AI pipeline (RunWhen + ${LLM_PROVIDER^^}) + Guardrails + Approve & Run UI"

step "Deploying a pod with a deliberately misspelled image tag (nginx:baddytag)…"
kubectl apply -n "${NAMESPACE}" -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: demo-bad-image
  namespace: k8s-ai
  labels:
    scenario: imagepullbackoff
spec:
  containers:
    - name: web
      image: nginx:baddytag
  restartPolicy: Never
EOF

info "Giving Kubernetes ~30 s to detect the ImagePullBackOff…"
sleep 30

step "Verifying pod state…"
kubectl get pod demo-bad-image -n "${NAMESPACE}" || true

ok "Scenario 1 is live!"
echo ""
echo "  👉  Open the dashboard at http://${NODE_IP}:${FRONTEND_PORT}"
echo "      You should see an 'ImagePullBackOff' issue card with:"
echo "        • AI diagnosis from RunWhen + ${LLM_PROVIDER^^}"
echo "        • Suggested Remediation command"
echo "        • ⚡ Approve & Run button"
echo "      After clicking 'Approve & Run', the dashboard will START POLLING"
echo "      every 5 s (up to 12 times) and automatically update when the issue clears."
echo ""
read -r -p "  Press ENTER when ready for Scenario 2…"

step "Removing demo-bad-image pod…"
kubectl delete pod demo-bad-image -n "${NAMESPACE}" --ignore-not-found

# =============================================================================
# SCENARIO 2 — Guardrail Block (Unsafe Command)
# =============================================================================
banner "SCENARIO 2 — Guardrail Protection (Unsafe Command Blocked)"

info "Feature demonstrated: Guardrail agent blocks destructive kubectl commands"

step "Sending an unsafe command directly to the /execute API…"
info "Opening a port-forward to the backend in the background…"
kubectl port-forward -n "${NAMESPACE}" svc/backend 18000:8000 &
PF_PID=$!
sleep 4   # let the tunnel establish

UNSAFE_RESPONSE=$(curl -s -X POST http://localhost:18000/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"kubectl delete namespace k8s-ai","issue":"demo-guardrail-test"}')

echo ""
echo "  Response from backend (UNSAFE command):"
echo "  ${UNSAFE_RESPONSE}"
echo ""

SAFE_RESPONSE=$(curl -s -X POST http://localhost:18000/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"kubectl get pods -A","issue":"demo-guardrail-test"}')

echo "  Safe command response (get pods):"
echo "  ${SAFE_RESPONSE}"
echo ""

kill "${PF_PID}" 2>/dev/null || true

ok "Scenario 2 complete!"
echo ""
echo "  👉  Notice:"
echo "        UNSAFE  (kubectl delete namespace …) → ❌ Command blocked by guardrail"
echo "        SAFE    (kubectl get pods -A)        → ✅ Shows actual pod list"
echo ""
read -r -p "  Press ENTER when ready for Scenario 3…"

# =============================================================================
# SCENARIO 3 — Incident Vector Memory (ChromaDB)
# =============================================================================
banner "SCENARIO 3 — Incident Vector Memory (ChromaDB learns from past fixes)"

info "Feature demonstrated: ChromaDB + SentenceTransformers stores + retrieves fixes"

step "Opening a port-forward to the backend…"
kubectl port-forward -n "${NAMESPACE}" svc/backend 18001:8000 &
PF_PID2=$!
sleep 4

step "Seeding ChromaDB with a past ImagePullBackOff fix…"
SEED_RESPONSE=$(curl -s -X POST http://localhost:18001/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "kubectl set image deployment/demo-app web=nginx:stable",
    "issue": "Pod demo-app is in ImagePullBackOff because image nginx:baddytag does not exist"
  }')
echo "  Seed response: ${SEED_RESPONSE}"

info "Now deploy a SECOND pod with the same bad image (slightly different name)…"
kubectl apply -n "${NAMESPACE}" -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: demo-bad-image-2
  namespace: k8s-ai
  labels:
    scenario: vectormemory
spec:
  containers:
    - name: web
      image: nginx:wrongtag
  restartPolicy: Never
EOF

sleep 25

step "Triggering a fresh analysis — the AI should now reference the past fix…"
ANALYSIS=$(curl -s http://localhost:18001/analyze)
echo ""
echo "  Analysis result (check 'explanation' for mention of past context):"
echo "${ANALYSIS}" | python3 -m json.tool 2>/dev/null || echo "${ANALYSIS}"
echo ""

kill "${PF_PID2}" 2>/dev/null || true
kubectl delete pod demo-bad-image-2 -n "${NAMESPACE}" --ignore-not-found

ok "Scenario 3 complete!"
echo ""
echo "  👉  In the AI explanation you should see past similar fixes referenced."
echo "      This is ChromaDB providing historic context to the ${LLM_PROVIDER^^} prompt."
echo ""
read -r -p "  Press ENTER when ready for Scenario 4…"

# =============================================================================
# SCENARIO 4 — Event-Driven Alert Loop
# =============================================================================
banner "SCENARIO 4 — Event-Driven Alert Loop (Prometheus → Alertmanager → Webhook)"

info "Feature demonstrated: Full event pipeline — Prometheus alert fires, Antigravity"
info "Listener picks it up, triggers targeted backend analysis, result appears on dashboard."

step "Deploying a CrashLoopBackOff pod to trigger Prometheus PodCrashLooping alert…"
kubectl apply -n "${NAMESPACE}" -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: demo-crashloop
  namespace: k8s-ai
  labels:
    scenario: eventdriven
spec:
  containers:
    - name: crasher
      image: busybox:latest
      command: ["sh", "-c", "echo 'Simulating crash' && exit 1"]
  restartPolicy: Always
EOF

info "The pod will start crash-looping. Prometheus evaluates alert rules every 30 s."
info "Once the alert fires, Alertmanager will POST to the Antigravity Listener."
info "The listener will forward it to the backend's /webhook/alert endpoint."
info "The backend will run RunWhen diagnostics and cache the result."
echo ""

step "Manually sending a simulated alert payload to speed up the demo…"
info "Opening a port-forward to the Antigravity Listener…"
kubectl port-forward -n "${NAMESPACE}" svc/antigravity-listener-svc 18080:8080 &
PF_PID3=$!
sleep 4

WEBHOOK_PAYLOAD='{
  "version": "4",
  "groupLabels": { "alertname": "PodCrashLooping" },
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "PodCrashLooping",
        "namespace": "k8s-ai",
        "pod": "demo-crashloop",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Pod demo-crashloop is crash-looping",
        "description": "Pod demo-crashloop in namespace k8s-ai has restarted more than 3 times in 5 minutes."
      }
    }
  ]
}'

step "Sending simulated Alertmanager payload to Antigravity Listener…"
LISTENER_RESP=$(curl -s -X POST http://localhost:18080/webhook/alertmanager \
  -H "Content-Type: application/json" \
  -d "${WEBHOOK_PAYLOAD}")
echo "  Listener acknowledged: ${LISTENER_RESP}"

kill "${PF_PID3}" 2>/dev/null || true

info "The backend is now running the analysis in the background…"
info "Open the dashboard — within ~30 s you should see the CrashLoopBackOff issue card."
info "(The dashboard polls /analyze every 5 s automatically after a remediation is applied.)"
echo ""

step "Tailing Antigravity Listener logs for trace output…"
kubectl logs -n "${NAMESPACE}" deploy/antigravity-listener --tail=20 || true

ok "Scenario 4 triggered!"
echo ""
echo "  👉  Open the dashboard at http://${NODE_IP}:${FRONTEND_PORT}"
echo "        • The crash-looping pod issue should appear via event-driven detection."
echo "        • Click 'Approve & Run' to apply the fix."
echo "        • The dashboard will poll until the pod is replaced / restarted."
echo ""
echo "  👉  Open Grafana at http://${NODE_IP}:${GRAFANA_PORT} to see metrics."
echo "        Username: admin   Password: admin"
echo ""

read -r -p "  Press ENTER to clean up Scenario 4 pods…"
kubectl delete pod demo-crashloop -n "${NAMESPACE}" --ignore-not-found

# =============================================================================
# BONUS — OBSERVABILITY CHECK
# =============================================================================
banner "BONUS — Grafana & Prometheus Setup Verification"

step "Checking Prometheus targets…"
kubectl port-forward -n "${NAMESPACE}" svc/prometheus-svc 19090:9090 &
PF_PROM=$!
sleep 4
PROM_TARGETS=$(curl -s http://localhost:19090/api/v1/targets | python3 -m json.tool 2>/dev/null | grep '"health"' | head -5 || echo "(run manually)")
echo "  Prometheus targets:"
echo "${PROM_TARGETS}"
kill "${PF_PROM}" 2>/dev/null || true

step "Checking Alertmanager alert groups…"
kubectl port-forward -n "${NAMESPACE}" svc/alertmanager-svc 19093:9093 &
PF_AM=$!
sleep 4
AM_STATUS=$(curl -s http://localhost:19093/api/v2/alerts | python3 -m json.tool 2>/dev/null | head -20 || echo "(run manually)")
echo "  Alertmanager current alerts:"
echo "${AM_STATUS}"
kill "${PF_AM}" 2>/dev/null || true

# =============================================================================
# SUMMARY
# =============================================================================
banner "All Scenarios Complete — Platform Feature Summary"

cat <<SUMMARY

  ${BOLD}Active LLM Provider:${NC} ${LLM_BADGE}

  ${BOLD}Feature Coverage:${NC}

  ✅  Scenario 1: ImagePullBackOff
        RunWhen discovers the failure, ${LLM_PROVIDER^^} explains it, dashboard shows
        AI diagnosis + suggested kubectl fix. One-click 'Approve & Run'.
        Dashboard POLLS every 5 s (up to 12 times) to auto-update status.

  ✅  Scenario 2: Guardrail Protection
        Dangerous commands (delete namespace, rm) are blocked at the API
        level before any kubectl execution happens. Safe commands pass.

  ✅  Scenario 3: Incident Vector Memory (ChromaDB)
        Past (Issue → Fix) pairs are embedded with SentenceTransformers
        and stored in ChromaDB. On the next similar failure the LLM
        receives those past fixes as context → faster, more accurate remediation.

  ✅  Scenario 4: Event-Driven Alert Loop
        Prometheus → Alertmanager → Antigravity Listener → FastAPI webhook.
        Backend executes mapped RunWhen diagnostic script
        and the result surfaces on the dashboard without manual polling.

  ${BOLD}Access Points:${NC}
  • Dashboard:     http://${NODE_IP}:${FRONTEND_PORT}
  • Grafana:       http://${NODE_IP}:${GRAFANA_PORT}  (admin / admin)
  • Prometheus:    http://${NODE_IP}:${PROMETHEUS_PORT}
  • Alertmanager:  http://${NODE_IP}:${ALERTMANAGER_PORT}

SUMMARY
