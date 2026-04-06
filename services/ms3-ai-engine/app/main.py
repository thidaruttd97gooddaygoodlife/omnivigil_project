from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import numpy as np
import torch
import pandas as pd  # requires: pip install 'pandas[pyarrow]'
from chronos import Chronos2Pipeline,BaseChronosPipeline

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


logging.info(f"PyTorch version: {torch.__version__}")
logging.info(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    logging.info(f"GPU Name: {torch.cuda.get_device_name(0)}")
device = "cuda" if torch.cuda.is_available() else "cpu"

pipeline = BaseChronosPipeline.from_pretrained("Stalemartyr/chronos-finetuned", device_map=device)

if pipeline:
    logging.info("Successfully loaded Chronos2Pipeline model")
else:
    logging.error("Failed to load Chronos2Pipeline model")


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

def telemetry_to_dataframe(telemetry_list: List[TelemetryReading]) -> pd.DataFrame:
    """Converts a list of TelemetryReading Pydantic models to a Pandas DataFrame."""
    # Use model_dump() for Pydantic V2 (use .dict() if you are on V1)
    data = [reading.model_dump() for reading in telemetry_list]
    return pd.DataFrame(data)

def dataframe_to_telemetry(df: pd.DataFrame, value_column: str = '0.9') -> List[TelemetryReading]:
    """
    Converts a long-format Pandas DataFrame back to a list of TelemetryReading Pydantic models.
    
    Args:
        df: The input dataframe containing 'id', 'timestamp', 'target_name', and the value column.
        value_column: The column to use for the actual metric values (e.g., 'predictions', '0.5').
    """
    # 1. Rename 'id' to 'device_id' to match the Pydantic model
    df_renamed = df.rename(columns={'id': 'device_id'})
    
    # 2. Pivot the DataFrame so that 'target_name' values become individual columns.
    # Group by device_id and timestamp to consolidate rows belonging to the same reading.
    df_pivoted = df_renamed.pivot_table(
        index=['device_id', 'timestamp'], 
        columns='target_name', 
        values=value_column
    ).reset_index()
    
    # 3. Ensure all required columns exist (in case the input batch is missing some targets)
    expected_cols = ['temperature_c', 'vibration_rms', 'rpm']
    for col in expected_cols:
        if col not in df_pivoted.columns:
            df_pivoted[col] = np.nan
            
    # 4. Pandas converts None to NaN for float columns. 
    # We must replace NaNs with None so Pydantic's Optional[float] accepts it.
    df_cleaned = df_pivoted.replace({np.nan: None})
    
    # 5. Convert DataFrame rows to a list of dictionaries
    records = df_cleaned.to_dict(orient='records')
    
    # 6. Unpack dictionaries back into Pydantic models
    return [TelemetryReading(**record) for record in records]

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

def _score_pred(reading: TelemetryReading) -> float:
    score = 0.0
    score += max(0.0, (reading.temperature_c - 70.0) / 40.0)
    score += max(0.0, (reading.vibration_rms - 4.0) / 6.0)
    if reading.rpm and reading.rpm > 1500:
        score += 0.1
    return max(0.0, min(1.0, score /0.8 ))

def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"


def _risk_level_pred(score: float) -> str:
    if score >= 0.7:
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
    id_column = "device_id"
    timestamp_column = "timestamp"
    target = ["temperature_c", "vibration_rms", "rpm"]
    prediction_length=24
    
    if not request.telemetry:
        return AnalyzeResponse(anomaly_score=0.0, risk_level="low", model="simulated")
    logging.info(f"Received telemetry for device {request.telemetry[0].device_id} with {len(request.telemetry)} readings")
    timeseries_id = request.telemetry[0].device_id
    df = telemetry_to_dataframe(request.telemetry)
    df[timestamp_column] = pd.to_datetime(df[timestamp_column])
    # sales_context_df = sales_context_df[sales_context_df[id_column]== timeseries_id]
    # df = df.drop(columns=['machine_type','line','zone'])
    df = df.ffill().bfill().fillna(0)
    df = df.sort_values(by=[id_column, timestamp_column])
    logging.info(f"Telemetry DataFrame head:\n{df[[id_column] + target].head()}")
    df_resampled = df.drop(columns=['device_id']).set_index(timestamp_column).resample('10s').mean().interpolate(method='slinear').reset_index()
    df_resampled['device_id'] = timeseries_id
    
    df_pred = pipeline.predict_df(
    df_resampled,
    prediction_length=prediction_length,
    quantile_levels=[0.1, 0.5, 0.9],
    id_column=id_column,
    timestamp_column=timestamp_column,
    target=target,
    
    )
    logging.info(f"Model predictions: {df_pred[['target_name', 'predictions']]}")
    pred_telemetry = dataframe_to_telemetry(df_pred)

    score = max(_score(item) for item in request.telemetry[-1:])
    score_pred = max(0, max(_score_pred(item) for item in pred_telemetry))
    level = _risk_level(score)
    pred_level = _risk_level_pred(score_pred)
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
        anomaly_score=round(score_pred, 4),
        risk_level=pred_level,
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
