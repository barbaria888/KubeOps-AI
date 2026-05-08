import os
import shlex
import subprocess

def run_kubectl(command: str):
    timeout_seconds = int(os.getenv("KUBEOPS_KUBECTL_TIMEOUT_SECONDS", "90"))
    raw_command = (command or "").strip()

    if not raw_command:
        return "Error: Empty command."

    try:
        tokens = shlex.split(raw_command)
    except ValueError as exc:
        return f"Error: Invalid command syntax. {exc}"

    if not tokens:
        return "Error: Empty command."

    if tokens[0].lower() == "kubectl":
        tokens = tokens[1:]

    if not tokens:
        return "Error: Missing kubectl arguments."

    cmd = ["kubectl"] + tokens

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return f"Error: kubectl command timed out after {timeout_seconds} seconds."
    except FileNotFoundError:
        return "Error: kubectl binary not found in backend container."
