# OmniVigil Project Setup (System Skeleton)
เอกสารนี้เป็นโครงรวมของระบบ เพื่อให้เปิดโปรเจกต์แล้วเห็นภาพชัดและต่อยอดได้ทันที

## 1) Business Impact
- ลด Unplanned Downtime เป้าหมาย 20-30%
- ลดการซ่อมเกินจำเป็นด้วยการใช้ข้อมูลจริง
- เปลี่ยนข้อมูลเซนเซอร์เป็นมูลค่าเชิงธุรกิจ

## 2) Service Order (มาตรฐานใหม่)
| MS | Service Folder | หน้าที่หลัก |
|---|---|---|
| MS1 | `ms1-auth` | Login, JWT, Role Authorization |
| MS2 | `ms2-ingestor` | รับ/clean telemetry และเก็บ InfluxDB |
| MS3 | `ms3-ai-engine` | วิเคราะห์ anomaly/risk |
| MS4 | `ms4-alert` | แจ้งเตือนผ่าน LINE/UI |
| MS5 | `ms5-maintenance` | จัดการ work order และประวัติซ่อม |

## 3) Infrastructure
- MQTT (Mosquitto)
- InfluxDB (Telemetry)
- Redis (Cache)
- PostgreSQL Auth
- PostgreSQL Maintenance

## 4) Run System
```bash
docker compose up --build
```

Swagger ของแต่ละ service:
- MS1: `http://localhost:8001/docs`
- MS2: `http://localhost:8002/docs`
- MS3: `http://localhost:8003/docs`
- MS4: `http://localhost:8004/docs`
- MS5: `http://localhost:8005/docs`

## 5) Coding Baseline
- ใช้กฎเดียวกันที่ `CONTRIBUTING.md`
- ใช้มาตรฐานไฟล์จาก `.editorconfig`
- endpoint/contract ใหม่ต้องอัปเดต `docs/openapi.md` และ `docs/contracts/*`

## 6) What is intentionally left for next implementation
- logic AI model จริง
- production-grade internal event bus (if needed in later phase)
- database migrations
- automated test/CI pipeline

## 7) Inter-Service Setup Contract (Current Runtime)

### Layer 1: Sim Sensor -> MQTT
- Sim Sensor publishes every 1-5 seconds by default (`INTERVAL_OPTIONS_SEC=1,2,3,4,5`).
- Telemetry uses Gaussian noise and injects explicit outliers for robustness tests.
- MQTT publish uses QoS 1 to support at-least-once delivery.
- Packet contract:

```json
{
	"device_id": "pump-01",
	"ts": "2026-04-29T10:00:00Z",
	"metrics": {
		"temperature_c": 85.0,
		"vibration_rms": 2.1,
		"rpm": 1490.0
	}
}
```

### Layer 2: MS2 Ingestor (MQTT + Dual-Write)
- MS2 subscribes `omnivigil/telemetry` in Paho callback thread.
- Callback only enqueues payload into internal buffer queue.
- Background worker performs normalize -> validate -> clean -> score -> store.
- Validation: rejects payload when missing sensor fields > 30%.
- Clamping: applies engineering bounds (e.g. temperature 0-150 C).
- Dual-write:
	- InfluxDB batch write for persistent time-series storage.
	- Redis list hot-path: `RPUSH telemetry:device:<device_id>` + `LTRIM -5000 -1`.

### Layer 3: MS2 Redis -> MS3
- `POST /ingest/analyze` in MS2 slices latest 70 points from Redis first (`LRANGE -70 -1` behavior), memory fallback only if Redis unavailable.
- MS2 sends that window to MS3 `/analyze`.
- MS3 dispatches Celery tasks via Redis broker and worker consumes them.

### Layer 5: MS2 Redis -> Frontend
- Frontend reads telemetry from `GET /readings` on MS2.
- MS2 serves from Redis hot-path first, so dashboard reflects server-side latest state.
- Frontend now auto-attaches `Authorization: Bearer <token>` if token exists in:
	- `localStorage.omnivigil_access_token` (priority), or
	- `VITE_ACCESS_TOKEN`.

## 8) Readiness Status and Known Gaps

Ready now:
- Sim Sensor -> MQTT -> MS2 flow is aligned with the target architecture.
- MS2 Redis hot-path is wired for both MS3 windowing and Frontend reads.
- Compose dependencies for Mosquitto/InfluxDB/Redis/PostgreSQL are consistent.

Not fully aligned yet (next step):
- MS3 `/analyze` currently waits for Celery results and returns normal response.
- Target architecture expects immediate `202 Accepted` fire-and-forget behavior.

Recommended follow-up for full alignment:
1. Split MS3 API into submit endpoint (`202`) and result/event retrieval endpoint.
2. Keep Celery worker as the only inference executor.
3. Publish final anomaly result via internal event channel (Redis Pub/Sub or dedicated bus).