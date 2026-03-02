# OmniVigil API Overview (Stub)

Base URLs (default):
- MS1 Ingestor: http://localhost:8001
- MS2 AI Engine: http://localhost:8002
- MS3 Alert: http://localhost:8003
- MS4 Maintenance: http://localhost:8004

Each service exposes Swagger UI at /docs and OpenAPI JSON at /openapi.json.

## MS1 Ingestor
- GET /health
- POST /ingest
- POST /ingest/analyze
- POST /simulate/batch
- POST /simulate/fail
- GET /readings

## MS2 AI Engine
- GET /health
- POST /analyze
- GET /events
- POST /models/refresh

## MS3 Alert
- GET /health
- POST /alerts
- GET /alerts
- GET /alerts/{alert_id}

## MS4 Maintenance
- GET /health
- POST /work-orders
- GET /work-orders
- GET /work-orders/{work_order_id}
- PATCH /work-orders/{work_order_id}/ack
