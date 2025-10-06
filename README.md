# MCP (DevOps Tools)

This repository runs a small MCP (Multi-Chat Plugin) server exposing DevOps tools (minikube, kubectl, docker, terraform, git, playwright).

## Goals
- Provide local devops tooling over MCP protocol
- Allow safe shell operations for admins (whitelisted)
- Work well on Windows with Docker Desktop + Minikube (docker driver)

## Prerequisites
- Windows 10/11
- Docker Desktop (running)
- Minikube (installed) - optional: `choco install minikube` or download from https://minikube.sigs.k8s.io/
- Node + npm (for npx servers used by MCP clients)
- Python 3.11, virtualenv

## Quickstart (local)
```powershell
# create venv and install
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# run server
python server.py
```

## Useful commands (PowerShell)
```powershell
# Docker
docker version
docker ps -a

# Minikube
minikube start --driver=docker
minikube status
minikube kubectl -- get namespaces

# MCP tools (via HTTP client or mcp-cli)
# - start minikube: call minikube_start()
# - stop minikube: call minikube_stop()
# - check namespaces: call kubectl(args="get namespaces")
# - run whitelisted shell: call run_shell(cmd="docker ps")
```

## Security
- `run_shell` is intentionally whitelisted and rejects pipes/redirections. Do not expand without considering risk.
