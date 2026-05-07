import os

from app.tools.k8sgpt import run_k8sgpt
from app.agents.reasoning import explain_issue
from app.agents.action import suggest_fix
from app.agents.guardrail import validate_action


def _safe_text(value):
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _fallback_explanation(description: str) -> str:
    return f"Cluster analysis reported: {description or 'No details were returned.'}"


def _fallback_action(description: str) -> str:
    if "ImagePullBackOff" in description or "ErrImagePull" in description:
        return "kubectl describe pod <pod-name>"
    if "CrashLoopBackOff" in description:
        return "kubectl logs <pod-name> --previous"
    return "kubectl get pods -A"

def analyze_cluster():
    results = []
    max_issues = int(os.getenv("KUBEOPS_MAX_ANALYZED_ISSUES", "2"))
    lazy_mode = os.getenv("KUBEOPS_LAZY_ANALYSIS", "true").lower() == "true"

    if lazy_mode:
        return [{
            "issue": "Cluster analysis is warming up",
            "explanation": "Lazy analysis is enabled, so the backend returns immediately while Ollama and K8sGPT are still starting.",
            "suggested_action": "kubectl get pods -A",
            "safe": True,
        }]

    issues = run_k8sgpt()

    if not isinstance(issues, dict):
        issues = {"results": []}

    for issue in issues.get("results", [])[:max_issues]:
        if not isinstance(issue, dict):
            issue = {"description": issue}

        description = _safe_text(issue.get("description", ""))

        explanation = _fallback_explanation(description)
        action = _fallback_action(description)

        if os.getenv("KUBEOPS_ENABLE_FULL_OLLAMA", "false").lower() == "true":
            try:
                ai_explanation = _safe_text(explain_issue(description))
                if ai_explanation and not ai_explanation.startswith(("Error:", "AI Error:")):
                    explanation = ai_explanation
            except Exception:
                pass

            try:
                ai_action = _safe_text(suggest_fix(description))
                if ai_action and not ai_action.startswith(("Error:", "AI Error:")):
                    action = ai_action
            except Exception:
                pass

        safe = validate_action(action)

        results.append({
            "issue": description,
            "explanation": explanation,
            "suggested_action": action,
            "safe": safe
        })

    return results
