"""
app/tools/llm.py — Unified LLM Client

Reads the LLM_PROVIDER environment variable ("ollama" or "nvidia") and
routes every inference call to the appropriate backend.

  LLM_PROVIDER=ollama  → local Ollama inference (default, free, private)
  LLM_PROVIDER=nvidia  → NVIDIA NIM API via OpenAI-compatible SDK

All agents (reasoning.py, action.py) call query_llm() and never need to
know which backend is active.
"""

import os
import logging

logger = logging.getLogger(__name__)

# ─── Provider Selection ────────────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower().strip()

# ─── NVIDIA NIM Configuration ─────────────────────────────────────────────────
NVIDIA_BASE_URL   = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY    = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL      = os.getenv("NVIDIA_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1")
NVIDIA_MAX_TOKENS = int(os.getenv("NVIDIA_MAX_TOKENS", "2048"))
NVIDIA_TEMPERATURE = float(os.getenv("NVIDIA_TEMPERATURE", "0.2"))

# SRE system prompt used by both backends so behaviour is consistent
# regardless of which engine answers.
SRE_SYSTEM_PROMPT = (
    "You are a senior Kubernetes Site Reliability Engineer (SRE) with deep "
    "expertise in cluster operations, pod lifecycle, networking, storage, "
    "scheduling, and resource management.\n\n"
    "Guidelines:\n"
    "- Focus on actionable Kubernetes operational issues: pod failures, "
    "CrashLoopBackOff, ImagePullBackOff, OOMKilled, scheduling failures, "
    "node pressure, service connectivity, storage issues, RBAC denials.\n"
    "- Ignore informational findings like unused ConfigMaps or Secrets.\n"
    "- When diagnosing, reference the live cluster context and past incidents "
    "provided in the prompt.\n"
    "- Suggest kubectl commands that use ONLY these verbs: get, describe, "
    "logs, set, rollout, scale, annotate, label, top, cordon, uncordon. "
    "Never suggest delete, create, exec, apply, patch, or edit commands.\n"
    "- Prefer diagnostic commands (describe, logs, get events) before "
    "any mutating actions (set image, rollout restart, scale).\n"
    "- Be concise but thorough. Provide structured output."
)


# ─── NVIDIA NIM path ──────────────────────────────────────────────────────────

def _query_nvidia(prompt: str) -> str:
    """Call NVIDIA NIM via the OpenAI-compatible REST API."""
    try:
        from openai import OpenAI  # imported lazily — not needed for Ollama path
    except ImportError:
        logger.error("openai package not installed. Run: pip install openai")
        return "Error: openai package missing. Install it with: pip install openai"

    if not NVIDIA_API_KEY:
        logger.error("NVIDIA_API_KEY is not set. Cannot call NVIDIA NIM.")
        return "Error: NVIDIA_API_KEY environment variable is not configured."

    try:
        client = OpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=NVIDIA_API_KEY,
        )

        logger.info(
            "Sending request to NVIDIA NIM | model=%s base_url=%s",
            NVIDIA_MODEL, NVIDIA_BASE_URL,
        )

        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": SRE_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=NVIDIA_TEMPERATURE,
            top_p=1,
            max_tokens=NVIDIA_MAX_TOKENS,
            stream=False,   # keep simple — SRE responses are short
        )

        content = response.choices[0].message.content or ""
        logger.info("NVIDIA NIM response received (%d chars)", len(content))
        return content.strip()

    except Exception as exc:
        logger.exception("NVIDIA NIM call failed: %s", exc)
        return f"Error: NVIDIA NIM request failed — {exc}"


# ─── Ollama path ──────────────────────────────────────────────────────────────

def _query_ollama_local(prompt: str) -> str:
    """Delegate to the Ollama tool module."""
    from app.tools.ollama import query_ollama  # noqa: PLC0415
    return query_ollama(prompt)


# ─── Public Interface ─────────────────────────────────────────────────────────

def query_llm(prompt: str) -> str:
    """
    Universal LLM entrypoint used by all agents.

    Routes to the correct backend based on LLM_PROVIDER:
      "nvidia" → NVIDIA NIM API  (requires NVIDIA_API_KEY)
      "ollama" → local Ollama    (default, requires running Ollama pod/service)

    Both paths share the same SRE system prompt so model behaviour is
    consistent across providers.
    """
    if LLM_PROVIDER == "nvidia":
        logger.debug("LLM route: NVIDIA NIM (model=%s)", NVIDIA_MODEL)
        return _query_nvidia(prompt)

    # Default: Ollama
    logger.debug("LLM route: Ollama (LLM_PROVIDER=%s)", LLM_PROVIDER)
    return _query_ollama_local(prompt)
