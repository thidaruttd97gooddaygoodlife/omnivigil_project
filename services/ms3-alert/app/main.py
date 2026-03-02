from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="MS3 Alert", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AlertRequest(BaseModel):
    machine_id: str
    risk_level: str
    anomaly_score: float
    message: Optional[str] = None
    channels: List[str] = ["line", "toast", "sound"]


class AlertResponse(BaseModel):
    alert_id: str
    status: str
    sent_at: str
    line_message: str
    toast_message: str


_alerts: List[dict] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ms3-alert"}


@app.post("/alerts", response_model=AlertResponse)
def create_alert(request: AlertRequest) -> AlertResponse:
    alert_id = str(uuid4())
    sent_at = datetime.now(timezone.utc).isoformat()
    line_message = f"LINE: {request.machine_id} risk {request.risk_level} score {request.anomaly_score}"
    toast_message = f"ALERT: {request.machine_id} is {request.risk_level}"

    payload = {
        "alert_id": alert_id,
        "sent_at": sent_at,
        "machine_id": request.machine_id,
        "risk_level": request.risk_level,
        "anomaly_score": request.anomaly_score,
        "channels": request.channels,
        "message": request.message,
    }
    _alerts.append(payload)

    return AlertResponse(
        alert_id=alert_id,
        status="sent",
        sent_at=sent_at,
        line_message=line_message,
        toast_message=toast_message,
    )


@app.get("/alerts")
def list_alerts(limit: int = 50) -> dict:
    return {"items": _alerts[-limit:]}


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict:
    for item in _alerts:
        if item["alert_id"] == alert_id:
            return item
    return {"error": "not_found"}
