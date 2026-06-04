from __future__ import annotations

from typing import Dict, List, Optional


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


SENSOR_THRESHOLDS: Dict[str, Dict[str, Optional[float]]] = {
    "temperature_c": {"normal_low": 45.0, "normal_high": 90.0, "warning_low": 35.0, "warning_high": 105.0},
    "vibration_rms": {"normal_low": 0.0, "normal_high": 4.5, "warning_low": 0.0, "warning_high": 7.1},
    "rpm": {"normal_low": 50.0, "normal_high": 12000.0, "warning_low": 0.0, "warning_high": 15000.0},
    "pressure_bar": {"normal_low": 1.0, "normal_high": 12.0, "warning_low": 0.2, "warning_high": 16.0},
    "flow_lpm": {"normal_low": 20.0, "normal_high": 500.0, "warning_low": 5.0, "warning_high": 800.0},
    "current_a": {"normal_low": 4.0, "normal_high": 65.0, "warning_low": 1.0, "warning_high": 90.0},
    "oil_temp_c": {"normal_low": 45.0, "normal_high": 85.0, "warning_low": 35.0, "warning_high": 95.0},
    "humidity_pct": {"normal_low": 35.0, "normal_high": 70.0, "warning_low": 20.0, "warning_high": 85.0},
    "power_kw": {"normal_low": 0.5, "normal_high": 30.0, "warning_low": 0.1, "warning_high": 45.0},
}


def score_sensor_value(value: float, sensor_name: str) -> float:
    if sensor_name not in SENSOR_THRESHOLDS:
        return 0.0

    threshold = SENSOR_THRESHOLDS[sensor_name]
    normal_low = threshold["normal_low"]
    normal_high = threshold["normal_high"]
    warning_low = threshold["warning_low"]
    warning_high = threshold["warning_high"]

    if normal_low is not None and value < normal_low:
        if warning_low is None or normal_low <= warning_low:
            return 0.3
        distance = (normal_low - value) / (normal_low - warning_low)
        return float(max(0.3, min(1.0, 0.3 + (0.7 * distance))))

    if normal_high is not None and value > normal_high:
        if warning_high is None or warning_high <= normal_high:
            return 0.3
        distance = (value - normal_high) / (warning_high - normal_high)
        return float(max(0.3, min(1.0, 0.3 + (0.7 * distance))))

    return 0.0
