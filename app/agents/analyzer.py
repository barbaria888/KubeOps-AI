from app.tools.k8sgpt import run_k8sgpt
from app.agents.reasoning import explain_issue
from app.agents.action import suggest_fix
from app.agents.guardrail import validate_action

def analyze_cluster():
    issues = run_k8sgpt()
    results = []

    for issue in issues.get("results", []):
        description = issue.get("description", "")

        explanation = explain_issue(description)
        action = suggest_fix(description)

        safe = validate_action(action)

        results.append({
            "issue": description,
            "explanation": explanation,
            "suggested_action": action,
            "safe": safe
        })

    return results
