import os
import logging

import requests

# Set up logging so you can see errors in 'kubectl logs'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use Environment Variables with sensible defaults
# In K8s, this will be http://ollama:11434/api/generate
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
# Set the model via ENV so you can switch between tinyllama and gemma:2b without rebuilding
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "tinyllama:latest")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
OLLAMA_FALLBACK_MODELS = os.getenv("OLLAMA_FALLBACK_MODELS", "tinyllama:latest,gemma:2b")

# Import the shared SRE system prompt from the unified LLM module so
# behaviour stays consistent regardless of which backend is active.
from app.tools.llm import SRE_SYSTEM_PROMPT


def query_ollama(prompt: str) -> str:
    """
    Sends a prompt to the local Ollama instance and returns the reasoning text.
    The SRE system prompt is always included so the model stays focused on
    high-priority Kubernetes diagnostics.
    """
    model_candidates = [OLLAMA_MODEL]
    if ":" not in OLLAMA_MODEL:
        model_candidates.append(f"{OLLAMA_MODEL}:latest")

    model_candidates.extend(
        [m.strip() for m in OLLAMA_FALLBACK_MODELS.split(",") if m.strip()]
    )

    deduped_models = []
    seen = set()
    for model in model_candidates:
        if model not in seen:
            seen.add(model)
            deduped_models.append(model)

    base_payload = {
        "system": SRE_SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 1024,
            "temperature": 0.2
        }
    }

    try:
        logger.info(
            f"Sending request to Ollama at {OLLAMA_URL} with model candidates: {', '.join(deduped_models)}"
        )

        # We add a timeout because LLMs can be slow on CPU-only nodes
        for model in deduped_models:
            payload = {"model": model, **base_payload}
            response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)

            if response.ok:
                logger.info(f"Ollama response succeeded with model {model}")
                return response.json().get("response", "AI returned an empty response.")

            if response.status_code == 404:
                logger.warning(f"Ollama returned 404 for model {model}, trying next model candidate.")
                continue

            response.raise_for_status()

        return (
            "Error: AI model unavailable on Ollama. "
            "Pull a model (for example tinyllama:latest) and retry."
        )

    except requests.exceptions.ConnectionError:
        logger.error(f"Failed to connect to Ollama at {OLLAMA_URL}. Is the service running?")
        return "Error: Could not connect to the AI engine."
    
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out. The model is taking too long to respond.")
        return "Error: AI reasoning timed out. Try a smaller model like tinyllama."
    
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama: {str(e)}")
        return f"AI Error: {str(e)}"
