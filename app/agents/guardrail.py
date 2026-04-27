def validate_action(action: str):
    blocked = ["delete", "rm", "wipe", "format"]

    for b in blocked:
        if b in action.lower():
            return False

    return True
