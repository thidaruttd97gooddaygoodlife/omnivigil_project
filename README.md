# OmniVigil

ระบบ Cloud-Native + Microservices สำหรับ Predictive Maintenance ในโรงงาน

## โครงภาพรวม 
- MS1 `services/ms1-auth`: login/JWT
- MS2 `services/ms2-ingestor`: ingest + clean telemetry + write InfluxDB
- MS3 `services/ms3-ai-engine`: ประเมิน anomaly/risk
- MS4 `services/ms4-alert`: แจ้งเตือน
- MS5 `services/ms5-maintenance`: work order
- Infra: Mosquitto, InfluxDB, Redis, RabbitMQ, PostgreSQL (2 ตัว)

## สิ่งที่ต้องมีในเครื่อง
- Docker Desktop (ต้องเป็นสถานะ Running)
- GitHub 
- (ถ้าจะรันหน้าเว็บ) Node.js 18+

## เริ่มใช้งานครั้งแรก (Windows PowerShell)
1) ไปที่โฟลเดอร์โปรเจกต์

```powershell
cd path\to\omnivigil
```

2) สร้างไฟล์ env

```powershell
Copy-Item .env.example .env
```

3) รันระบบพร้อม simulator

```powershell
docker compose --profile simulator up -d --build
```

4) เช็กว่า service ขึ้นครบ

```powershell
docker compose ps
```

## จุดที่ต้องเปิดเช็กหลังระบบขึ้น
- MS1 Auth: http://localhost:8001/docs
- MS2 Ingestor: http://localhost:8002/docs
- MS3 AI Engine: http://localhost:8003/docs
- MS4 Alert: http://localhost:8004/docs
- MS5 Maintenance: http://localhost:8005/docs
- InfluxDB UI: http://localhost:8086

## วิธียืนยันว่า Pipeline ทำงานจริง ใส่ชื่อ Port ตนเองแทน 
1) เช็กสุขภาพ MS2

```powershell
curl.exe http://localhost:8002/health
```

2) เช็กสถิติ ingest

```powershell
curl.exe http://localhost:8002/stats
```

ค่าที่ควรเพิ่มขึ้นเรื่อย ๆ:
- `mqtt_messages_total`
- `stored_total`
- `influx_write_success_total`

3) ยิง anomaly ด้วยมือ (เดโม)

```powershell
docker compose exec sim-sensor sh -c "echo all > /tmp/force_anomaly"
```

## คำสั่งที่ใช้บ่อย
- ดู log ของ service เดียว


## ตัวอย่างการ รีบิลด์เฉพาะ service ที่แก้ ใส่ชื่อ service ตนเอง แทน `ms2-ingestor`
```powershell
docker compose logs -f ms2-ingestor
```

```powershell
docker compose up -d --build ms2-ingestor
```

- หยุดระบบ

```powershell
docker compose down
```

- รีเซ็ตข้อมูลทั้งหมด (ใช้เมื่อระบบเพี้ยนหนัก)
- ระวังคำสั่งนี้จะลบข้อมูลใน InfluxDB, Redis, RabbitMQ, PostgreSQL ด้วย

```powershell
docker compose down -v
docker compose --profile simulator up -d --build
```

## Frontend (อย่างเดียว)

```powershell
cd frontend
npm install
npm run dev
```

## เอกสารอ้างอิงในโปรเจกต์
- กติกาทีม: `CONTRIBUTING.md`
- สถาปัตยกรรม: `docs/architecture.md`
- API รวม: `docs/openapi.md`
- Production checklist: `docs/production_checklist.md`
- Setup มาตรฐานทีม: `docs/project_setup.md`
- Handoff ฝั่ง MS2: `docs/ms2_handoff.md`


