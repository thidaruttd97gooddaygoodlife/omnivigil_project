# OmniVigil API Overview

Base URLs (default):
- MS1 Auth: http://localhost:8001
- MS2 Ingestor: http://localhost:8002
- MS3 AI Engine: http://localhost:8003
- MS4 Alert: http://localhost:8004
- MS5 Maintenance: http://localhost:8005

Each service exposes Swagger UI at /docs and OpenAPI JSON at /openapi.json.

## MS1 Auth
- GET /health
- POST /auth/login
- GET /auth/verify
- GET /auth/me
- GET /auth/authorize?required_role={role}

## MS2 Ingestor
- GET /health
- POST /ingest
- POST /ingest/analyze
- POST /simulate/batch
- POST /simulate/fail
- GET /readings

## MS3 AI Engine
- GET /health
- POST /analyze
- GET /events
- POST /models/refresh

## MS4 Alert
- GET /health
- POST /alerts
- GET /alerts
- GET /alerts/{alert_id}

## MS5 Maintenance
- GET /health
- POST /work-orders
- GET /work-orders
- GET /work-orders/{work_order_id}
- PATCH /work-orders/{work_order_id}/ack

## Auth Integration Policy
- Frontend ต้อง login ผ่าน `POST /auth/login` แล้วส่ง `Authorization: Bearer <token>`
- ทุก service ที่ต้องตรวจสิทธิ์ให้ verify token ผ่าน MS1
