# OmniVigil Production Checklist (Course Submission)

เอกสารนี้ใช้เป็น checklist ก่อนเดโม/ส่งงาน โดยโฟกัส Cloud-Native + Microservice readiness

## 1) Security Baseline
- สร้างไฟล์ `.env` จาก `.env.example`
- เปลี่ยนค่าพวกนี้ก่อนใช้งานจริง: `INFLUXDB_TOKEN`, `INFLUXDB_INIT_PASSWORD`, `JWT_SECRET`, `*_POSTGRES_PASSWORD`
- ห้าม commit ไฟล์ `.env` ขึ้น repo

## 2) Start Stack (with simulator)
```bash
docker compose --profile simulator up -d --build
```

## 3) Service Health Gates
ตรวจทุก service ต้อง `healthy` หรือ `Up`:
```bash
docker compose ps
```

เช็ค API health:
```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
```

## 4) Data Pipeline Validation
- MQTT -> MS2 -> InfluxDB

เช็ค ingest metrics:
```bash
curl http://localhost:8002/stats
```
ค่าที่ควรเพิ่มขึ้น: `mqtt_messages_total`, `stored_total`, `influx_write_success_total`

## 5) InfluxDB Retention (สำคัญสำหรับงานจริง)
> ค่า default ของ bucket จาก bootstrap มักเป็น retention ไม่จำกัด ให้ตั้ง retention ตามนโยบายโครงงาน

### ตัวอย่างตั้ง retention 30 วัน
```bash
docker compose exec influxdb influx bucket update \
  --name telemetry \
  --retention 720h \
  --org omnivigil \
  --token "$INFLUXDB_TOKEN"
```

### ตรวจ bucket config
```bash
docker compose exec influxdb influx bucket list \
  --org omnivigil \
  --token "$INFLUXDB_TOKEN"
```

## 6) InfluxDB Backup / Restore
### Backup
```bash
docker compose exec influxdb influx backup /tmp/influx-backup \
  --org omnivigil \
  --token "$INFLUXDB_TOKEN"
```

คัดลอก backup ออกมาที่ host:
```bash
docker cp omnivigil-influxdb-1:/tmp/influx-backup ./backups/influx-backup
```

### Restore (เมื่อจำเป็น)
```bash
docker compose exec influxdb influx restore /tmp/influx-backup \
  --token "$INFLUXDB_TOKEN"
```

## 7) Fault Injection Demo
- Trigger anomaly ทั้งโรงงาน:
```bash
docker compose exec sim-sensor sh -c 'echo all > /tmp/force_anomaly'
```

- Trigger เฉพาะเครื่อง:
```bash
docker compose exec sim-sensor sh -c 'echo cnc-spindle-301 > /tmp/force_anomaly'
```

## 8) Resource & Persistence Notes
- ทุก service ตั้ง `restart: unless-stopped`
- มี resource caps (`mem_limit`, `cpus`) เพื่อกัน service แย่งทรัพยากร
- ใช้ named volumes สำหรับ `influxdb`, `postgres`, `redis`, `rabbitmq`

## 9) Team Handoff (MS3)
ส่งข้อมูลให้ทีม AI:
- Bucket: `telemetry`
- Measurement: `telemetry`
- Tags: `device_id`, `machine_type`, `line`, `zone`
- Fields: `temperature_c`, `vibration_rms`, `rpm`, `pressure_bar`, `flow_lpm`, `current_a`, `oil_temp_c`, `humidity_pct`, `power_kw`
