from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

import anyio
import httpx
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.tasks import ALL_SENSORS, run_inference_sensor

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="MS3 AI Engine (Web Server)", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_alert_url = os.getenv("ALERT_URL", "http://localhost:8004")
_maintenance_url = os.getenv("MAINTENANCE_URL", "http://localhost:8005")
_last_events: List[dict] = []


# ── Pydantic models ──────────────────────────────────────────────────────────

class TelemetryReading(BaseModel):
    """One sensor snapshot from one device. Extra fields (e.g. from future sensors) are ignored."""
    model_config = ConfigDict(extra="ignore")

    device_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # All 9 monitored sensors — all Optional so partial payloads are accepted
    temperature_c: Optional[float] = None
    vibration_rms: Optional[float] = None
    rpm:           Optional[float] = None
    pressure_bar:  Optional[float] = None
    flow_lpm:      Optional[float] = None
    current_a:     Optional[float] = None
    oil_temp_c:    Optional[float] = None
    humidity_pct:  Optional[float] = None
    power_kw:      Optional[float] = None


class AnalyzeRequest(BaseModel):
    telemetry: List[TelemetryReading]


class DeviceResult(BaseModel):
    """Per-device inference results, broken down by sensor."""
    anomaly_score: float
    per_sensor: Dict[str, float]


class AnalyzeResponse(BaseModel):
    anomaly_score: float          # worst score across all devices
    risk_level: str
    model: str
    per_device: Optional[Dict[str, DeviceResult]] = None   # detailed breakdown
    event_id: Optional[str] = None
    alert_id: Optional[str] = None
    work_order_id: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _score(reading: TelemetryReading) -> float:
    """
    Fast threshold-based score for the CURRENT reading (no ML).
    Used for immediate alerting while ML inference runs asynchronously.
    """
    score = 0.0
    if reading.temperature_c is not None:
        score += max(0.0, (reading.temperature_c - 70.0) / 40.0)
    if reading.vibration_rms is not None:
        score += max(0.0, (reading.vibration_rms - 4.0) / 6.0)
    if reading.rpm is not None and reading.rpm > 1500:
        score += 0.1
    if reading.pressure_bar is not None:
        score += max(0.0, (reading.pressure_bar - 8.0) / 4.0)
    if reading.current_a is not None:
        score += max(0.0, (reading.current_a - 20.0) / 10.0)
    if reading.power_kw is not None:
        score += max(0.0, (reading.power_kw - 15.0) / 5.0)
    # Normalise (6 sensors contributing → divide by 6)
    return max(0.0, min(1.0, score / 6.0))


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.50:
        return "high"
    if score >= 0.30:
        return "medium"
    return "low"


def _dispatch_alert(device_id: str, level: str, score: float) -> Optional[str]:
    payload = {
        "machine_id": device_id,
        "risk_level": level,
        "anomaly_score": round(score, 4),
        "message": "Auto alert from AI engine",
        "channels": ["line", "toast", "sound"],
    }
    try:
        r = httpx.post(f"{_alert_url}/alerts", json=payload, timeout=5.0)
        r.raise_for_status()
        return r.json().get("alert_id")
    except httpx.HTTPError:
        return None


def _create_work_order(
    device_id: str, level: str, alert_id: Optional[str]
) -> Optional[str]:
    payload = {
        "machine_id": device_id,
        "issue": f"Investigate {level} anomaly",
        "priority": "high" if level in {"high", "critical"} else "medium",
        "source_alert_id": alert_id,
    }
    try:
        r = httpx.post(f"{_maintenance_url}/work-orders", json=payload, timeout=5.0)
        r.raise_for_status()
        return r.json().get("work_order_id")
    except httpx.HTTPError:
        return None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ms3-ai-engine", "mode": "web"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    if not request.telemetry:
        return AnalyzeResponse(anomaly_score=0.0, risk_level="low", model="simulated")

    # ── 1. Group telemetry by device_id ──────────────────────────────────────
    # This ensures ALL devices in the payload are processed,
    # not just the first one.
    device_groups: Dict[str, List[dict]] = defaultdict(list)
    for reading in request.telemetry:
        device_groups[reading.device_id].append(reading.model_dump(mode="json"))

    logging.info(
        f"Received telemetry for {len(device_groups)} device(s): "
        f"{list(device_groups.keys())}"
    )

    # ── 2. Dispatch one Celery task per device × per sensor ──────────────────
    # All tasks are sent to the queue immediately (non-blocking).
    # The worker processes them one at a time (concurrency=1 by default).
    # To run multiple sensors in true parallel, increase --concurrency in
    # docker-compose.yml (requires more RAM per worker).
    pending: List[tuple] = []   # (device_id, sensor_name, celery_async_result)

    for device_id, records in device_groups.items():
        df_check = pd.DataFrame(records)
        available = [
            s for s in ALL_SENSORS
            if s in df_check.columns and df_check[s].notna().any()
        ]
        logging.info(f"[{device_id}] Dispatching tasks for: {available}")
        for sensor in available:
            # Each call to .delay() puts one task on the Celery queue
            task = run_inference_sensor.delay(device_id, sensor, records)
            pending.append((device_id, sensor, task))

    if not pending:
        return AnalyzeResponse(
            anomaly_score=0.0, risk_level="low", model="no-sensor-data"
        )

    # ── 3. Collect results without blocking the event loop ───────────────────
    # anyio.to_thread.run_sync runs the blocking .get() calls in a thread pool.
    # Each task has a 120-second timeout. Failed tasks default to score=0.
    def _collect() -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = defaultdict(dict)
        for dev_id, sensor, async_result in pending:
            try:
                res = async_result.get(timeout=120.0)
                out[dev_id][sensor] = float(res.get("score", 0.0))
            except Exception as exc:
                logging.error(f"[{dev_id}/{sensor}] Task collection failed: {exc}")
                out[dev_id][sensor] = 0.0
        return dict(out)

    device_sensor_scores = await anyio.to_thread.run_sync(_collect)

    # ── 4. Aggregate per device, then overall ────────────────────────────────
    per_device: Dict[str, DeviceResult] = {}
    for dev_id, sensor_scores in device_sensor_scores.items():
        dev_score = max(sensor_scores.values(), default=0.0)
        per_device[dev_id] = DeviceResult(
            anomaly_score=round(dev_score, 4),
            per_sensor={s: round(v, 4) for s, v in sensor_scores.items()},
        )

    overall_score = max(
        (dr.anomaly_score for dr in per_device.values()), default=0.0
    )
    worst_device = max(per_device, key=lambda d: per_device[d].anomaly_score)
    pred_level = _risk_level(overall_score)

    # ── 5. Immediate threshold check & alerting ──────────────────────────────
    score_current = max(_score(r) for r in request.telemetry)
    imm_level = _risk_level(score_current)

    event_id = alert_id = work_order_id = None
    if imm_level in {"high", "critical"}:
        event_id = str(uuid4())
        alert_id = _dispatch_alert(worst_device, imm_level, score_current)
        work_order_id = _create_work_order(worst_device, imm_level, alert_id)
        _last_events.append(
            {
                "event_id": event_id,
                "device_id": worst_device,
                "risk_level": imm_level,
                "anomaly_score": score_current,
                "alert_id": alert_id,
                "work_order_id": work_order_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    logging.info(
        f"Analysis complete — overall_score={overall_score:.4f}  "
        f"risk={pred_level}  devices={list(per_device.keys())}"
    )

    return AnalyzeResponse(
        anomaly_score=round(overall_score, 4),
        risk_level=pred_level,
        model="chronos-per-sensor",
        per_device=per_device,
        event_id=event_id,
        alert_id=alert_id,
        work_order_id=work_order_id,
    )


@app.get("/events")
def events(limit: int = 50) -> dict:
    return {"items": _last_events[-limit:]}


@app.post("/models/refresh")
def refresh_model() -> dict:
    return {"status": "queued", "message": "model refresh simulated"}

