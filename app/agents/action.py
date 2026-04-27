from app.tools.ollama import query_ollama

def suggest_fix(issue: str):
    prompt = f"Suggest a kubectl command to fix:\n{issue}\nOnly return command."
    return query_ollama(prompt)
