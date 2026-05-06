# MS4 Alert

MS4 is an alert consumer service.

## What it does
- Subscribes to Redis Pub/Sub channel `anomaly_detected`
- Converts anomaly events to alert records
- Stores full alert audit in PostgreSQL table `alert_audit`
- Exposes query APIs for frontend and operations teams

## Endpoints
- `GET /health`
- `POST /alerts` (manual alert creation for compatibility/testing)
- `GET /alerts`
- `GET /alerts/{alert_id}`

## Required ENV
- `ALERT_POSTGRES_URL`
- `REDIS_URL`
- `REDIS_EVENT_CHANNEL` (default: `anomaly_detected`)
