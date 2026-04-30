import requests
import os
import logging

# Set up logging so you can see errors in 'kubectl logs'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use Environment Variables with sensible defaults
# In K8s, this will be http://ollama:11434/api/generate
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
# Set the model via ENV so you can switch between tinyllama and gemma:2b without rebuilding
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "tinyllama")

# SRE system prompt injected into every Ollama request so the model behaves as a
# focused Kubernetes SRE agent regardless of the individual user prompt.
SRE_SYSTEM_PROMPT = (
    "You are an expert Kubernetes SRE Agent. "
    "You are operating in a resource-constrained, CPU-only environment where speed and "
    "precision are critical.\n\n"
    "CONTEXT & INFRASTRUCTURE AWARENESS:\n"
    "- Infrastructure: K3s cluster on a single-node control plane.\n"
    "- AI Engine: Local Ollama (tinyllama) via internal Service DNS (http://ollama:11434).\n"
    "- Constraints: The Frontend (Nginx) and Backend (FastAPI) have 300s timeouts. "
    "You must generate text FAST to prevent a 504 Gateway Timeout.\n\n"
    "YOUR DIAGNOSTIC GOALS:\n"
    "1. IDENTIFY: Scan the K8sGPT JSON input. Focus ONLY on high-priority errors "
    "(Pod failures). Ignore unused ConfigMaps.\n"
    "2. REMEDIATE: Generate a concrete 'kubectl' command to fix the root cause.\n"
    "3. CONNECTIVITY CHECK: Ensure you are suggesting actions via the Backend API "
    "(/api/execute). If the UI shows a 504 error, it means you took too long or Nginx "
    "lost the path to http://backend:8000.\n\n"
    "OPERATIONAL RULES:\n"
    "- Be concise. One diagnosis sentence, one kubectl command. Nothing else."
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
        "stream": False
    }

    try:
        logger.info(f"Sending request to Ollama at {OLLAMA_URL} using model {OLLAMA_MODEL}")
        
        # We add a 60s timeout because LLMs can be slow on CPU-only nodes
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        
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
