import subprocess
import json
import logging
import os

logger = logging.getLogger(__name__)


def run_k8sgpt(namespace: str = None) -> dict:
    """Run k8sgpt analyze and return raw JSON results.

    Args:
        namespace: Optional Kubernetes namespace to scope the analysis to.
                   When provided (e.g. from a Prometheus webhook), only the
                   pods in that namespace are inspected which is faster and
                   avoids noise from unrelated namespaces.
    """
    try:
        timeout_seconds = int(os.getenv("KUBEOPS_K8SGPT_TIMEOUT_SECONDS", "120"))

        cmd = ["k8sgpt", "analyze", "--filter=Pod", "-o", "json"]
        if namespace and namespace not in ("", "default"):
            cmd += ["--namespace", namespace]
            logger.info("k8sgpt: scoped analysis to namespace '%s'", namespace)
        else:
            logger.info("k8sgpt: running cluster-wide analysis")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            error_output = (result.stderr or result.stdout or "k8sgpt failed").strip()
            return {"results": [{"description": error_output}]}

        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"results": [{"description": "k8sgpt timed out while analyzing Pod failures."}]}
    except Exception as e:
        return {"results": [{"description": str(e)}]}
