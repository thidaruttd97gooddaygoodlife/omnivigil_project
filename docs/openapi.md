# OmniVigil API Gateway Overview

ทุก ๆ API Service ของโปรเจกต์จะถูกจัดเส้นทาง (Route) และควบคุมการเข้าถึงด้วย **Kong API Gateway** โดยมีพอร์ตหลักในการเข้าถึงคือ `http://localhost:8000`

---

## 🔗 เส้นทางการเรียกใช้ API ผ่าน Gateway (Base URLs)

| บริการ (Microservice) | เส้นทางเกตเวย์ (Proxy Endpoint) | เอกสารเปิดเผย (Swagger Docs) | พอร์ตตรงหลังบ้าน (หลีกเลี่ยงการใช้ตรง) |
| :--- | :--- | :--- | :--- |
| **MS1 Auth** | `http://localhost:8000/auth-service` | `/auth-service/docs` | `http://localhost:8001` |
| **MS2 Ingestor** | `http://localhost:8000/ingestor-service` | `/ingestor-service/docs` | `http://localhost:8002` |
| **MS3 AI Engine** | `http://localhost:8000/ai-service` | `/ai-service/docs` | `http://localhost:8003` |
| **MS4 Alert** | `http://localhost:8000/alert-service` | `/alert-service/docs` | `http://localhost:8004` |
| **MS5 Maintenance** | `http://localhost:8000/maintenance-service` | `/maintenance-service/docs` | `http://localhost:8005` |
| **MS6 Machine** | `http://localhost:8000/machine-service` | `/machine-service/docs` | `http://localhost:8006` |

*หมายเหตุ: Swagger UI และ OpenAPI specification ของทุกตัวยังเปิดใช้งานปกติผ่าน Path `/docs` ต่อจากเส้นทางของ API Gateway เช่น `http://localhost:8000/auth-service/docs`*

---

## 🛠️ รายการ Endpoint หลักของแต่ละบริการ

### 1. MS1 Auth (การตรวจสอบสิทธิ์และโทเค็น)
* `GET /health` - ตรวจสอบความพร้อมใช้งาน
* `POST /auth/login` - ล็อกอินรับสิทธิ์ (จำกัดความถี่ด้วย Rate Limiting ที่ 60 ครั้งต่อนาที)
* `GET /auth/verify` - ตรวจสอบความถูกต้องของ JWT Token
* `GET /auth/me` - ดึงประวัติส่วนตัวผู้ใช้ปัจจุบัน
* `GET /docker/stats` - ดึงสถิติคอมพิวเตอร์และตัวคอนเทนเนอร์ (ผ่าน Docker socket)

### 2. MS2 Ingestor (การดึงข้อมูลเซ็นเซอร์)
* `GET /health` - ตรวจสอบความพร้อมใช้งาน
* `POST /ingest` - รับข้อมูลจากเซ็นเซอร์ (ผ่าน HTTP POST)
* `POST /ingest/analyze` - รับค่า สรุป และโยนต่อให้ AI ประเมินผล
* `GET /readings` - เรียกประวัติสถิติเซ็นเซอร์ในระบบ

### 3. MS3 AI Engine (สมองกลวิเคราะห์ความเสี่ยง)
* `GET /health` - ตรวจสอบความพร้อมใช้งาน
* `POST /analyze` - รับข้อมูลเซ็นเซอร์จำลองเพื่อวิเคราะห์ประเมินแบบทันทีและ Celery Chronos Forecast
* `GET /predict/event` - ดึงประวัติการคาดการณ์ล่าสุดจากฐานข้อมูลหรือ Redis stream

### 4. MS4 Alert (ระบบจัดส่งแจ้งเตือน)
* `GET /health` - ตรวจสอบความพร้อมใช้งาน
* `POST /alerts` - รับเรื่องความเสี่ยง สร้าง Rich Anomaly Flex Card และส่งเข้า LINE Bot API
* `GET /alerts` - ดูประวัติการแจ้งเตือน
* `GET /alerts/{alert_id}` - ดึงรายละเอียดแจ้งเตือนเฉพาะรหัส

### 5. MS5 Maintenance (ระบบใบสั่งซ่อมบำรุง)
* `GET /health` - ตรวจสอบความพร้อมใช้งาน
* `POST /work-orders` - เปิดใบสั่งซ่อมบำรุง
* `GET /work-orders` - ดึงรายการใบสั่งซ่อมบำรุงทั้งหมด (กรองตามความเร่งด่วน/สถานะ)
* `PATCH /work-orders/{work_order_id}/status` - ปรับปรุงสถานะซ่อมแซม (เช่น open -> acknowledged -> in_progress -> completed)

### 6. MS6 Machine (ทะเบียนประวัติเครื่องจักร)
* `GET /health` - ตรวจสอบความพร้อมใช้งาน
* `GET /machines` - แสดงรายการเครื่องจักรทั้งหมดพร้อมค่าพลังชีวิต (Health Score)
* `PUT /machines/{machine_id}` - ปรับปรุงแก้ไขเครื่องจักร
