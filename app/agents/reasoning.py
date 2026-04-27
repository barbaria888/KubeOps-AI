from app.tools.ollama import query_ollama
from app.tools.vector_store import search_similar

def explain_issue(issue: str):
    past = search_similar(issue)

    prompt = f"""
    Kubernetes issue:
    {issue}

    Similar past fixes:
    {past}

    Explain clearly and suggest fix.
    """

    return query_ollama(prompt)
