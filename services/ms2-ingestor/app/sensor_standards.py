from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SensorStandard:
    key: str
    label: str
    unit: str
    normal_low: Optional[float]
    normal_high: Optional[float]
    warning_low: Optional[float]
    warning_high: Optional[float]
    absolute_low: Optional[float]
    absolute_high: Optional[float]
    reference: str
    note: str


SENSOR_STANDARDS: dict[str, SensorStandard] = {
    "temperature_c": SensorStandard(
        key="temperature_c",
        label="Temperature",
        unit="°C",
        normal_low=45.0,
        normal_high=90.0,
        warning_low=35.0,
        warning_high=105.0,
        absolute_low=-20.0,
        absolute_high=200.0,
        reference="Engineering baseline from machine profiles + ISA-TR20 style instrumentation ranges",
        note="Site-specific OEM limits must override these baselines in production.",
    ),
    "vibration_rms": SensorStandard(
        key="vibration_rms",
        label="Vibration RMS",
        unit="rms",
        normal_low=0.0,
        normal_high=4.5,
        warning_low=0.0,
        warning_high=7.1,
        absolute_low=0.0,
        absolute_high=50.0,
        reference="ISO 20816 severity guidance mapped to project RMS scale",
        note="Project value is normalized RMS proxy, not direct mm/s channel.",
    ),
    "rpm": SensorStandard(
        key="rpm",
        label="Rotational Speed",
        unit="rpm",
        normal_low=50.0,
        normal_high=12000.0,
        warning_low=0.0,
        warning_high=15000.0,
        absolute_low=0.0,
        absolute_high=20000.0,
        reference="Machine profile baseline + OEM spindle/pump speed envelopes",
        note="Use per-asset nameplate rpm window for final thresholds.",
    ),
    "pressure_bar": SensorStandard(
        key="pressure_bar",
        label="Pressure",
        unit="bar",
        normal_low=1.0,
        normal_high=12.0,
        warning_low=0.2,
        warning_high=16.0,
        absolute_low=0.0,
        absolute_high=25.0,
        reference="Process instrumentation baseline (typical industrial utility/process lines)",
        note="Calibrate per P&ID design pressure and relief settings.",
    ),
    "flow_lpm": SensorStandard(
        key="flow_lpm",
        label="Flow",
        unit="L/min",
        normal_low=20.0,
        normal_high=500.0,
        warning_low=5.0,
        warning_high=800.0,
        absolute_low=0.0,
        absolute_high=5000.0,
        reference="Pump/compressor process baseline from project machine profiles",
        note="Tune by line recipe and control-valve setpoint ranges.",
    ),
    "current_a": SensorStandard(
        key="current_a",
        label="Current",
        unit="A",
        normal_low=4.0,
        normal_high=65.0,
        warning_low=1.0,
        warning_high=90.0,
        absolute_low=0.0,
        absolute_high=1200.0,
        reference="IEC motor loading practice + project profile baselines",
        note="Set overload alarm from motor FLA on each asset.",
    ),
    "oil_temp_c": SensorStandard(
        key="oil_temp_c",
        label="Oil Temperature",
        unit="°C",
        normal_low=45.0,
        normal_high=85.0,
        warning_low=35.0,
        warning_high=95.0,
        absolute_low=-20.0,
        absolute_high=220.0,
        reference="Lubrication OEM guidance baseline for rotating machinery",
        note="Confirm lubricant grade-specific max film temperature.",
    ),
    "humidity_pct": SensorStandard(
        key="humidity_pct",
        label="Humidity",
        unit="%",
        normal_low=35.0,
        normal_high=70.0,
        warning_low=20.0,
        warning_high=85.0,
        absolute_low=0.0,
        absolute_high=100.0,
        reference="ASHRAE-style environmental operating envelope (adapted)",
        note="For packaging/clean zones, enforce tighter local SOP limits.",
    ),
    "power_kw": SensorStandard(
        key="power_kw",
        label="Power",
        unit="kW",
        normal_low=0.5,
        normal_high=30.0,
        warning_low=0.1,
        warning_high=45.0,
        absolute_low=0.0,
        absolute_high=2500.0,
        reference="Project machine profile baseline + utility load engineering practice",
        note="Set per-machine expected load curve for best anomaly precision.",
    ),
}


def evaluate_sensor_value(key: str, value: Optional[float]) -> str:
    if value is None:
        return "missing"

    standard = SENSOR_STANDARDS.get(key)
    if not standard:
        return "unknown"

    if standard.absolute_low is not None and value < standard.absolute_low:
        return "critical"
    if standard.absolute_high is not None and value > standard.absolute_high:
        return "critical"
    if standard.warning_low is not None and value < standard.warning_low:
        return "critical"
    if standard.warning_high is not None and value > standard.warning_high:
        return "critical"
    if standard.normal_low is not None and value < standard.normal_low:
        return "warning"
    if standard.normal_high is not None and value > standard.normal_high:
        return "warning"
    return "normal"


def standards_as_dict() -> dict[str, dict]:
    return {
        key: {
            "label": value.label,
            "unit": value.unit,
            "normal_low": value.normal_low,
            "normal_high": value.normal_high,
            "warning_low": value.warning_low,
            "warning_high": value.warning_high,
            "absolute_low": value.absolute_low,
            "absolute_high": value.absolute_high,
            "reference": value.reference,
            "note": value.note,
        }
        for key, value in SENSOR_STANDARDS.items()
    }
