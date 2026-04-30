from app.tools.ollama import query_ollama
from app.tools.vector_store import search_similar

def explain_issue(issue: str):
    past = search_similar(issue)

    prompt = (
        f"Kubernetes Pod failure detected:\n{issue}\n\n"
        f"Similar past fixes (for context only):\n{past}\n\n"
        "Focus on Pod failures only. Ignore unused ConfigMaps. "
        "In one sentence, identify the root cause and provide the exact "
        "kubectl command to remediate it."
    )

    return query_ollama(prompt)
