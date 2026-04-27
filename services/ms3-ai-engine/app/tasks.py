"""
MS3 AI Engine — Celery Tasks
============================

Architecture (per-sensor, per-device parallelism):
  main.py (FastAPI server)
    └─ groups incoming telemetry by device_id
    └─ for each device, dispatches ONE Celery task per sensor
    └─ waits for all tasks in parallel, then aggregates scores

  run_inference_sensor  ← the only Celery task
    └─ receives: device_id, sensor_name, list of readings
    └─ resamples ONE column (no string-dtype crash)
    └─ runs Chronos forecast
    └─ returns anomaly score for that sensor

NOTE: ms3-worker runs with --concurrency=1 by default.
  Each task runs strictly one at a time on the worker.
  Increase --concurrency in docker-compose.yml to run multiple
  sensor tasks in true parallel (requires more RAM per worker).
"""

import os
import logging
from typing import List, Dict
import pandas as pd
from datetime import datetime, timezone
from app.celery_app import celery_app
from app.sensors import ALL_SENSORS as SENSOR_NAMES, score_sensor_value

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("ms3-tasks")

# ── Sensor catalogue ────────────────────────────────────────────────────────
# All 9 sensors this system monitors. main.py uses this list to decide which
# sensor tasks to dispatch (only those actually present in the payload).
ALL_SENSORS = SENSOR_NAMES

# ── Per-sensor anomaly thresholds ────────────────────────────────────────────
# score = clamp((predicted_p90 − warn) / range, 0.0, 1.0)
# Tune these based on real operating conditions.
SENSOR_THRESHOLDS: Dict[str, Dict[str, float]] = {}

# ── Chronos model (lazy-loaded once per worker process) ──────────────────────
_pipeline = None


def get_pipeline():
    """Load and cache the Chronos model (one instance per Celery worker process)."""
    global _pipeline
    if _pipeline is None:
        import torch
        from chronos import BaseChronosPipeline

        model_id = os.getenv("CHRONOS_MODEL_ID", "Stalemartyr/chronos-finetuned")
        requested_device = os.getenv("CHRONOS_DEVICE", "auto").strip().lower()
        cuda_available = torch.cuda.is_available()

        if requested_device == "cuda" and not cuda_available:
            logger.warning("CHRONOS_DEVICE=cuda requested but CUDA is unavailable; falling back to CPU.")

        device = "cuda" if cuda_available and requested_device in {"auto", "cuda"} else "cpu"
        logger.info(f"Loading Chronos model '{model_id}' on {device} ...")
        _pipeline = BaseChronosPipeline.from_pretrained(
            model_id, device_map=device
        )
        logger.info("Chronos model ready.")
    return _pipeline


def _score_sensor(predicted_value: float, sensor_name: str) -> float:
    """
    Map a sensor's predicted worst-case value to an anomaly score [0.0, 1.0].
    0.0 = well within normal range.  1.0 = critical anomaly.
    """
    return score_sensor_value(predicted_value, sensor_name)


# ── Celery task ──────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.run_inference_sensor")
def run_inference_sensor(
    device_id: str,
    sensor_name: str,
    records: List[Dict],
) -> Dict:
    """
    Run Chronos ML inference for ONE sensor of ONE device.

    Args:
        device_id:   Machine identifier, e.g. "CNC-001"
        sensor_name: Which sensor column to analyse, e.g. "temperature_c"
        records:     List of telemetry dicts (must include "timestamp" and sensor column)

    Returns:
        {
            "device_id": str,
            "sensor":    str,
            "score":     float,   # 0.0 (normal) → 1.0 (critical anomaly)
            "timestamp": str,     # ISO-8601 UTC
        }
    """
    id_col = "device_id"
    ts_col = "timestamp"
    prediction_length = 24   # forecast steps (e.g. 24 × 10 s = 4 minutes ahead)

    _zero = {
        "device_id": device_id,
        "sensor": sensor_name,
        "score": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        df = pd.DataFrame(records)

        # Guard: sensor column must exist and have at least some data
        if sensor_name not in df.columns or df[sensor_name].isna().all():
            logger.warning(f"[{device_id}/{sensor_name}] Column missing or all-NaN — skipping.")
            return _zero

        # ── 1. Keep ONLY timestamp + this sensor (avoids dtype-str crash on resample) ──
        df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
        df[sensor_name] = pd.to_numeric(df[sensor_name], errors="coerce")
        df_clean = df[[ts_col, sensor_name]].sort_values(ts_col)

        # Fill gaps: forward-fill → back-fill → zero for any remaining NaN
        df_clean[sensor_name] = df_clean[sensor_name].ffill().bfill().fillna(0.0)

        # ── 2. Resample to a fixed 10-second grid ────────────────────────────────
        df_resampled = (
            df_clean.set_index(ts_col)[[sensor_name]]
            .resample("10s")
            .mean()
            .interpolate(method="slinear")
            .reset_index()
        )
        # Chronos requires an id column alongside the time series
        df_resampled[id_col] = device_id

        if len(df_resampled) < 10:
            logger.warning(
                f"[{device_id}/{sensor_name}] Only {len(df_resampled)} rows after resample — "
                "using threshold fallback."
            )
            worst_current = float(df_clean[sensor_name].max())
            return {
                "device_id": device_id,
                "sensor": sensor_name,
                "score": _score_sensor(worst_current, sensor_name),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"[{device_id}/{sensor_name}] Running Chronos on {len(df_resampled)} rows "
            f"(forecast {prediction_length} steps) ..."
        )

        # ── 3. Chronos forecast ───────────────────────────────────────────────────
        try:
            pipeline = get_pipeline()
        except Exception as exc:
            logger.warning(
                f"[{device_id}/{sensor_name}] Chronos unavailable, using threshold fallback: {exc}"
            )
            worst_current = float(df_resampled[sensor_name].max())
            return {
                "device_id": device_id,
                "sensor": sensor_name,
                "score": _score_sensor(worst_current, sensor_name),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        df_pred = pipeline.predict_df(
            df_resampled,
            prediction_length=prediction_length,
            quantile_levels=[0.1, 0.5, 0.9],
            id_column=id_col,
            timestamp_column=ts_col,
            target=[sensor_name],      # single-column target list
        )

        # ── 4. Score: use worst (max) of the 90th-percentile forecast values ──────
        # df_pred columns: id_col, ts_col, "target_name", "0.1", "0.5", "0.9"
        p90_values = df_pred["0.9"].dropna().tolist()
        if not p90_values:
            logger.warning(f"[{device_id}/{sensor_name}] No p90 predictions returned.")
            return _zero

        worst_p90 = float(max(p90_values))
        score = _score_sensor(worst_p90, sensor_name)

        logger.info(
            f"[{device_id}/{sensor_name}] worst_p90={worst_p90:.3f}  score={score:.4f}"
        )
        return {
            "device_id": device_id,
            "sensor": sensor_name,
            "score": score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(
            f"[{device_id}/{sensor_name}] Inference failed: {exc}", exc_info=True
        )
        return _zero
