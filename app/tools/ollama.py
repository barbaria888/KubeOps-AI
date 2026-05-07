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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "tinyllama")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))

# SRE system prompt injected into every Ollama request so the model behaves as a
# focused Kubernetes SRE agent regardless of the individual user prompt.
SRE_SYSTEM_PROMPT = (
    "You are a Kubernetes SRE assistant in a CPU-only environment. "
    "Focus only on Pod failures, ignore ConfigMaps, and be concise. "
    "Return one diagnosis sentence and one kubectl command, nothing else."
)


def query_ollama(prompt: str) -> str:
    """
    Sends a prompt to the local Ollama instance and returns the reasoning text.
    The SRE system prompt is always included so the model stays focused on
    high-priority Kubernetes diagnostics.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "system": SRE_SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 80,
            "temperature": 0.2
        }
    }

    try:
        logger.info(f"Sending request to Ollama at {OLLAMA_URL} using model {OLLAMA_MODEL}")
        
        # We add a 60s timeout because LLMs can be slow on CPU-only nodes
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
        
        # Raise an exception for 4XX/5XX errors
        response.raise_for_status()
        
        return response.json().get("response", "AI returned an empty response.")

    except requests.exceptions.ConnectionError:
        logger.error(f"Failed to connect to Ollama at {OLLAMA_URL}. Is the service running?")
        return "Error: Could not connect to the AI engine."
    
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out. The model is taking too long to respond.")
        return "Error: AI reasoning timed out. Try a smaller model like tinyllama."
    
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama: {str(e)}")
        return f"AI Error: {str(e)}"
