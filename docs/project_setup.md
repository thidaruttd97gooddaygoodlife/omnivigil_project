# OmniVigil Project Setup (System Skeleton)
เอกสารนี้เป็นโครงรวมของระบบ เพื่อให้เปิดโปรเจกต์แล้วเห็นภาพชัดและต่อยอดได้ทันที

## 1) Business Impact
- ลด Unplanned Downtime เป้าหมาย 20-30%
- ลดการซ่อมเกินจำเป็นด้วยการใช้ข้อมูลจริง
- เปลี่ยนข้อมูลเซนเซอร์เป็นมูลค่าเชิงธุรกิจ

## 2) Service Order (มาตรฐานใหม่)
| MS | Service Folder | หน้าที่หลัก |
|---|---|---|
| MS1 | `ms1-auth` | Login, JWT, Role Authorization, Resource Stats |
| MS2 | `ms2-ingestor` | รับ/clean telemetry และเก็บ InfluxDB |
| MS3 | `ms3-ai-engine` | วิเคราะห์ anomaly/risk ด้วย Chronos ML |
| MS4 | `ms4-alert` | แจ้งเตือนผ่าน LINE Flex Message/UI |
| MS5 | `ms5-maintenance` | จัดการ work order และประวัติซ่อม |
| MS6 | `ms6-machine` | ทะเบียนประวัติและสเตตัสสุขภาพเครื่องจักร |

## 3) Infrastructure
- MQTT (Mosquitto)
- InfluxDB (Telemetry)
- Redis (Cache & Celery Queue)
- RabbitMQ (Event Bus)
- PostgreSQL Auth
- PostgreSQL Maintenance
- **Kong API Gateway** (Central Ingress Router)
- **Prometheus** (Metrics Scraper)
- **Grafana** (Metrics Visualizer Dashboard)

## 4) Run System
```bash
docker compose --profile simulator up -d --build
```

Swagger API Docs (ผ่าน Kong API Gateway พอร์ต 8000):
- MS1 Auth: `http://localhost:8000/auth-service/docs`
- MS2 Ingestor: `http://localhost:8000/ingestor-service/docs`
- MS3 AI Engine: `http://localhost:8000/ai-service/docs`
- MS4 Alert: `http://localhost:8000/alert-service/docs`
- MS5 Maintenance: `http://localhost:8000/maintenance-service/docs`
- MS6 Machine: `http://localhost:8000/machine-service/docs`

## 5) Coding Baseline
- ใช้กฎเดียวกันที่ `CONTRIBUTING.md`
- ใช้มาตรฐานไฟล์จาก `.editorconfig`
- endpoint/contract ใหม่ต้องอัปเดต `docs/openapi.md` และ `docs/contracts/*`

## 6) What is intentionally left for next implementation
- logic AI model จริง
- event pipeline RabbitMQ แบบ production
- database migrations
- automated test/CI pipeline