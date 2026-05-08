import os
import shlex
import subprocess

def run_kubectl(command: str):
    timeout_seconds = int(os.getenv("KUBEOPS_KUBECTL_TIMEOUT_SECONDS", "90"))
    raw_command = (command or "").strip()

    if not raw_command:
        return False, "Error: Empty command."

    try:
        tokens = shlex.split(raw_command)
    except ValueError:
        return False, "Error: Invalid command syntax."

    if not tokens:
        return False, "Error: Empty command."

    if tokens[0].lower() == "kubectl":
        tokens = tokens[1:]

    if not tokens:
        return False, "Error: Missing kubectl arguments."

    cmd = ["kubectl"] + tokens

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if result.returncode == 0:
            output = (result.stdout or "").strip()
            return True, output or "Command executed successfully."
        return False, "Error: kubectl command failed. Check backend logs for details."
    except subprocess.TimeoutExpired:
        return False, f"Error: kubectl command timed out after {timeout_seconds} seconds."
    except FileNotFoundError:
        return False, "Error: kubectl binary not found in backend container."
