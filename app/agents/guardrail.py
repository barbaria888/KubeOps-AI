"""
app/agents/guardrail.py — Command Safety Guardrail

Two-layer defense (application level) that mirrors the RBAC ClusterRole
in k8s/rbac.yaml.  Even if one layer has a bug the other provides a
safety net.

Allowed kubectl verbs (must match rbac.yaml exactly):
  get, describe, logs, set, rollout, scale,
  annotate, label, top, cordon, uncordon, port-forward

Blocked verbs/keywords:
  delete, rm, wipe, format, exec, apply, edit, create
  (except pods/portforward which is handled by 'port-forward' verb)
"""

import re


def validate_action(action: str) -> bool:
    """Return True if a single command string is safe to execute.

    This is the original guardrail — kept intact for backward compatibility.
    For multi-line LLM output, use ``validate_action_list()`` instead.
    """
    command = (action or "").strip()
    if not command:
        return False

    lowered = command.lower()

    # Block known destructive keywords
    blocked = ["delete", "rm", "wipe", "format", "exec", "apply", "edit"]
    unsafe_patterns = [";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r"]

    # Prevent accidental execution when the model returns an error string
    # instead of a kubectl command.
    if lowered.startswith(("error:", "ai error:", "404 client error", "500 server error")):
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

    # Verbs allowed by both the guardrail AND the RBAC ClusterRole.
    allowed_verbs = {
        "get", "describe", "logs", "set", "rollout", "scale",
        "annotate", "label", "top", "cordon", "uncordon", "port-forward"
    }

    if tokens[0].lower() == "kubectl":
        if len(tokens) < 2:
            return False
        return tokens[1].lower() in allowed_verbs

    return tokens[0].lower() in allowed_verbs


def validate_action_list(raw_action_text: str) -> tuple:
    """Parse multi-line LLM output, validate each command, return safe ones.

    The LLM may return a structured remediation plan with section headers
    (DIAGNOSTIC, REMEDIATION, VERIFICATION) and numbered/bulleted commands.
    This function extracts individual ``kubectl ...`` commands, validates
    each one through ``validate_action()``, and returns a tuple of:

      (all_safe: bool, safe_commands: list[str])

    Args:
        raw_action_text: Raw multi-line string from the action agent.

    Returns:
        A tuple of ``(all_safe, safe_commands)`` where ``all_safe`` is True
        only if every extracted command passed the guardrail.
    """
    if not raw_action_text or not raw_action_text.strip():
        return False, []

    lines = raw_action_text.strip().splitlines()
    extracted_commands: list[str] = []

    for line in lines:
        cleaned = line.strip()

        # Skip empty lines, section headers, and commentary
        if not cleaned:
            continue
        if cleaned.upper().startswith(("DIAGNOSTIC:", "REMEDIATION:", "VERIFICATION:")):
            continue
        if cleaned.startswith(("#", "---", "===")):
            continue

        # Strip leading numbering: "1. ", "2) ", "- ", "* "
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", cleaned)
        cleaned = re.sub(r"^[-*]\s*", "", cleaned)
        cleaned = cleaned.strip()

        # Strip trailing explanation after " — " or " - " separators
        if " — " in cleaned:
            cleaned = cleaned.split(" — ")[0].strip()
        elif " -- " in cleaned:
            cleaned = cleaned.split(" -- ")[0].strip()

        # Only accept lines that look like kubectl commands
        if cleaned.lower().startswith("kubectl "):
            extracted_commands.append(cleaned)

    if not extracted_commands:
        return False, []

    safe_commands: list[str] = []
    all_safe = True

    for cmd in extracted_commands:
        if validate_action(cmd):
            safe_commands.append(cmd)
        else:
            all_safe = False

    return all_safe if safe_commands else False, safe_commands

