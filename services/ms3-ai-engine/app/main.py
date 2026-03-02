from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

app = FastAPI(title="MS3 AI Engine", version="0.1.0")

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


class AnalyzeRequest(BaseModel):
    telemetry: List[TelemetryReading]


class AnalyzeResponse(BaseModel):
    anomaly_score: float
    risk_level: str
    model: str
    event_id: Optional[str] = None
    alert_id: Optional[str] = None
    work_order_id: Optional[str] = None


_last_events: List[dict] = []
_alert_url = os.getenv("ALERT_URL", "http://localhost:8004")
_maintenance_url = os.getenv("MAINTENANCE_URL", "http://localhost:8005")


def _score(reading: TelemetryReading) -> float:
    score = 0.0
    score += max(0.0, (reading.temperature_c - 70.0) / 40.0)
    score += max(0.0, (reading.vibration_rms - 4.0) / 6.0)
    if reading.rpm and reading.rpm > 1500:
        score += 0.1
    return max(0.0, min(1.0, score / 2.0))


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.3:
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
        response = httpx.post(f"{_alert_url}/alerts", json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json().get("alert_id")
    except httpx.HTTPError:
        return None


def _create_work_order(device_id: str, level: str, alert_id: Optional[str]) -> Optional[str]:
    payload = {
        "machine_id": device_id,
        "issue": f"Investigate {level} anomaly",
        "priority": "high" if level in {"high", "critical"} else "medium",
        "source_alert_id": alert_id,
    }
    try:
        response = httpx.post(f"{_maintenance_url}/work-orders", json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json().get("work_order_id")
    except httpx.HTTPError:
        return None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ms3-ai-engine"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    if not request.telemetry:
        return AnalyzeResponse(anomaly_score=0.0, risk_level="low", model="simulated")

    score = max(_score(item) for item in request.telemetry)
    level = _risk_level(score)
    event_id = None
    alert_id = None
    work_order_id = None

    if level in {"high", "critical"}:
        event_id = str(uuid4())
        device_id = request.telemetry[0].device_id
        alert_id = _dispatch_alert(device_id, level, score)
        work_order_id = _create_work_order(device_id, level, alert_id)
        _last_events.append(
            {
                "event_id": event_id,
                "risk_level": level,
                "anomaly_score": score,
                "alert_id": alert_id,
                "work_order_id": work_order_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    return AnalyzeResponse(
        anomaly_score=round(score, 4),
        risk_level=level,
        model="bi_lstm+pso+isolation_forest (simulated)",
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
