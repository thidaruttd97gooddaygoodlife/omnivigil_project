# MS2 Handoff (Ready for Team)

เอกสารนี้ใช้ส่งต่องาน MS2 ให้เพื่อนทำ MS3/MS4/MS5 ต่อได้ทันที

## 1) Scope ที่ส่งมอบแล้ว
- MS2 รับข้อมูลจาก MQTT (`omnivigil/telemetry`)
- Validate/Clean ข้อมูล telemetry ก่อนจัดเก็บ
- เขียนข้อมูลลง InfluxDB measurement `telemetry`
- มี retry buffer กรณี Influx เขียนไม่สำเร็จชั่วคราว
- มี endpoint สำหรับตรวจงาน: `/health`, `/stats`, `/readings`

## 2) Data Contract ที่ทีมอื่นต้องใช้
- Bucket: `telemetry`
- Measurement: `telemetry`
- Tags: `device_id`, `machine_type`, `line`, `zone`
- Fields: `temperature_c`, `vibration_rms`, `rpm`, `pressure_bar`, `flow_lpm`, `current_a`, `oil_temp_c`, `humidity_pct`, `power_kw`

## 3) Environment ที่ MS2 ต้องมี
- `INFLUXDB_URL`
- `INFLUXDB_TOKEN`
- `INFLUXDB_ORG`
- `INFLUXDB_BUCKET`
- `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`

หมายเหตุ:
- ถ้าใช้ Influx local ให้ `INFLUXDB_URL=http://influxdb:8086`
- ถ้าใช้ Influx Cloud ให้ `INFLUXDB_URL=https://<region>.cloud2.influxdata.com`

## 4) Definition of Done (DoD) สำหรับปิดงาน MS2
1. `docker compose ps` แล้ว `ms2-ingestor` เป็น healthy
2. `GET /health` ได้ `status: ok`
3. `GET /stats` แล้วค่าพวกนี้เพิ่มขึ้น:
   - `mqtt_messages_total`
   - `stored_total`
   - `influx_write_success_total`
4. `mqtt_parse_errors_total = 0`
5. `pending_influx_writes = 0` (หรือไม่โตต่อเนื่อง)

## 5) คำสั่งตรวจรับงาน (copy-run)
```powershell
docker compose --profile simulator up -d --build
curl.exe http://localhost:8002/health
curl.exe http://localhost:8002/stats
```

## 6) หลักฐานรอบล่าสุด (ตัวอย่าง)
- `mqtt_messages_total`: 3850
- `stored_total`: 3850
- `influx_write_success_total`: 3850
- `mqtt_parse_errors_total`: 0
- `pending_influx_writes`: 0

## 7) ส่งต่อให้เพื่อนทีมอื่น
- ทีม MS3: ใช้ schema จากหัวข้อ Data Contract เพื่ออ่านข้อมูลจาก Influx
- ทีม MS4/MS5: รับผลจาก MS3 ต่อ ไม่ต้องแก้ ingest
- ถ้าจะแยก branch ทำงาน: แนะนำ `feat/ms2-ingestor-*` ตาม `CONTRIBUTING.md`