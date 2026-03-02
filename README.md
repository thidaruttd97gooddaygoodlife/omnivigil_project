# OmniVigil: Cloud-Native Industrial IoT & Predictive Intelligence

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
1. Data Ingestion: MS1 (IoT Ingestor) รับข้อมูลจากเซนเซอร์และทำความสะอาดข้อมูล
2. Time-series Storage: InfluxDB สำหรับเก็บข้อมูลจำนวนมากที่ไหลเข้ารวดเร็ว
3. AI Processing: MS2 (AI Engine) วิเคราะห์โอกาสความผิดปกติ
4. Fast Cache: Redis สำหรับผลลัพธ์ที่ต้องแสดงแบบเรียลไทม์
5. Event-Driven: RabbitMQ เป็นตัวกลางส่งเหตุการณ์ผิดปกติอย่างปลอดภัย
6. Alert & Operation:
   - MS3 (Alert) ส่งแจ้งเตือนเข้า LINE
   - MS4 (Maintenance) บันทึกประวัติการซ่อม
7. Relational Storage: PostgreSQL เก็บประวัติการซ่อมและข้อมูลเชิงธุรกิจ

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
- services/ms1-ingestor: รับข้อมูล Telemetry และทำความสะอาด
- services/ms2-ai-engine: ประเมินความเสี่ยงและคะแนนความผิดปกติ
- services/ms3-alert: ส่งแจ้งเตือน (LINE/Toast/Sound) แบบจำลอง
- services/ms4-maintenance: จัดการใบสั่งซ่อมแบบจำลอง
- docs/contracts: ตัวอย่าง JSON สำหรับแต่ละบริการ
- docs/openapi.md: สรุปเส้นทาง API

## Run (Docker Compose)
1) ติดตั้ง Docker Desktop
2) รันคำสั่ง:

```bash
docker compose up --build
```

บริการจะเปิดที่:
- MS1: http://localhost:8001/docs
- MS2: http://localhost:8002/docs
- MS3: http://localhost:8003/docs
- MS4: http://localhost:8004/docs

## Run (Local)
ติดตั้ง Python 3.11+ แล้วรันทีละ service:

```bash
cd services/ms1-ingestor
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

ทำซ้ำกับ ms2, ms3, ms4 โดยเปลี่ยนพอร์ตเป็น 8002, 8003, 8004

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
- ระบบจะไหลผ่าน MS1 -> MS2 -> MS3 -> MS4 และแสดงผลใน UI

---

# Real-time Sensor Simulation (Free, Cloud-Native)

## What you get
- MQTT Broker จริง (Mosquitto)
- Sensor Simulator ส่งข้อมูลตามเวลาเข้า MQTT
- MS1 Subscribe MQTT แล้วเขียนลง InfluxDB

## Run
```bash
docker compose up --build
```

## MQTT Settings
ค่าอยู่ใน docker-compose.yml
- MQTT_BROKER: mosquitto
- MQTT_TOPIC: omnivigil/telemetry
- INTERVAL_MS: 1500
- ANOMALY_RATE: 0.04
