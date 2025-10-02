from fastmcp import FastMCP
import docker
from kubernetes import client, config
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import subprocess

mcp = FastMCP("DevOps Tools")

@mcp.tool()
def docker_list_containers():
    client = docker.from_env()
    return [c.name for c in client.containers.list()]

@mcp.tool()
def docker_restart(name: str):
    client = docker.from_env()
    container = client.containers.get(name)
    container.restart()
    return f"Restarted {name}"

@mcp.tool()
def k8s_list_pods(namespace: str = "default"):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace)
    return [p.metadata.name for p in pods.items]

@mcp.tool()
def k8s_scale_deployment(name: str, replicas: int, namespace: str = "default"):
    config.load_kube_config()
    apps_v1 = client.AppsV1Api()
    body = {"spec": {"replicas": replicas}}
    apps_v1.patch_namespaced_deployment_scale(name, namespace, body)
    return f"Scaled {name} to {replicas}"

@mcp.tool()
def run_selenium_test(url: str):
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    title = driver.title
    driver.quit()
    return f"Page title: {title}"

@mcp.tool()
def run_python_script(script: str):
    result = subprocess.run(["python3", "-c", script], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else result.stderr

if __name__ == "__main__":
    # Use HTTP transport so it can run as a server
    mcp.run(transport="http", host="0.0.0.0", port=8000)
