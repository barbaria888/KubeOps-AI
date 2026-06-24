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
                   resources in that namespace are inspected which is faster
                   and avoids noise from unrelated namespaces.

    Returns:
        A dict with a ``results`` key containing a list of detected issues.
        Returns ``{"results": []}`` when nothing is found or on error.
    """
    try:
        timeout_seconds = int(os.getenv("KUBEOPS_K8SGPT_TIMEOUT_SECONDS", "120"))

        # Do NOT restrict to --filter=Pod — let all enabled analyzers run
        # (Pod, Service, ReplicaSet, Ingress, PVC, etc.) so the pipeline
        # can detect issues beyond just pod-level failures.
        cmd = ["k8sgpt", "analyze", "--output", "json"]
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
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            error_output = stderr or stdout or "k8sgpt failed"
            logger.error("k8sgpt exited %d: %s", result.returncode, error_output)
            return {"results": [{"description": error_output}]}

        raw = (result.stdout or "").strip()
        if not raw:
            logger.warning("k8sgpt returned an empty output buffer.")
            return {"results": []}

        return json.loads(raw)
    except subprocess.TimeoutExpired:
        return {"results": [{"description": "k8sgpt timed out while analyzing cluster resources."}]}
    except json.JSONDecodeError:
        logger.error("Failed to parse k8sgpt JSON. Raw buffer: %s", result.stdout)
        return {"results": []}
    except Exception as e:
        logger.exception("Unexpected k8sgpt error: %s", e)
        return {"results": [{"description": str(e)}]}

