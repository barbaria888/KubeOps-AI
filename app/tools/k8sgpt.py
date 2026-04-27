import subprocess
import json

def run_k8sgpt():
    try:
        result = subprocess.run(
            ["k8sgpt", "analyze", "-o", "json"],
            capture_output=True,
            text=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        return {"results": [{"description": str(e)}]}
