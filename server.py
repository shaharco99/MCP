import os
import subprocess
import platform
import time
import threading
import docker
from kubernetes import client, config
from fastmcp import FastMCP
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

mcp = FastMCP("DevOps Tools")

# =============================
# Utilities
# =============================
def run_cmd(cmd: str):
    """Run shell command and return stdout/stderr safely."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        return f"❌ Command failed:\n{result.stderr}"
    return result.stdout.strip()

def docker_client():
    """Return a Docker client compatible with Windows or Linux."""
    if platform.system() == "Windows":
        docker_host = os.environ.get("DOCKER_HOST", "npipe:////./pipe/docker_engine")
        return docker.DockerClient(base_url=docker_host)
    return docker.from_env()

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
# Kubernetes Caching
# =============================
_k8s_cache = {"pods": {}, "namespaces": {}, "deployments": {}}
_cache_lock = threading.Lock()

def cached_k8s_fetch(kind, namespace=None, fetch_func=None, ttl=15):
    ns = namespace or load_kube()
    key = f"{kind}:{ns}"
    with _cache_lock:
        if key in _k8s_cache and time.time() - _k8s_cache[key]["timestamp"] < ttl:
            return _k8s_cache[key]["data"]
    data = fetch_func(ns) if fetch_func else []
    with _cache_lock:
        _k8s_cache[key] = {"data": data, "timestamp": time.time()}
    return data

# =============================
# Docker Tools
# =============================
@mcp.tool()
def docker_list_containers():
    cli = docker_client()
    return [c.name for c in cli.containers.list()]

@mcp.tool()
def docker_restart(name: str):
    cli = docker_client()
    container = cli.containers.get(name)
    container.restart()
    return f"✅ Restarted {name}"

@mcp.tool()
def docker_build(path: str, tag: str):
    def _build():
        cli = docker_client()
        cli.images.build(path=path, tag=tag)
    threading.Thread(target=_build).start()
    return f"⚡ Docker build for {tag} started in background"

@mcp.tool()
def docker_run(image: str, name: str = None, detach: bool = True):
    def _run():
        cli = docker_client()
        cli.containers.run(image, name=name, detach=detach)
    threading.Thread(target=_run).start()
    return f"⚡ Docker container {image} started in background"

@mcp.tool()
def docker_stop(name: str):
    cli = docker_client()
    container = cli.containers.get(name)
    container.stop()
    return f"🛑 Stopped {name}"

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

# =============================
# Kubernetes Tools
# =============================
@mcp.tool()
def k8s_list_namespaces():
    return cached_k8s_fetch(
        kind="namespaces",
        fetch_func=lambda ns: [n.metadata.name for n in client.CoreV1Api().list_namespace().items]
    )

@mcp.tool()
def k8s_list_pods(namespace: str = None):
    return cached_k8s_fetch(
        kind="pods",
        namespace=namespace,
        fetch_func=lambda ns: [p.metadata.name for p in client.CoreV1Api().list_namespaced_pod(ns).items]
    )

@mcp.tool()
def k8s_list_deployments(namespace: str = None):
    return cached_k8s_fetch(
        kind="deployments",
        namespace=namespace,
        fetch_func=lambda ns: [d.metadata.name for d in client.AppsV1Api().list_namespaced_deployment(ns).items]
    )

@mcp.tool()
def k8s_scale_deployment(name: str, replicas: int, namespace: str = None):
    def _scale():
        ns = namespace or load_kube()
        body = {"spec": {"replicas": replicas}}
        client.AppsV1Api().patch_namespaced_deployment_scale(name, ns, body)
    threading.Thread(target=_scale).start()
    return f"⚡ Scaling deployment {name} triggered in background"

# =============================
# Helm Tools
# =============================
def run_helm_cmd(cmd: str):
    return run_cmd(f"helm {cmd}")

@mcp.tool()
def helm_list(namespace: str = None):
    ns_flag = f"-n {namespace}" if namespace else "--all-namespaces"
    return run_helm_cmd(f"list {ns_flag}")

@mcp.tool()
def helm_install(release: str, chart: str, namespace: str = "default"):
    def _install():
        run_helm_cmd(f"install {release} {chart} -n {namespace} --create-namespace")
    threading.Thread(target=_install).start()
    return f"⚡ Helm install {release} triggered in background"

@mcp.tool()
def helm_upgrade(release: str, chart: str, namespace: str = "default"):
    def _upgrade():
        run_helm_cmd(f"upgrade {release} {chart} -n {namespace}")
    threading.Thread(target=_upgrade).start()
    return f"⚡ Helm upgrade {release} triggered in background"

@mcp.tool()
def helm_uninstall(release: str, namespace: str = "default"):
    def _uninstall():
        run_helm_cmd(f"uninstall {release} -n {namespace}")
    threading.Thread(target=_uninstall).start()
    return f"⚡ Helm uninstall {release} triggered in background"

# =============================
# Selenium Tool
# =============================
@mcp.tool()
def run_selenium_test(url: str):
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    title = driver.title
    driver.quit()
    return f"🌐 Page title: {title}"

# =============================
# Python Runner Tool
# =============================
@mcp.tool()
def run_python_script(script: str):
    result = subprocess.run(["python", "-c", script], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else result.stderr

# =============================
# File Tools
# =============================
@mcp.tool()
def read_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@mcp.tool()
def write_file(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        return f"✅ File {path} updated."

# =============================
# Cluster Overview
# =============================
@mcp.tool()
def cluster_overview():
    ns = load_kube()
    v1 = client.CoreV1Api()
    apps = client.AppsV1Api()
    cli = docker_client()

    namespaces = [n.metadata.name for n in v1.list_namespace().items]
    pods = [p.metadata.name for p in v1.list_namespaced_pod(ns).items]
    deployments = [d.metadata.name for d in apps.list_namespaced_deployment(ns).items]
    containers = [c.name for c in cli.containers.list()]

    return (
        f"🌍 Minikube Status:\n{run_cmd('minikube status')}\n\n"
        f"📂 Active Namespace: {ns}\n"
        f"📂 All Namespaces: {', '.join(namespaces)}\n\n"
        f"🐳 Pods in {ns}: {', '.join(pods) if pods else '(none)'}\n"
        f"📦 Deployments in {ns}: {', '.join(deployments) if deployments else '(none)'}\n\n"
        f"🐋 Docker Containers: {', '.join(containers) if containers else '(none)'}"
    )

# =============================
# Run MCP Server
# =============================
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
