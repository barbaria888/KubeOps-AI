from fastapi import FastAPI
from pydantic import BaseModel
from app.agents.analyzer import analyze_cluster
from app.tools.kubectl import run_kubectl
from app.agents.guardrail import validate_action
from app.tools.vector_store import store_issue

app = FastAPI()

class CommandRequest(BaseModel):
    command: str
    issue: str = ""

@app.get("/")
def root():
    return {"message": "K8s Agentic AI running"}

@app.get("/analyze")
def analyze():
    return analyze_cluster()

@app.post("/execute")
def execute(req: CommandRequest):
    if not validate_action(req.command):
        return {"output": "❌ Command blocked by guardrail"}

    try:
        result = run_kubectl(req.command)

        # Store incident memory on successful execution
        if req.issue:
            store_issue(req.issue, req.command)

        return {"output": result}
    except Exception:
        return {"output": "Error: command execution failed unexpectedly."}
