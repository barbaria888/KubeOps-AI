import subprocess
import json
import os

def run_k8sgpt():
    try:
        timeout_seconds = int(os.getenv("KUBEOPS_K8SGPT_TIMEOUT_SECONDS", "120"))
        result = subprocess.run(
            ["k8sgpt", "analyze", "--filter=Pod", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )

        if result.returncode != 0:
            error_output = (result.stderr or result.stdout or "k8sgpt failed").strip()
            return {"results": [{"description": error_output}]}

        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"results": [{"description": "k8sgpt timed out while analyzing Pod failures."}]}
    except Exception as e:
        return {"results": [{"description": str(e)}]}
