import subprocess

def run_kubectl(command: str):
    cmd = ["kubectl"] + command.split()
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr
