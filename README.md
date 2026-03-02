# OmniVigil: Cloud-Native Industrial IoT & Predictive Intelligence

## Quick Runbook 

### 0) เช็กก่อนรัน
1. เปิด Docker Desktop ให้ขึ้นสถานะ Running
2. สร้างไฟล์ env จาก template:

```powershell
Copy-Item .env.example .env
```

### 1) รันระบบครั้งแรก
```bash
docker compose up -d --build
```

โหมดนี้จะไม่ทำให้ terminal รก (รันแบบ background)

ถ้าต้องการรันตัวจำลอง sensor ด้วย ให้ใช้:
```bash
docker compose --profile simulator up -d --build
```

### 2) ตรวจว่า service ขึ้นครบ
- MS1 Auth: http://localhost:8001/docs
- MS2 Ingestor: http://localhost:8002/docs
- MS3 AI Engine: http://localhost:8003/docs
- MS4 Alert: http://localhost:8004/docs
- MS5 Maintenance: http://localhost:8005/docs

### 3) ถ้าแก้โค้ดแล้วอยากรันต่อ
รันเฉพาะ service ที่แก้ (ตัวอย่างแก้ AI Engine):
```bash
docker compose up -d --build ms3-ai-engine
docker compose logs -f ms3-ai-engine
```

### 4) คำสั่งที่ใช้บ่อย
```bash
docker compose ps
docker compose logs -f ms3-ai-engine
docker compose logs --tail=80
docker compose down
```

ดูเฉพาะ error/warn (PowerShell):
```powershell
docker compose logs --tail=200 | Select-String "ERROR|WARN|CRITICAL"
```

### 5) กรณีข้อมูลค้าง/พังหนัก ให้รีเซ็ตทั้งหมด
```bash
docker compose down -v
docker compose up -d --build
```

### 6) ถ้า image/container รก
```bash
docker compose down --remove-orphans
docker image prune -f
docker container prune -f
```

หมายเหตุ: คำสั่งข้างบนลบเฉพาะของที่ไม่ใช้งานแล้ว

## Project Setup Baseline (Team Handoff)
- มาตรฐานทีม: `CONTRIBUTING.md`
- Project setup blueprint: `docs/project_setup.md`
- สถาปัตยกรรม: `docs/architecture.md`
- API ภาพรวม: `docs/openapi.md`
- Production checklist: `docs/production_checklist.md`

### Current Microservices in this repository
- `services/ms1-auth` : login/JWT/role authorization
- `services/ms2-ingestor` : IoT ingestion + data cleaning + InfluxDB write
- `services/ms3-ai-engine` : anomaly scoring + risk decision
- `services/ms4-alert` : notification dispatch (LINE/UI channels)
- `services/ms5-maintenance` : work order lifecycle

## 1) ที่มาและความสำคัญ
ในโรงงานอุตสาหกรรม ปัญหาที่กระทบต้นทุนสูงสุดคือ "เครื่องจักรเสียกะทันหัน" (Unplanned Downtime) เพียงมอเตอร์ตัวเดียวหยุด อาจทำให้สายการผลิตหยุดชะงักและเสียหายหลักล้านบาทต่อชั่วโมง
OmniVigil เปลี่ยนแนวคิดจาก "เสียแล้วค่อยซ่อม" เป็น "รู้ก่อนเสีย" ด้วยการนำข้อมูลเซนเซอร์ (อุณหภูมิ, ความสั่น) ขึ้นคลาวด์ให้ AI วิเคราะห์และแจ้งเตือนก่อนเกิดเหตุจริง

## 2) ฟีเจอร์หลัก
- Real-time Monitoring: เฝ้าดูสถานะเครื่องจักรผ่าน Dashboard ตลอด 24 ชั่วโมง
- AI Anomaly Detection: ตรวจจับสัญญาณผิดปกติเล็กๆ ที่คนมองไม่เห็น เพื่อเตือนล่วงหน้า
- Automated Ticketing: แจ้งเตือนเข้า LINE ของช่าง พร้อมออกใบสั่งซ่อมอัตโนมัติ
- Health Dashboard: สรุปสุขภาพทั้งเครื่องจักรและระบบคอมพิวเตอร์ในจอเดียว

## 3) โครงสร้างระบบ (Architecture) และ Data Flow
สถาปัตยกรรมแบบ Microservices เพื่อความยืดหยุ่นและเสถียร

### Data Flow
1. Authentication: MS1 (Auth Service) ตรวจสิทธิ์ผู้ใช้และออก JWT
2. Data Ingestion: MS2 (IoT Ingestor) รับข้อมูลจากเซนเซอร์และทำความสะอาดข้อมูล
3. AI Processing: MS3 (AI Engine) วิเคราะห์โอกาสความผิดปกติ
4. Alert Dispatch: MS4 (Alert Service) ส่งแจ้งเตือนตาม channel
5. Work Order: MS5 (Maintenance Service) บันทึกงานซ่อมและสถานะ

โครงสร้างข้อมูลหลัก:
1. Time-series Storage: InfluxDB สำหรับเก็บข้อมูลจำนวนมากที่ไหลเข้ารวดเร็ว
2. Fast Cache: Redis สำหรับผลลัพธ์ที่ต้องแสดงแบบเรียลไทม์
3. Event-Driven: RabbitMQ เป็นตัวกลางส่งเหตุการณ์ผิดปกติอย่างปลอดภัย
4. Relational Storage: PostgreSQL แยก Auth DB และ Maintenance DB

## 4) บทบาทสมาชิก
- PO & Lead DevOps: วางโครงสร้างระบบคลาวด์ (Kubernetes) และ CI/CD
- AI/Data Scientist: พัฒนาโมเดล AI และระบบกรองข้อมูล
- Backend Dev (Data): พัฒนาระบบรับส่งข้อมูลเซนเซอร์
- Backend Dev (Logic): พัฒนาระบบแจ้งเตือนและงานซ่อมบำรุง
- Frontend Dev: สร้าง Dashboard ที่ใช้งานง่ายและสวยงาม
- QA & Integration: ทดสอบการทำงานร่วมกันของทุกระบบ

## 5) ประโยชน์ที่ได้รับ
- ธุรกิจ: ลดความเสียหายจากการหยุดผลิตได้ถึง 30% และยืดอายุเครื่องจักร
- นักศึกษา: ได้เรียนรู้เทคโนโลยีระดับโลก เช่น Kubernetes, AI Ops, Microservices

## 6) สิ่งที่ทำให้งานโดดเด่น
- End-to-End: เห็นตั้งแต่ข้อมูลดิบ → AI Score → แจ้งเตือนผู้ใช้
- Immersive: มีเสียงเตือนและ Pop-up แบบ OS ทำให้งานดูมีชีวิต
- Cloud-Native: แสดงสถานะ Microservices และ K8s Pods ใน Dashboard

## 7) แนวทางการนำเสนอ (Demo Flow)
- เริ่มจากหน้า Dashboard สถานะปกติ (Healthy)
- กดปุ่ม Simulate Fail ให้กราฟพุ่ง
- ชี้ให้เห็นการแจ้งเตือน (เสียง/Toast/LINE จำลอง)
- สรุปว่าระบบตรวจจับได้ก่อนเกิดเหตุจริง

## 8) Real-world Notification Features (Mockup)
- OS Toast Notification (มุมขวาบน)
- Mobile UI Simulator (LINE Notify) พร้อมปุ่ม Action
- Sound Alert (เปิด/ปิดได้)
- Haptic/Visual Feedback (พื้นหลัง Pulse เมื่อ Critical)
- Service Health Status (แสดงสถานะของ Microservices)

## 9) แนวคิด AI/ML ระดับสูงสำหรับ Predictive Maintenance
### 9.1 Hybrid Deep Learning Model
- Bi-Directional LSTM: จับความสัมพันธ์เชิงเวลาได้แม่นยำ
- Autoencoder: เรียนรู้ภาวะปกติและตรวจจับความผิดปกติจาก Reconstruction Error
- FFT + CNN: แปลงสั่นสะเทือนเป็น Frequency Domain เพื่อหา Failure Signature
- RUL Estimation: พยากรณ์อายุการใช้งานที่เหลืออยู่

### 9.2 Unsupervised Anomaly Detection
- Clustering (DBSCAN/K-Means++): แยกกลุ่มปกติและจับ outliers
- Isolation Forest: แยกข้อมูลผิดปกติแบบเร็วและแม่นยำในมิติสูง

### 9.3 Optimization & Control
- PSO (Particle Swarm Optimization): ปรับจูน Hyperparameters เร็วกว่า GA
- Reinforcement Learning (PPO/DQN): ใช้ในการตัดสินใจเชิงควบคุมอัตโนมัติ

## 10) สรุปคอมโบโมเดลระดับ Doctor
Bi-LSTM + PSO + Isolation Forest เป็นชุดที่ให้ความแม่นยำและทันสมัยที่สุด
เหมาะสำหรับงาน Predictive Maintenance แบบ Cloud-Native ที่ต้องการทั้งความเร็วและความน่าเชื่อถือ

---

# OmniVigil Backend Stubs (FastAPI)

## Repo Structure
- services/ms1-auth: จัดการ login/JWT/role
- services/ms2-ingestor: รับข้อมูล Telemetry และทำความสะอาด
- services/ms3-ai-engine: ประเมินความเสี่ยงและคะแนนความผิดปกติ
- services/ms4-alert: ส่งแจ้งเตือน (LINE/Toast/Sound) แบบจำลอง
- services/ms5-maintenance: จัดการใบสั่งซ่อมแบบจำลอง
- docs/contracts: ตัวอย่าง JSON สำหรับแต่ละบริการ
- docs/openapi.md: สรุปเส้นทาง API

## Run (Docker Compose)
1) ติดตั้ง Docker Desktop
2) รันคำสั่ง:

```bash
docker compose up --build
```

บริการจะเปิดที่:
- MS1 Auth: http://localhost:8001/docs
- MS2 Ingestor: http://localhost:8002/docs
- MS3 AI Engine: http://localhost:8003/docs
- MS4 Alert: http://localhost:8004/docs
- MS5 Maintenance: http://localhost:8005/docs

## Run (Local)
ติดตั้ง Python 3.11+ แล้วรันทีละ service:

```bash
cd services/ms2-ingestor
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```

ทำซ้ำกับ service อื่นตามลำดับพอร์ต 8001 ถึง 8005

## Sample Payloads
ดูไฟล์ตัวอย่างที่:
- docs/contracts/telemetry.json
- docs/contracts/anomaly_request.json
- docs/contracts/alert_request.json
- docs/contracts/work_order_request.json

---

# OmniVigil Frontend Dashboard (React)

## Setup
```bash
cd frontend
npm install
npm run dev
```

เปิดใช้งานที่ http://localhost:5173

## Pipeline Demo
- กดปุ่ม "Simulate Batch" เพื่อสร้าง Telemetry หลายจุด
- กดปุ่ม "Simulate Fail" เพื่อยิงเหตุการณ์ระดับ Critical
- ระบบจะไหลผ่าน MS2 -> MS3 -> MS4 -> MS5 และแสดงผลใน UI

---

# Real-time Sensor Simulation (Free, Cloud-Native)

## What you get
- MQTT Broker จริง (Mosquitto)
- Sensor Simulator ส่งข้อมูลตามเวลาเข้า MQTT
- MS2 Subscribe MQTT แล้วเขียนลง InfluxDB

## Run
```bash
docker compose up --build
```

## MQTT Settings
ค่าอยู่ใน docker-compose.yml
- MQTT_BROKER: mosquitto
- MQTT_TOPIC: omnivigil/telemetry
- INTERVAL_MS: 5000
- ANOMALY_RATE: 0.04

Simulator defaults:
- MACHINE_COUNT: 5
- NETWORK_DROP_RATE: 0.03
- NETWORK_DROP_DURATION_SEC: 8
- MANUAL_TRIGGER_FILE: /tmp/force_anomaly

Default machine IDs:
- mix-pump-101
- filling-comp-201
- cnc-spindle-301
- boiler-feed-401
- pack-conveyor-501

Manual trigger anomaly (container):
```bash
docker compose exec sim-sensor sh -c 'echo all > /tmp/force_anomaly'
```

Manual trigger เฉพาะเครื่อง:
```bash
docker compose exec sim-sensor sh -c 'echo cnc-spindle-301 > /tmp/force_anomaly'
```

ตรวจ ingest metrics:
```bash
curl http://localhost:8002/stats
```


