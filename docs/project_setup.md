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
- RabbitMQ (Event Bus)
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
- event pipeline RabbitMQ แบบ production
- database migrations
- automated test/CI pipeline