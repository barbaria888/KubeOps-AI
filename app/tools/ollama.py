import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

def query_ollama(prompt):
    res = requests.post(OLLAMA_URL, json={
        "model": "gemma:2b",
        "prompt": prompt,
        "stream": False
    })
    return res.json().get("response", "")
