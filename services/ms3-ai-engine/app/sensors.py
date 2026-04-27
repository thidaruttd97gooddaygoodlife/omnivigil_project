from __future__ import annotations

from typing import Dict, List


ALL_SENSORS: List[str] = [
    "temperature_c",
    "vibration_rms",
    "rpm",
    "pressure_bar",
    "flow_lpm",
    "current_a",
    "oil_temp_c",
    "humidity_pct",
    "power_kw",
]


SENSOR_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "temperature_c": {"warn": 70.0, "range": 40.0},
    "vibration_rms": {"warn": 4.0, "range": 6.0},
    "rpm": {"warn": 1500.0, "range": 500.0},
    "pressure_bar": {"warn": 8.0, "range": 4.0},
    "flow_lpm": {"warn": 50.0, "range": 30.0},
    "current_a": {"warn": 20.0, "range": 10.0},
    "oil_temp_c": {"warn": 80.0, "range": 30.0},
    "humidity_pct": {"warn": 80.0, "range": 20.0},
    "power_kw": {"warn": 15.0, "range": 5.0},
}


def score_sensor_value(value: float, sensor_name: str) -> float:
    if sensor_name not in SENSOR_THRESHOLDS:
        return 0.0

    threshold = SENSOR_THRESHOLDS[sensor_name]
    return float(
        max(0.0, min(1.0, (value - threshold["warn"]) / threshold["range"]))
    )
