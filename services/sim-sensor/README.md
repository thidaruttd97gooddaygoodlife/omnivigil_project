# Sensor Simulator (for MS2)

ตัวจำลองเครื่องจักรเพื่อส่ง telemetry เข้า MQTT อัตโนมัติ สำหรับทดสอบ MS2

## Features
- Multi-machine simulation (default 5 เครื่องจริงจากไลน์ผลิต)
- Gaussian noise simulation สำหรับค่าเซนเซอร์ให้ดูสมจริง
- Intentional outlier injection เพื่อทดสอบการ clean/clamp ฝั่ง MS2
- Network latency/drop simulation
- Manual trigger anomaly

## Default Machine Set (5 เครื่อง)
- `mix-pump-101` (centrifugal pump): temp, vibration, rpm, pressure, flow, current, power
- `filling-comp-201` (air compressor): temp, vibration, rpm, pressure, current, oil_temp, power
- `cnc-spindle-301` (CNC spindle): temp, vibration, rpm, current, oil_temp, power
- `boiler-feed-401` (boiler feed pump): temp, vibration, rpm, pressure, flow, current, power
- `pack-conveyor-501` (conveyor gearmotor): temp, vibration, rpm, current, humidity, power

## Environment Variables
- `MQTT_BROKER` (default `localhost`)
- `MQTT_PORT` (default `1883`)
- `MQTT_TOPIC` (default `omnivigil/telemetry`)
- `INTERVAL_OPTIONS_SEC` (default `1,2,3,4,5`)
- `INTERVAL_MS` (fallback legacy, default `5000`)
- `ANOMALY_RATE` (default `0.03`)
- `MACHINE_COUNT` (default `5`)
- `MACHINE_IDS` (optional, comma-separated IDs เช่น `mix-pump-101,cnc-spindle-301`)
- `NETWORK_DROP_RATE` (default `0.02`)
- `NETWORK_DROP_DURATION_SEC` (default `8`)
- `MANUAL_TRIGGER_FILE` (default `/tmp/force_anomaly`)

## Telemetry Packet Contract (MQTT QoS 1)
ทุก message ถูกส่งไปที่ `omnivigil/telemetry` ด้วย QoS 1 โดยใช้โครงสร้าง:

```json
{
	"device_id": "pump-01",
	"machine_type": "centrifugal-pump",
	"line": "L1",
	"zone": "mixing",
	"ts": "2026-04-29T10:00:00Z",
	"metrics": {
		"temperature_c": 85.2,
		"vibration_rms": 2.1,
		"rpm": 1498.0
	}
}
```

## Manual Trigger Anomaly
มี 2 วิธี

### 1) ผ่าน STDIN command
ระหว่างรัน script พิมพ์:

```text
spike all
```

หรือระบุเครื่อง:

```text
spike cnc-spindle-301
```

### 2) ผ่าน trigger file
เขียนค่า `all` หรือ `cnc-spindle-301` ลงไฟล์ trigger path แล้ว script จะอ่านและลบไฟล์ให้:

```bash
echo all > /tmp/force_anomaly
```

## Run with compose profile
จาก root:

```bash
docker compose --profile simulator up -d --build
```

ตัวอย่างถ้าต้องการคงที่ 20 วินาที:

```bash
INTERVAL_OPTIONS_SEC=20 docker compose --profile simulator up -d --build
```