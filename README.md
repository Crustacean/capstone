# Release Dashboard

A small Python DevOps portfolio project for tracking and promoting releases through `sandbox`, `dev`, `uat`, and `prod`.

The app gives you a working dashboard plus the delivery artifacts around it: Docker image build, Jenkins pipeline, Kubernetes manifests, health checks, and environment-specific scaling.

## Features

- FastAPI web dashboard and JSON API
- SQLite deployment history
- Release promotion flow: sandbox -> dev -> uat -> prod
- Dockerfile for local or CI image builds
- Jenkins pipeline with install, test, image build, and gated promotions
- Kubernetes base manifests plus sandbox/dev/uat/prod overlays
- HPA settings that differ by environment

## Run Locally

On Debian/Ubuntu, install Python packaging support first if needed:

```bash
sudo apt-get install python3-venv python3-pip
```

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## API Examples

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/deployments
curl -X POST http://127.0.0.1:8000/deployments \
  -H 'Content-Type: application/json' \
  -d '{"version":"v1.0.0","actor":"jenkins"}'
curl -X POST 'http://127.0.0.1:8000/promote/sandbox?actor=jenkins'
```

## Test

```bash
pytest
```

## Jenkins Agent Prerequisite

The `Jenkinsfile` uses the Jenkins agent's `python3`. The dependency pins are kept on versions that support Python 3.14, because the current Jenkins agent reports CPython 3.14.

The Docker image also uses Python 3.14 so local containers and Jenkins builds stay aligned.

## Build Image

```bash
docker build -t release-dashboard:local .
docker run --rm -p 8000:8000 release-dashboard:local
```

## Kubernetes

Render an environment with Kustomize:

```bash
kubectl kustomize k8s/sandbox
kubectl apply -k k8s/sandbox
```

Create namespaces first if your cluster does not already have them:

```bash
kubectl create namespace sandbox
kubectl create namespace dev
kubectl create namespace uat
kubectl create namespace prod
```

## Portfolio Story

This project demonstrates that you can build a Python service and design the release path around it: automated checks, container delivery, staged environments, promotion gates, health probes, and Kubernetes scaling.
