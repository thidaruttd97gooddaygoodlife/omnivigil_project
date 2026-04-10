# MS2 IoT Ingestor

MS2 รับข้อมูลจาก MQTT, ทำความสะอาดข้อมูล, และบันทึกลง InfluxDB เพื่อให้ทีม AI (MS3) ดึงไปใช้ต่อได้ทันที

## Responsibilities
- Subscribe MQTT topic: `omnivigil/telemetry`
- Validate + clean payload (`temperature_c`, `vibration_rms`, `rpm`, `pressure_bar`, `flow_lpm`, `current_a`, `oil_temp_c`, `humidity_pct`, `power_kw`)
- Write to InfluxDB measurement: `telemetry`
- Buffer pending writes ถ้า InfluxDB ล่มชั่วคราว

## Endpoints
- `GET /health` : สถานะ service + queue pending writes
- `GET /stats` : metrics สำหรับตรวจ ingest throughput/error
- `GET /quality/reference` : เกณฑ์ค่าปกติ/เตือน/วิกฤตของ sensor พร้อมที่มาอ้างอิง
- `GET /quality/readings` : quality score + flags ต่อ reading สำหรับงาน AI/Data Engineer
- `POST /ingest` : ingest แบบ HTTP
- `POST /ingest/analyze` : ingest และลองเรียก AI engine (optional)
- `POST /simulate/batch` : ยิงข้อมูลชุดทดสอบเข้า MS2 โดยตรง
- `POST /simulate/fail` : สร้างค่า critical จุดเดียวเพื่อ demo
- `GET /readings` : ดูข้อมูลล่าสุดใน memory

## Required ENV
- `MQTT_BROKER` (default `localhost`)
- `MQTT_PORT` (default `1883`)
- `MQTT_TOPIC` (default `omnivigil/telemetry`)
- `MQTT_QOS` (default `1`)
- `INFLUXDB_URL`
- `INFLUXDB_TOKEN`
- `INFLUXDB_ORG`
- `INFLUXDB_BUCKET`

## Optional ENV
- `AI_ENGINE_URL` (ใช้กับ `/ingest/analyze` และ `/simulate/fail`)
- `MAX_IN_MEMORY_READINGS` (default `5000`)
- `MAX_PENDING_INFLUX_WRITES` (default `10000`)
- `LOG_LEVEL` (default `INFO`)

## Run with Docker Compose
จาก root project:

```bash
cp .env.example .env
docker compose --profile simulator up -d --build
```

บน Windows PowerShell ใช้:

```powershell
Copy-Item .env.example .env
docker compose --profile simulator up -d --build
```

## InfluxDB API ต้องใช้ไหม?
- สำหรับการเขียนข้อมูล: **MS2 ใช้ `influxdb-client` อยู่แล้ว** ไม่ต้องเขียน HTTP API เอง
- สำหรับการตรวจสอบ/query ข้อมูล: ใช้ InfluxDB UI หรือเรียก Influx HTTP API ได้

### Step-by-step ตรวจข้อมูลใน InfluxDB (ด้วย API)
1. เช็คว่า InfluxDB up แล้ว:

```bash
curl http://localhost:8086/health
```

2. Query ข้อมูลล่าสุดใน bucket `telemetry`:

```bash
curl --request POST "http://localhost:8086/api/v2/query?org=omnivigil" \\
	--header "Authorization: Token omni_token" \\
	--header "Content-Type: application/vnd.flux" \\
	--data "from(bucket: \"telemetry\") |> range(start: -5m) |> filter(fn: (r) => r._measurement == \"telemetry\") |> limit(n: 20)"
```

3. ถ้าต้องการเช็คเฉพาะเครื่อง:

```bash
curl --request POST "http://localhost:8086/api/v2/query?org=omnivigil" \\
	--header "Authorization: Token omni_token" \\
	--header "Content-Type: application/vnd.flux" \\
	--data "from(bucket: \"telemetry\") |> range(start: -15m) |> filter(fn: (r) => r.device_id == \"cnc-spindle-301\") |> limit(n: 30)"
```

## Quick Verification
1. เช็ค health:

```bash
curl http://localhost:8002/health
```

2. เช็ค stats:

```bash
curl http://localhost:8002/stats
```

3. ถ้าข้อมูลไหลปกติ ค่าพวกนี้ควรเพิ่มขึ้นเรื่อยๆ:
- `mqtt_messages_total`
- `stored_total`
- `influx_write_success_total`

4. ตรวจ baseline/reference ของ sensor:

```bash
curl http://localhost:8002/quality/reference
```

5. ตรวจคุณภาพข้อมูลล่าสุด (noise/jump/warning/critical):

```bash
curl "http://localhost:8002/quality/readings?limit=20"
```

## Handoff to MS3 Team
บอกทีม AI ว่า:
- ข้อมูล telemetry ถูกเก็บใน InfluxDB bucket `telemetry`
- measurement ชื่อ `telemetry`
- fields: `temperature_c`, `vibration_rms`, `rpm`, `pressure_bar`, `flow_lpm`, `current_a`, `oil_temp_c`, `humidity_pct`, `power_kw`
- tags: `device_id`, `machine_type`, `line`, `zone`
- quality fields ใน Influx: `quality_score`, `quality_warning_count`, `quality_critical_count`, `quality_jump_count`
- quality API: `GET /quality/reference` และ `GET /quality/readings`
