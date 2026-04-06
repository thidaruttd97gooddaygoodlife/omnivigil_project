# MS3 AI Engine

Distributed AI service for anomaly scoring and risk evaluation using time-series forecasting.

## Architecture
This service is split into two components to handle heavy ML inference efficiently:
1.  **Web API (FastAPI)**: A lightweight frontend that accepts telemetry, calculates immediate threshold-based scores, and offloads heavy forecasting tasks to the worker pool.
2.  **Worker Pool (Celery)**: Dedicated processes that load the ML models (Chronos) and perform compute-intensive inference.

## Infrastructure Requirements
- **Redis**: Used as the message broker and result backend for Celery.
- **GPU (Optional but Recommended)**: The worker uses CUDA if available for faster inference.

## Endpoints
- `GET /health`: Service health status and operational mode (web/worker).
- `POST /analyze`: Main inference endpoint. Triggers background forecasting and returns risk levels.
- `GET /events`: Retrieval of recent high-risk anomaly events.
- `POST /models/refresh`: Stub for reloading/refreshing ML models.

## File Structure & Descriptions

### Core Application (`app/`)
-   **`main.py`**: The entry point for the FastAPI web server. It handles HTTP requests, provides the `/analyze` and `/health` endpoints, and coordinates the immediate risk assessment logic. It dispatches heavy ML tasks to the Celery worker pool and awaits results asynchronously.
-   **`celery_app.py`**: Configures the Celery instance. It defines the Redis broker and backend connection strings and sets up task serialization and time limits.
-   **`tasks.py`**: Houses the Celery task definitions. This file is loaded by the worker processes. It contains the logic for loading the Chronos model (using `BaseChronosPipeline`) and performing the actual time-series forecasting on resampled telemetry data.
-   **`worker.py`**: A utility module containing the standalone inference logic and model loading helpers. It serves as a shared logic base and can be used for direct local testing outside of the Celery environment.

### Project Metadata
-   **`Dockerfile`**: Defines the container image for both the Web API and the Worker. The behavior is toggled via the `command` in `docker-compose.yml`.
-   **`requirements.txt`**: Lists all dependencies, including heavy ML libraries like `torch` and `chronos-forecasting`, alongside infrastructure tools like `celery` and `redis`.

## ML Model
- **Engine**: [Chronos Forecasting](https://github.com/amazon-science/chronos-forecasting)
- **Model**: `Stalemartyr/chronos-finetuned`
- **Logic**: Predicts future telemetry values (temperature, vibration, RPM) to calculate a proactive anomaly score based on predicted trends.

## Development
To run the worker locally:
```bash
celery -A app.celery_app worker --loglevel=info
```
To run the web server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8003
```
