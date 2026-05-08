def validate_action(action: str):
    command = (action or "").strip()
    if not command:
        return False

    lowered = command.lower()
    blocked = ["delete", "rm", "wipe", "format"]
    unsafe_patterns = [";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r"]

    if lowered.startswith(("error:", "ai error:")):
        return False

    for b in blocked:
        if b in lowered:
            return False

    for pattern in unsafe_patterns:
        if pattern in command:
            return False

    tokens = command.split()
    if not tokens:
        return False

    allowed_verbs = {
        "get", "describe", "logs", "set", "rollout", "scale",
        "annotate", "label", "top", "cordon", "uncordon", "port-forward"
    }

    if tokens[0].lower() == "kubectl":
        if len(tokens) < 2:
            return False
        return tokens[1].lower() in allowed_verbs

    return tokens[0].lower() in allowed_verbs
