from app.tools.llm import query_llm


def suggest_fix(issue: str) -> str:
    """Use the active LLM to suggest a kubectl remediation command.

    Applies an explicit deterministic rule for ImagePullBackOff first to
    get a fast, reliable response for the most common failure type.
    Falls back to the LLM for all other failure modes.
    Works with both Ollama (local) and NVIDIA NIM (cloud) backends.
    """
    # Apply explicit remediation rule for ImagePullBackOff before calling the LLM
    # so we get a deterministic, fast response for the most common failure type.
    # The LLM is responsible for extracting the correct deployment/container/image
    # values from the issue text.
    if "ImagePullBackOff" in issue or "ErrImagePull" in issue:
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
    return query_llm(prompt)
