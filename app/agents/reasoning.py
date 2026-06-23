from app.tools.llm import query_llm
from app.tools.vector_store import search_similar


def explain_issue(issue: str) -> str:
    """Ask the active LLM to explain a Kubernetes issue with historical context.

    Queries ChromaDB for past similar incidents and injects them as context
    into the prompt so the model can reference past successful fixes.
    Works with both Ollama (local) and NVIDIA NIM (cloud) backends.
    """
    past = search_similar(issue)

    prompt = (
        f"Kubernetes Pod failure detected:\n{issue}\n\n"
        f"Similar past fixes (for context only):\n{past}\n\n"
        "Focus on Pod failures only. Ignore unused ConfigMaps. "
        "In one sentence, identify the root cause and provide the exact "
        "kubectl command to remediate it."
    )

    return query_llm(prompt)
