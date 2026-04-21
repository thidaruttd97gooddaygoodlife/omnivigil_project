# Project Rules & Conventions

## General
- Architecture: Microservices with central MQTT broker (Mosquitto).
- Tech Stack: Python (FastAPI, Celery), React (Frontend), MQTT.
- AI Engine: ms3-ai-engine splits into FastAPI server + Celery worker.

## Development Workflow
- Follow TDD when possible.
- Use `agent-context-kit` for task tracking.
- Commit messages follow Conventional Commits.

## Service Catalog
Refer to `docs/service_catalog.yaml` for service definitions.
