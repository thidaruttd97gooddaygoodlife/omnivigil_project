import os
import logging
from typing import List
import pandas as pd
import numpy as np
import torch
from chronos import BaseChronosPipeline
from pydantic import BaseModel
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger("ms3-worker")

# ML Model Setup
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Loading model on device: {device}")

# Global pipeline instance in the worker
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        logger.info("Initializing Chronos model...")
        _pipeline = BaseChronosPipeline.from_pretrained("Stalemartyr/chronos-finetuned", device_map=device)
        logger.info("Model loaded successfully")
    return _pipeline

class TelemetryReading(BaseModel):
    device_id: str
    timestamp: datetime
    temperature_c: float
    vibration_rms: float
    rpm: float | None = None

def _score_pred(reading: TelemetryReading) -> float:
    score = 0.0
    score += max(0.0, (reading.temperature_c - 70.0) / 40.0)
    score += max(0.0, (reading.vibration_rms - 4.0) / 6.0)
    if reading.rpm and reading.rpm > 1500:
        score += 0.1
    return max(0.0, min(1.0, score / 0.8))

def run_inference(telemetry_data: List[dict]) -> dict:
    """
    Runs the heavy ML inference. This is meant to be called in a separate process or worker.
    """
    id_column = "device_id"
    timestamp_column = "timestamp"
    target = ["temperature_c", "vibration_rms", "rpm"]
    prediction_length = 24

    df = pd.DataFrame(telemetry_data)
    df[timestamp_column] = pd.to_datetime(df[timestamp_column])
    timeseries_id = df[id_column].iloc[0]
    
    df = df.ffill().bfill().fillna(0)
    df = df.sort_values(by=[id_column, timestamp_column])
    
    df_resampled = df.drop(columns=[id_column]).set_index(timestamp_column).resample('10s').mean().interpolate(method='slinear').reset_index()
    df_resampled[id_column] = timeseries_id

    pipeline = get_pipeline()
    df_pred = pipeline.predict_df(
        df_resampled,
        prediction_length=prediction_length,
        quantile_levels=[0.1, 0.5, 0.9],
        id_column=id_column,
        timestamp_column=timestamp_column,
        target=target,
    )

    # Convert predictions back to scores
    # Simplified: use the 0.9 quantile as the predicted value
    df_renamed = df_pred.rename(columns={'id': 'device_id'})
    df_pivoted = df_renamed.pivot_table(
        index=['device_id', 'timestamp'], 
        columns='target_name', 
        values='0.9'
    ).reset_index().replace({np.nan: None})
    
    pred_readings = [TelemetryReading(**record) for record in df_pivoted.to_dict(orient='records')]
    
    score_pred = max(0, max(_score_pred(item) for item in pred_readings))
    
    return {
        "anomaly_score": round(score_pred, 4),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
