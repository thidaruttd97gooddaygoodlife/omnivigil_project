# MS5 Maintenance

MS5 manages maintenance work orders and supports both API and event-driven creation.

## What it does
- Stores work orders in PostgreSQL
- Consumes Redis events from channel `anomaly_detected`
- Auto-creates work orders when `anomaly_score > AUTO_CREATE_THRESHOLD`
- Requires JWT verification for frontend-facing APIs

## Endpoints
- `GET /health`
- `POST /work-orders`
- `GET /work-orders`
- `GET /work-orders/{order_id}`
- `PATCH /work-orders/{order_id}/accept`
- `PATCH /work-orders/{order_id}/complete`

## Required ENV
- `POSTGRES_URL`
- `MS1_AUTH_URL`
- `REDIS_URL`

## Optional ENV
- `REDIS_EVENT_CHANNEL` (default: `anomaly_detected`)
- `AUTO_CREATE_THRESHOLD` (default: `0.9`)
- `INTERNAL_SERVICE_KEY` (internal bypass for service-to-service calls)
