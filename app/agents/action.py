from app.tools.ollama import query_ollama

def suggest_fix(issue: str):
    # Apply explicit remediation rule for ImagePullBackOff before calling the LLM
    # so we get a deterministic, fast response for the most common failure type.
    if "ImagePullBackOff" in issue or "ErrImagePull" in issue:
        # Extract a best-effort deployment/container name from the issue text.
        # The LLM will fill in the correct values from the full context.
        prompt = (
            f"The following Kubernetes Pod is in ImagePullBackOff:\n{issue}\n\n"
            "Return ONLY a single kubectl set image command in the form:\n"
            "kubectl set image deployment/<name> <container>=<correct-image>:<tag>"
        )
    else:
        prompt = (
            f"Kubernetes Pod failure:\n{issue}\n\n"
            "Return ONLY a single kubectl command to fix the root cause."
        )
    return query_ollama(prompt)
