# OmniVigil Runbook

OmniVigil คือระบบ Microservices สำหรับงาน Predictive Maintenance ในโรงงาน

## 1) ของคุณ: Sim Sensor + MS2

ขอบเขตของคุณมี 2 บริการหลัก
- Sim Sensor: สร้าง telemetry จำลอง แล้วส่งเข้า MQTT
- MS2 Ingestor: รับ telemetry, clean data, quality score, dual-write ไป InfluxDB และ Redis

### ENV ที่คุณมีแล้ว (ถูกต้อง)
- MQTT_BROKER
- MQTT_PORT
- MQTT_TOPIC
- INFLUXDB_URL
- INFLUXDB_TOKEN
- INFLUXDB_ORG
- INFLUXDB_BUCKET
- REDIS_URL

หมายเหตุสำคัญ
- ชุดนี้ครบสำหรับ data path ของคุณ (Sim Sensor -> MQTT -> MS2 -> Influx/Redis)
- ค่าเหล่านี้ต้องชี้ไปที่บริการจริงภายนอก (Managed endpoints) ไม่ใช่ localhost
- ถ้าจะเรียก endpoint MS2 ที่ต้อง auth ด้วย frontend/user token ให้มี MS1_AUTH_URL และ JWT token เพิ่ม

ตัวอย่างแนวคิดค่าแบบ production/managed
- MQTT_BROKER=<managed-mqtt-host>
- INFLUXDB_URL=https://<managed-influx-host>
- REDIS_URL=rediss://<managed-redis-host>:6379/0

### ความหมายของ ENV ของคุณ
- MQTT_BROKER, MQTT_PORT, MQTT_TOPIC
  หน้าที่: ให้ Sim Sensor ส่งข้อมูลเข้า broker และให้ MS2 subscribe topic เดียวกัน
- INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET
  หน้าที่: ให้ MS2 เขียนข้อมูลลง InfluxDB แบบ batch
- REDIS_URL
  หน้าที่: ให้ MS2 เขียน hot-path list per device ด้วย RPUSH/LTRIM และใช้เป็น source อ่านเร็ว

### ข้อเท็จจริงด้านโค้ดของคุณ
- Sim Sensor สุ่มรอบ 1-5 วินาที, Gaussian noise, inject outlier และ publish MQTT QoS1
- MS2 มี MQTT callback -> internal queue -> worker thread
- MS2 validate missing metrics > 30%
- MS2 clamp ค่าให้อยู่ใน guardrail
- MS2 คำนวณ quality score
- MS2 dual-write Influx + Redis list (trim ล่าสุด 5000 จุด)

## 2) ของเพื่อน: ทั้งระบบ

ระบบเต็มมี
- MS1 Auth
- MS2 Ingestor
- MS3 AI Engine + Worker
- MS4 Alert
- MS5 Maintenance

### เพื่อนต้องทำต่อ (สถานะล่าสุด)
- MS4: ต่อ LINE Messaging API จริงและทำ delivery handling ให้ครบ
- MS3: job status ถูกย้ายไป Redis แล้ว (ไม่ใช่ local-only dict)

## 3) โหมดรันที่ทีมใช้ได้

มี 2 โหมด

### เลือกไฟล์รันเมื่อ "ไม่เอา Local"
- ใช้ docker-compose.managed.yml
- ใช้ .env.managed ที่คัดลอกจาก env.managed.example แล้วใส่ค่า endpoint จริง
- ไม่ใช้ .env สำหรับโหมดนี้

### โหมด A: Local Full Stack (ทุกอย่างในเครื่อง)
ใช้ไฟล์ compose หลัก
- [docker-compose.yml](docker-compose.yml)

รัน
```powershell
Copy-Item .env.example .env
docker compose --profile simulator up -d --build
```

เหมาะกับ
- ทำเดโมครบ flow
- ทดสอบทั้งระบบแบบปิดในเครื่องเดียว

image ที่จะถูกใช้ในโหมดนี้
- Infra images: eclipse-mosquitto, influxdb, redis, postgres (2 ตัว)
- App images: ms1-auth, ms2-ingestor, ms3-ai-engine, ms4-alert, ms5-maintenance, sim-sensor

### โหมด B: Managed External Services (แนะนำสำหรับทีม integration และ Localless)
ใช้บริการจริงภายนอกสำหรับ MQTT, Redis, InfluxDB และ Postgres

ไฟล์ที่ใช้
- [docker-compose.managed.yml](docker-compose.managed.yml)
- [env.managed.example](env.managed.example)

รัน
```powershell
Copy-Item env.managed.example .env.managed
docker compose -f docker-compose.managed.yml --env-file .env.managed up -d --build
```

ตรวจความถูกต้องก่อนรันจริง
```powershell
docker compose -f docker-compose.managed.yml --env-file .env.managed config > $null
```

เหมาะกับ
- ทีมที่มี managed services จริงอยู่แล้ว
- ลดจำนวน infra container ในเครื่อง
- มาตรฐาน microservice แบบ localless (state อยู่นอก service process)

image ที่จะถูกใช้ในโหมดนี้
- App images เท่านั้น: ms1-auth, ms2-ingestor, ms3-ai-engine, ms3-worker, ms4-alert, ms5-maintenance, sim-sensor (เปิดเมื่อใช้ profile simulator)
- ไม่มี infra images ในเครื่องสำหรับ MQTT/Redis/Influx/Postgres

### วิธีรันทั้งระบบ (ไม่ Local)
```powershell
docker compose -f docker-compose.managed.yml --env-file .env.managed up -d --build
```

### วิธีรันเฉพาะของคุณ (Sim Sensor + MS2 แบบไม่ Local)
กรณีต้องการให้ simulator ส่งจริงเข้า MQTT แล้วให้ MS2 ingest
```powershell
docker compose -f docker-compose.managed.yml --env-file .env.managed --profile simulator up -d --build ms1-auth ms2-ingestor sim-sensor
```

กรณีไม่ใช้ simulator (รอข้อมูลจาก sensor/broker จริง)
```powershell
docker compose -f docker-compose.managed.yml --env-file .env.managed up -d --build ms1-auth ms2-ingestor
```

## 4) ถ้าใช้บริการจริงภายนอก: ต้องเตรียมอะไร

หลักการ
- แต่ละบริการมี DB ของตัวเองตามความรับผิดชอบ
- ต้องใช้ credential ของจริงจาก platform ทีม
- ห้าม hardcode secret ในโค้ด

ตัวอย่างการแยก ownership ของ DB
- MS1 Auth -> Auth Postgres
- MS5 Maintenance -> Maintenance Postgres
- MS4 Alert audit -> Alert Postgres (แยกหรือ shared instance คนละ database/schema)
- MS2 -> InfluxDB + Redis (ไม่ใช้ Postgres ของตัวเอง)
- MS3 -> Redis broker/backend และเก็บ job status ใน Redis key-space

## 5) Security แนวปฏิบัติ (ทีมต้องทำตาม)

- ใช้ JWT ผ่าน MS1 เท่านั้น
- MS2 และ MS5 ต้อง verify token กับ MS1 ทุกครั้งสำหรับ frontend-facing API
- INTERNAL_SERVICE_KEY ใช้เฉพาะ service-to-service trusted path
- ตั้ง secret ผ่าน env เท่านั้น
- บน production ให้ใช้ short token expiry, rotate secrets, จำกัด CORS origin จริง
- บังคับ TLS ทุก endpoint ภายนอก
- แยกสิทธิ์ DB account ต่อบริการ (least privilege)
- ห้าม log token, password, connection string แบบเต็ม

## 6) จุดเปิดตรวจระบบ

หลังระบบขึ้น ให้เช็ก
- MS1: http://localhost:8001/health
- MS2: http://localhost:8002/health
- MS3: http://localhost:8003/health
- MS4: http://localhost:8004/health
- MS5: http://localhost:8005/health

สำหรับ scope ของคุณ (MS2)
- http://localhost:8002/stats
- http://localhost:8002/readings?limit=20

## 7) เอกสารเสริมในโปรเจกต์

- [docs/architecture.md](docs/architecture.md)
- [docs/project_setup.md](docs/project_setup.md)
- [docs/production_checklist.md](docs/production_checklist.md)
- [services/ms2-ingestor/README.md](services/ms2-ingestor/README.md)
- [services/sim-sensor/README.md](services/sim-sensor/README.md)

## 8) ห้ามอัป Secret ขึ้น Git

หลักการ
- เก็บค่าใช้งานจริงไว้ใน .env.managed เท่านั้น
- อัปขึ้น Git ได้เฉพาะ env.managed.example (template)

เช็กก่อน push
```powershell
git check-ignore -v .env.managed
git status
```

ถ้าเผลอเคย track ไฟล์ลับ
```powershell
git rm --cached .env.managed
git commit -m "stop tracking managed env file"
```

ถ้า token/password หลุด ให้ rotate ที่ผู้ให้บริการทันที
