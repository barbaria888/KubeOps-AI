import os

from app.tools.k8sgpt import run_k8sgpt
from app.agents.reasoning import explain_issue
from app.agents.action import suggest_fix
from app.agents.guardrail import validate_action

def analyze_cluster():
    issues = run_k8sgpt()
    results = []
    max_issues = int(os.getenv("KUBEOPS_MAX_ANALYZED_ISSUES", "2"))

    for issue in issues.get("results", [])[:max_issues]:
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
