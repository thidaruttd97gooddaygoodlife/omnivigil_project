# OmniVigil Runbook

OmniVigil คือระบบ Microservices สำหรับงาน Predictive Maintenance ในโรงงาน ซึ่งถูกออกแบบมาให้ทำงานประสานกันผ่านเครือข่ายและฐานข้อมูลที่แยกส่วนกันอย่างชัดเจนตามหลักการ Microservices Architecture

---

## 1. สถาปัตยกรรมระบบและหน้าที่ของแต่ละ Microservice

ระบบเต็มแบ่งออกเป็น 5 ไมโครเซอร์วิสหลักและ 1 ซิมูเลเตอร์ แต่ละส่วนมีหน้าที่แยกจากกันชัดเจน:

- **Sim Sensor**: (ตัวจำลอง) ส่งข้อมูล Telemetry สุ่มและยิง Anomaly ปลอมเข้า MQTT Broker โดยจำลองข้อมูลเซ็นเซอร์รอบละ 1-5 วินาที พร้อมเพิ่ม Gaussian noise และ Inject outlier
- **MS1 Auth**: ระบบจัดการผู้ใช้งานและการ Authentication รับผิดชอบการเข้าสู่ระบบ, ลงทะเบียน, ออกและตรวจสอบ JWT Token มีฐานข้อมูล PostgreSQL เป็นของตัวเอง
- **MS2 Ingestor**: ด่านหน้ารับข้อมูลจาก Sensor (ผ่าน MQTT) ทำหน้าที่ Validate metrics, Clean data, คำนวณ Quality Score และทำ Dual-write ข้อมูลลง InfluxDB (แบบ Batch) และ Redis (Hot-path ข้อมูลล่าสุด)
- **MS3 AI Engine + Worker**: ประมวลผลข้อมูลด้วย AI เพื่อตรวจจับความผิดปกติ (Anomaly) ทำงานแบบ Asynchronous โดยใช้ Redis Queue ในการเก็บ Job status และส่ง Event
- **MS4 Alert**: จัดการระบบแจ้งเตือน รับ Event ความผิดปกติที่ตรวจพบแล้วยิงแจ้งเตือนไปยังผู้ใช้ (เช่น ผ่าน LINE Messaging API) มีฐานข้อมูล PostgreSQL สำหรับเก็บ Audit Log
- **MS5 Maintenance**: จัดการข้อมูลการซ่อมบำรุง, สร้าง ติดตาม และอัปเดตตั๋วซ่อมบำรุงเมื่อเครื่องจักรมีปัญหา มีฐานข้อมูล PostgreSQL ของตัวเอง

---

## 2. การตั้งค่า Environment Variables

ระบบรองรับการรัน 2 รูปแบบหลัก คือ Local และ Managed (External Services)

### ไฟล์ Environment
- `.env` (สำหรับโหมด Local)
- `env.managed` (สำหรับโหมด Managed ที่ต้องต่อ External Database)

**ข้อควรระวัง:** ห้ามนำความลับ (Secrets) เช่น รหัสผ่าน หรือ URL ฐานข้อมูลจริง ใส่ลงในไฟล์ที่ถูก Track โดย Git เด็ดขาด (อัปขึ้น Git ได้เฉพาะไฟล์ Template เช่น `env.managed.example`)

### ค่าตัวแปรที่สำคัญในระบบ (จำแนกตามความรับผิดชอบ)
ก่อนรันระบบเต็มรูปแบบ ทีมต้องมั่นใจว่ามีค่าเหล่านี้ครบถ้วนในไฟล์ Environment:

**Shared Security:**
- `JWT_SECRET`: คีย์ลับสำหรับสร้าง/ตรวจสอบ JWT Token ของ MS1 (ต้องใช้รหัสที่คาดเดายาก)
- `INTERNAL_SERVICE_KEY`: สำหรับการคุยกันเองระหว่าง Service ภายใน

**Data Pipeline (MS2 & Sim Sensor):**
- **MQTT**: `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, `MQTT_PASSWORD`
- **InfluxDB**: `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`
- **Redis**: `REDIS_URL` (ใช้ร่วมกันหลาย MS ทั้ง MS2, MS3, MS4, MS5)

**Database (PostgreSQL) ประจำ Service:**
- **MS1**: `POSTGRES_URL_AUTH` (ต้องเป็น URL ของฐานข้อมูล Auth)
- **MS4**: `ALERT_POSTGRES_URL` (ต้องเป็น URL ของฐานข้อมูล Alert)
- **MS5**: `POSTGRES_URL_MAINT` (ต้องเป็น URL ของฐานข้อมูล Maintenance)

---

## 3. โหมดการรันระบบ (Deployment Modes)

### โหมด A: Local Full Stack (รันทุกอย่างในเครื่องเดียว)
เหมาะสำหรับการทำ Demo หรือรันทดสอบระบบแบบครบ Flow บนเครื่อง Local
- ใช้ไฟล์ `docker-compose.yml` (จะมีการดึง Infra images อย่าง Postgres, Redis, InfluxDB, MQTT Broker มารันในเครื่องด้วย)
```powershell
Copy-Item .env.example .env
docker compose --profile simulator up -d --build
```

### โหมด B: Managed External Services (แนะนำสำหรับการเชื่อมต่อระบบจริง)
เหมาะสำหรับทีมที่มีฐานข้อมูล Managed Services อยู่แล้ว (เพื่อลดโหลดเครื่อง Local และจำลอง Production)
- ใช้ไฟล์ `docker-compose.managed.yml` (จะรันเฉพาะ App images เท่านั้น)
```powershell
# 1. คัดลอก Template ไปเป็นไฟล์ใช้งานจริง
Copy-Item env.managed.example env.managed

# 2. เข้าไปแก้ไขไฟล์ env.managed เติม Database URL และ Credentials ให้ครบทุก Service

# 3. รันระบบทั้งหมด
docker compose -f docker-compose.managed.yml --env-file env.managed up -d --build
```

### โหมด C: รันเฉพาะ Data Pipeline (MS2 + Sim Sensor)
กรณีต้องการรันทดสอบเฉพาะการดูดข้อมูลและรับส่งผ่าน MQTT โดยไม่ต้องรอให้ระบบ Auth (MS1) พร้อมทำงาน (MS2 ได้ตั้งค่า Resilient Startup ให้ข้ามการเช็ค DB ของ MS1 แล้ว)
```powershell
docker compose -f docker-compose.managed.yml --env-file env.managed --profile simulator up -d --build ms2-ingestor sim-sensor
```
*วิธีเช็คผล:* 
ตรวจสอบ Logs ว่ารับข้อมูลและยิงลง InfluxDB/Redis สำเร็จหรือไม่:
`docker logs omnivigil-sim-sensor-1` และ `docker logs omnivigil-ms2-ingestor-1`

---

## 4. แนวปฏิบัติด้านความปลอดภัย (Security Best Practices)
เพื่อให้ระบบปลอดภัย ทีมงานทุกคนต้องยึดหลักการเหล่านี้:
- **Authorization**: ใช้ JWT ผ่าน MS1 เท่านั้น MS2 และ MS5 ต้อง Verify token กับ MS1 เสมอสำหรับ API ที่รับ Request จาก Frontend
- **Secrets Management**: ตั้งค่า Secret ผ่าน Environment Variables เท่านั้น ห้าม Hardcode ลงใน Source Code
- **Least Privilege**: แยกสิทธิ์ Database Account และ Schema ต่อบริการอย่างชัดเจน (MS1, MS4, MS5 ต้องไม่ใช้ Database เดียวกัน)
- **Encryption in Transit**: บังคับใช้ TLS สำหรับทุก Endpoint ภายนอก (เช่น MQTT_PORT=8883)
- **Sanitization**: ห้าม Log Token, Password หรือ Connection String แบบเต็มในระบบเด็ดขาด

---

## 5. จุดเปิดตรวจระบบ (Health Checks)
หลังรันระบบขึ้น สามารถตรวจสอบสถานะการทำงาน (รวมถึงการเชื่อมต่อ DB) ของแต่ละ Service ได้ที่:
- MS1: http://localhost:8001/health
- MS2: http://localhost:8002/health
- MS3: http://localhost:8003/health
- MS4: http://localhost:8004/health
- MS5: http://localhost:8005/health

---

## 6. กฎข้อบังคับการใช้งาน Git
**ห้ามอัปไฟล์ Secret ขึ้น Git เด็ดขาด** หากมีการสร้างไฟล์ `env.managed` ระบบจะทำการ Ignore อัตโนมัติ (ตั้งไว้ใน `.gitignore` แล้ว)
หากเผลอ Track ไฟล์ความลับไปแล้ว ให้รัน:
```powershell
git rm --cached env.managed
git commit -m "chore: stop tracking managed env file"
```
**หมายเหตุ:** หาก Token หรือ Password ใดหลุดขึ้น Public Git ให้แจ้งเปลี่ยน (Rotate) ที่ฝั่งผู้ให้บริการ (Provider) ทันที

---
**เอกสารอ้างอิงเพิ่มเติม:**
- [docs/architecture.md](docs/architecture.md)
- [docs/project_setup.md](docs/project_setup.md)
- [docs/production_checklist.md](docs/production_checklist.md)
