import json
import math
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

broker = os.getenv("MQTT_BROKER", "localhost")
port = int(os.getenv("MQTT_PORT", "1883"))
topic = os.getenv("MQTT_TOPIC", "omnivigil/telemetry")
device_id = os.getenv("DEVICE_ID", "motor-001")
interval_ms = int(os.getenv("INTERVAL_MS", "1000"))
anomaly_rate = float(os.getenv("ANOMALY_RATE", "0.03"))

client = mqtt.Client(client_id=f"sim-sensor-{device_id}-{random.randint(100, 999)}")
client.connect(broker, port, 60)
client.loop_start()

base_temp = 68.0
base_vib = 2.4
base_rpm = 1450.0

drift = 0.0
step = 0

while True:
    phase = step / 14.0
    temp = base_temp + 6.5 * math.sin(phase) + random.uniform(-0.6, 0.6) + drift
    vib = base_vib + 0.7 * math.sin(step / 9.0) + random.uniform(-0.15, 0.15)
    rpm = base_rpm + 40 * math.sin(step / 18.0) + random.uniform(-8, 8)

    if random.random() < anomaly_rate:
        temp += random.uniform(10, 22)
        vib += random.uniform(3, 7)
        rpm += random.uniform(80, 160)

    payload = {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": round(temp, 2),
        "vibration_rms": round(max(0.1, vib), 3),
        "rpm": round(max(0.0, rpm), 1)
    }

    client.publish(topic, json.dumps(payload))

    drift = min(drift + 0.004, 18.0)
    step += 1
    time.sleep(interval_ms / 1000.0)
