# OmniVigil Engineering Rules

กติกาหลัก

## 1. Branch และ Commit
- Feature: `feat/<service>-<name>`
- Fix: `fix/<service>-<name>`
- ใช้ Conventional Commits เช่น `feat(ms2-ingestor): validate telemetry`

ตัวอย่าง:
- branch: `feat/ms3-ai-engine-anomaly-threshold`
- commit: `fix(ms4-alert): handle line api timeout`

## 2. ขอบเขตแต่ละ Service
- `ms1-auth`: auth/JWT
- `ms2-ingestor`: รับ+clean telemetry
- `ms3-ai-engine`: วิเคราะห์ anomaly
- `ms4-alert`: แจ้งเตือน
- `ms5-maintenance`: work order

ห้ามข้าม DB กันตรง ๆ ให้คุยกันผ่าน API/Event เท่านั้น

ตัวอย่าง:
- ถูก: `ms3-ai-engine` เรียก API ของ `ms5-maintenance` เพื่อเปิด work order
- ผิด: `ms3-ai-engine` ต่อ PostgreSQL ของ `ms5-maintenance` โดยตรง

## 3. เขียน API ให้เหมือนกัน
- ใช้ FastAPI + Pydantic
- endpoint ใช้รูปแบบสม่ำเสมอ เช่น `/work-orders`
- ถ้าเพิ่ม endpoint ให้ update `docs/openapi.md`

ตัวอย่าง:
- ถูก: `POST /work-orders`, `GET /work-orders/{id}`
- ผิด: `POST /createWorkOrder`, `GET /getWorkOrderById`

## 4. คุณภาพโค้ดขั้นต่ำ
- Python 3.11+, มี type hints
- ชื่อตัวแปรต้องสื่อความหมาย
- ห้าม hardcode secret (ใช้ env vars)

ตัวอย่าง:
- ถูก: `jwt_secret = os.getenv("JWT_SECRET")`
- ผิด: `jwt_secret = "my-secret-123"`

## 5. ก่อน Merge ต้องผ่าน
- health check ผ่าน
- contract ตัวอย่างใน `docs/contracts` อัปเดต
- README/service ที่แก้ อัปเดตตามจริง

ตัวอย่าง Checklist:
- [ ] `GET /health` ของ service ที่แก้ตอบ `status: ok`
- [ ] เพิ่ม/แก้ไฟล์ตัวอย่าง request-response ใน `docs/contracts`
- [ ] README ของ service มี endpoint ล่าสุด