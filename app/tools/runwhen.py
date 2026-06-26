"""
app/tools/runwhen.py — RunWhen Skills Registry execution

Deterministic alert-to-script mapping router. Maps Prometheus alertnames
to specific, audited RunWhen CodeBundle scripts for read-only diagnosis.
"""

import os
import subprocess
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Base path where the init container clones rw-cli-codecollection
RUNWHEN_BASE_DIR = "/opt/runwhen/codebundles"

# Alertname to CodeBundle mapping
ALERT_TO_RUNWHEN_MAP: Dict[str, Dict[str, str]] = {
    "PodCrashLooping": {
        "codebundle": "k8s-namespace-healthcheck",
        "script": "runbook.sh",
        "description": "General namespace and pod health check",
    },
    "KubePodNotReady": {
        "codebundle": "k8s-namespace-healthcheck",
        "script": "runbook.sh",
        "description": "General namespace and pod health check",
    },
    "KubeDeploymentReplicasMismatch": {
        "codebundle": "k8s-deployment-healthcheck",
        "script": "runbook.sh",
        "description": "Deployment specific health check",
    },
    "KubePersistentVolumeFillingUp": {
        "codebundle": "k8s-pvc-healthcheck",
        "script": "runbook.sh",
        "description": "Persistent Volume Claim health check",
    },
    "KubeNodeNotReady": {
        "codebundle": "k8s-node-healthcheck",
        "script": "runbook.sh",
        "description": "Node health check",
    },
    "KubeContainerOOMKilled": {
        "codebundle": "k8s-namespace-healthcheck",
        "script": "runbook.sh",
        "description": "General namespace and pod health check",
    },
}

class RunWhenRunner:
    @staticmethod
    def execute_diagnostic(alert_name: str, context: dict) -> Optional[str]:
        """
        Execute the appropriate RunWhen CodeBundle script for a given alert.
        
        Args:
            alert_name: The Prometheus alertname.
            context: Dictionary containing alert context like namespace, pod.
            
        Returns:
            Structured Markdown output from the script, or None if no script
            is mapped or if the execution fails.
        """
        mapping = ALERT_TO_RUNWHEN_MAP.get(alert_name)
        if not mapping:
            logger.info("runwhen: No mapping found for alert '%s'. Falling back to default cluster context.", alert_name)
            return None
            
        codebundle = mapping["codebundle"]
        script = mapping["script"]
        script_path = os.path.join(RUNWHEN_BASE_DIR, codebundle, script)
        
        if not os.path.isfile(script_path):
            logger.warning("runwhen: CodeBundle script not found at %s", script_path)
            return None
            
        namespace = context.get("namespace", "default")
        pod = context.get("pod", "")
        
        # Build environment for the script
        env = os.environ.copy()
        env["NAMESPACE"] = namespace
        env["CONTEXT"] = namespace # Some scripts might expect CONTEXT
        if pod and pod != "unknown_resource":
             env["POD_NAME"] = pod
        
        logger.info("runwhen: Executing %s for alert '%s' in namespace '%s'", codebundle, alert_name, namespace)
        
        try:
            # Run the bash script with a timeout
            result = subprocess.run(
                ["bash", script_path],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.warning(
                    "runwhen: Script %s failed with exit code %d. stderr: %s", 
                    script_path, result.returncode, result.stderr.strip()
                )
                return None
                
            output = result.stdout.strip()
            if not output:
                logger.warning("runwhen: Script %s returned empty output.", script_path)
                return None
                
            return f"### RunWhen Diagnostic Report ({codebundle})\n\n{output}"
            
        except subprocess.TimeoutExpired:
            logger.error("runwhen: Execution of %s timed out after 30 seconds.", script_path)
            return None
        except Exception as e:
            logger.exception("runwhen: Failed to execute %s: %s", script_path, e)
            return None
