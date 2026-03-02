from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

app = FastAPI(title="MS1 IoT Ingestor", version="0.1.0")
logger = logging.getLogger("ms1-ingestor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TelemetryReading(BaseModel):
    device_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    temperature_c: float
    vibration_rms: float
    rpm: Optional[float] = None


class IngestResponse(BaseModel):
    accepted: bool
    cleaned: TelemetryReading
    stored_count: int
    ingest_id: str


class IngestAnalyzeResponse(BaseModel):
    ingest: IngestResponse
    analysis: Optional[dict] = None
    error: Optional[str] = None


class BatchRequest(BaseModel):
    device_id: str
    count: int = Field(ge=1, le=200, default=10)


_readings: List[TelemetryReading] = []
_ai_engine_url = os.getenv("AI_ENGINE_URL", "http://localhost:8002")
_mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
_mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
_mqtt_topic = os.getenv("MQTT_TOPIC", "omnivigil/telemetry")
_mqtt_username = os.getenv("MQTT_USERNAME")
_mqtt_password = os.getenv("MQTT_PASSWORD")

_influx_url = os.getenv("INFLUXDB_URL")
_influx_token = os.getenv("INFLUXDB_TOKEN")
_influx_org = os.getenv("INFLUXDB_ORG")
_influx_bucket = os.getenv("INFLUXDB_BUCKET")
_influx_client: Optional[InfluxDBClient] = None
_write_api = None


def _clean_reading(reading: TelemetryReading) -> TelemetryReading:
    temp = max(-20.0, min(200.0, reading.temperature_c))
    vib = max(0.0, min(50.0, reading.vibration_rms))
    rpm = None if reading.rpm is None else max(0.0, reading.rpm)
    return TelemetryReading(
        device_id=reading.device_id,
        timestamp=reading.timestamp,
        temperature_c=temp,
        vibration_rms=vib,
        rpm=rpm,
    )


def _init_influx() -> None:
    global _influx_client, _write_api
    if not (_influx_url and _influx_token and _influx_org and _influx_bucket):
        logger.info("InfluxDB config missing. Skipping InfluxDB writer.")
        return
    _influx_client = InfluxDBClient(url=_influx_url, token=_influx_token, org=_influx_org)
    _write_api = _influx_client.write_api(write_options=SYNCHRONOUS)


def _write_influx(reading: TelemetryReading) -> None:
    if not _write_api:
        return
    point = (
        Point("telemetry")
        .tag("device_id", reading.device_id)
        .field("temperature_c", reading.temperature_c)
        .field("vibration_rms", reading.vibration_rms)
        .field("rpm", reading.rpm or 0.0)
        .time(reading.timestamp, WritePrecision.NS)
    )
    _write_api.write(bucket=_influx_bucket, org=_influx_org, record=point)


def _store_reading(cleaned: TelemetryReading) -> None:
    _readings.append(cleaned)
    try:
        _write_influx(cleaned)
    except Exception as exc:
        logger.warning("InfluxDB write failed: %s", exc)


def _call_ai_engine(telemetry: List[TelemetryReading]) -> tuple[Optional[dict], Optional[str]]:
    payload = {"telemetry": [item.model_dump(mode="json") for item in telemetry]}
    try:
        response = httpx.post(f"{_ai_engine_url}/analyze", json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json(), None
    except httpx.HTTPError as exc:
        return None, str(exc)


def _on_connect(client, userdata, flags, rc) -> None:
    if rc == 0:
        client.subscribe(_mqtt_topic)
        logger.info("MQTT connected to %s:%s topic=%s", _mqtt_broker, _mqtt_port, _mqtt_topic)
    else:
        logger.warning("MQTT connect failed: %s", rc)


def _on_message(client, userdata, message) -> None:
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        reading = TelemetryReading(**payload)
        cleaned = _clean_reading(reading)
        _store_reading(cleaned)
    except Exception as exc:
        logger.warning("MQTT message error: %s", exc)


def _start_mqtt() -> None:
    try:
        client = mqtt.Client(client_id=f"ms1-ingestor-{uuid4()}")
        if _mqtt_username and _mqtt_password:
            client.username_pw_set(_mqtt_username, _mqtt_password)
        client.on_connect = _on_connect
        client.on_message = _on_message
        client.connect(_mqtt_broker, _mqtt_port, 60)
        client.loop_start()
        app.state.mqtt_client = client
    except Exception as exc:
        logger.warning("MQTT connection skipped: %s", exc)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ms1-ingestor"}


@app.on_event("startup")
def startup() -> None:
    _init_influx()
    _start_mqtt()


@app.on_event("shutdown")
def shutdown() -> None:
    client = getattr(app.state, "mqtt_client", None)
    if client:
        client.loop_stop()
        client.disconnect()
    if _influx_client:
        _influx_client.close()


@app.post("/ingest", response_model=IngestResponse)
def ingest(reading: TelemetryReading) -> IngestResponse:
    cleaned = _clean_reading(reading)
    _store_reading(cleaned)
    return IngestResponse(
        accepted=True,
        cleaned=cleaned,
        stored_count=len(_readings),
        ingest_id=str(uuid4()),
    )


@app.post("/ingest/analyze", response_model=IngestAnalyzeResponse)
def ingest_analyze(reading: TelemetryReading) -> IngestAnalyzeResponse:
    cleaned = _clean_reading(reading)
    _store_reading(cleaned)
    analysis, error = _call_ai_engine([cleaned])
    return IngestAnalyzeResponse(
        ingest=IngestResponse(
            accepted=True,
            cleaned=cleaned,
            stored_count=len(_readings),
            ingest_id=str(uuid4()),
        ),
        analysis=analysis,
        error=error,
    )


@app.post("/simulate/batch")
def simulate_batch(request: BatchRequest) -> dict:
    import random

    generated = []
    now = datetime.now(timezone.utc)
    for _ in range(request.count):
        generated.append(
            TelemetryReading(
                device_id=request.device_id,
                timestamp=now,
                temperature_c=round(random.uniform(40, 110), 2),
                vibration_rms=round(random.uniform(0.1, 12.0), 3),
                rpm=round(random.uniform(900, 1600), 1),
            )
        )
    for item in generated:
        _store_reading(_clean_reading(item))

    return {"count": len(generated), "stored_count": len(_readings)}


@app.post("/simulate/fail", response_model=IngestAnalyzeResponse)
def simulate_fail(device_id: str = "motor-001") -> IngestAnalyzeResponse:
    critical = TelemetryReading(
        device_id=device_id,
        temperature_c=118.5,
        vibration_rms=10.9,
        rpm=1580.0,
    )
    cleaned = _clean_reading(critical)
    _store_reading(cleaned)
    analysis, error = _call_ai_engine([cleaned])
    return IngestAnalyzeResponse(
        ingest=IngestResponse(
            accepted=True,
            cleaned=cleaned,
            stored_count=len(_readings),
            ingest_id=str(uuid4()),
        ),
        analysis=analysis,
        error=error,
    )


@app.get("/readings", response_model=List[TelemetryReading])
def readings(limit: int = 100) -> List[TelemetryReading]:
    return _readings[-limit:]
