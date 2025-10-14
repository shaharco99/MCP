import os
import platform
import subprocess
import threading

from fastmcp import FastMCP
from kubernetes import client, config

from agents import MCPAgentOrchestrator

# Initialize MCP server and agent orchestrator
mcp = FastMCP("DevOps Tools")
agent_orchestrator = MCPAgentOrchestrator()


# =============================
# Utilities
# =============================
def run_cmd(cmd: str):
    """Run shell command and return stdout/stderr safely."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        return f"❌ Command failed:\n{result.stderr}"
    return result.stdout.strip()


def load_kube():
    """Load kubeconfig from default location depending on OS and return the current namespace."""
    if platform.system() == "Windows":
        kube_path = os.path.join(os.environ.get("USERPROFILE", ""), ".kube", "config")
    else:
        kube_path = os.path.expanduser("~/.kube/config")

    if not os.path.exists(kube_path):
        raise FileNotFoundError(f"Kubeconfig not found at {kube_path}")

    config.load_kube_config(config_file=kube_path)

    # Get current context and namespace
    contexts, active_context = config.list_kube_config_contexts()
    if active_context and "namespace" in active_context["context"]:
        return active_context["context"]["namespace"]

    return "default"


# =============================
# Minikube Tools
# =============================
def run_minikube_cmd(cmd: str):
    return run_cmd(f"minikube {cmd}")


@mcp.tool()
def minikube_start():
    def _start():
        subprocess.run("minikube start --driver=docker", shell=True)

    threading.Thread(target=_start).start()
    return "⚡ Minikube start triggered in background"


@mcp.tool()
def minikube_stop():
    return run_minikube_cmd("stop")


@mcp.tool()
def minikube_status():
    return run_minikube_cmd("status")


@mcp.tool()
def minikube_dashboard():
    return run_minikube_cmd("dashboard --url")


@mcp.tool()
def kubectl(namespace: str = None, args: str = "get namespaces"):
    """Run a kubectl command inside the minikube cluster using minikube's kubectl.

    Parameters:
        namespace: optional namespace to target
        args: the kubectl args (e.g. 'get pods -o wide')
    """
    # basic sanitation: don't allow shell redirection or pipelines
    if any(tok in args for tok in [";", "|", ">", "<"]):
        return "❌ Unsafe kubectl args detected"

    ns_flag = f"-n {namespace}" if namespace else ""
    cmd = f"minikube kubectl -- {args} {ns_flag}".strip()
    return run_cmd(cmd)


@mcp.tool()
def run_shell(cmd: str):
    """Run a whitelisted admin shell command.

    Allowed commands: minikube start|stop|status|dashboard, minikube kubectl -- <...>, docker ps, docker logs, helm version
    """
    allowed_prefixes = [
        "minikube ",
        "minikube kubectl -- ",
        "docker ",
        "helm ",
        "kubectl ",
    ]

    if not any(cmd.strip().startswith(p) for p in allowed_prefixes):
        return "❌ Command not allowed"

    # disallow redirections/pipes
    if any(tok in cmd for tok in [";", "|", ">", "<"]):
        return "❌ Unsafe characters in command"

    return run_cmd(cmd)


# =============================
# Python Runner Tool
# =============================
@mcp.tool()
def run_python_script(script: str):
    result = subprocess.run(["python", "-c", script], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else result.stderr


# =============================
# Cluster Overview
# =============================
@mcp.tool()
def cluster_overview():
    ns = load_kube()
    v1 = client.CoreV1Api()
    apps = client.AppsV1Api()

    namespaces = [n.metadata.name for n in v1.list_namespace().items]
    pods = [p.metadata.name for p in v1.list_namespaced_pod(ns).items]
    deployments = [d.metadata.name for d in apps.list_namespaced_deployment(ns).items]

    return (
        f"🌍 Minikube Status:\n{run_cmd('minikube status')}\n\n"
        f"📂 Active Namespace: {ns}\n"
        f"📂 All Namespaces: {', '.join(namespaces)}\n\n"
        f"🐳 Pods in {ns}: {', '.join(pods) if pods else '(none)'}\n"
        f"📦 Deployments in {ns}: {', '.join(deployments) if deployments else '(none)'}"
    )


# =============================
# Run MCP Server
# =============================
if __name__ == "__main__":
    # Start MCP server
    mcp.run(transport="http", host="0.0.0.0", port=8000)
