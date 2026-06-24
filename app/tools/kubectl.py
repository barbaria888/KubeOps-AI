import os
import logging
import shlex
import subprocess

logger = logging.getLogger(__name__)


def run_kubectl(command: str):
    """Execute a kubectl command and return (success: bool, output: str).

    On failure the actual stderr is returned so callers (including the
    analyzer fallback) can see the real error instead of a generic message.
    """
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

        # Return the real error so callers can diagnose RBAC denials, etc.
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        error_detail = stderr or stdout or "unknown error"
        logger.warning(
            "kubectl failed (rc=%d): %s | cmd=%s",
            result.returncode, error_detail, " ".join(cmd),
        )
        return False, f"Error: {error_detail}"
    except subprocess.TimeoutExpired:
        return False, f"Error: kubectl command timed out after {timeout_seconds} seconds."
    except FileNotFoundError:
        return False, "Error: kubectl binary not found in backend container."
