from __future__ import annotations

"""
Sim Sensor Service
==================

Generates synthetic industrial telemetry and publishes it to MQTT.

Behavior summary:
- Runs an infinite loop with randomized interval in 1-5 seconds (default).
- Simulates up to 9 sensor dimensions per machine profile.
- Uses Gaussian noise to mimic natural sensor variance.
- Intentionally injects outliers to validate downstream cleaning/clamping.
- Publishes JSON packets via MQTT QoS 1 to support at-least-once delivery.

Preferred packet contract:
{
    "device_id": "pump-01",
    "ts": "...",
    "metrics": { ... sensor fields ... }
}
"""

# -- Configuration ---------------------------------------------------------
# These values are read from environment variables so the simulator can run
# in different deployment modes without code changes.
#
# - MQTT settings: where to publish telemetry.
# - INTERVAL_OPTIONS_SEC: choose send interval options.
# - BASE_ANOMALY_RATE: chance of a synthetic anomaly on each sample.
# - MACHINE_COUNT: number of active device profiles to simulate.
# - NETWORK_DROP_RATE: simulate temporary broker/network outages.
# - MANUAL_TRIGGER_FILE: external file trigger for manual anomaly injection.

import json
import math
import os
import queue
import random
import threading
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app.machine_profiles import CORE_MACHINE_PROFILES, MachineProfile

BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("MQTT_TOPIC", "omnivigil/telemetry")
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
INTERVAL_MS = int(os.getenv("INTERVAL_MS", "5000"))
INTERVAL_OPTIONS_SEC_RAW = os.getenv("INTERVAL_OPTIONS_SEC", "1,2,3,4,5")
BASE_ANOMALY_RATE = float(os.getenv("ANOMALY_RATE", "0.03"))

MACHINE_COUNT = int(os.getenv("MACHINE_COUNT", "5"))
MACHINE_IDS = os.getenv("MACHINE_IDS", "").strip()

NETWORK_DROP_RATE = float(os.getenv("NETWORK_DROP_RATE", "0.02"))
NETWORK_DROP_DURATION_SEC = float(os.getenv("NETWORK_DROP_DURATION_SEC", "8"))

MANUAL_TRIGGER_FILE = os.getenv("MANUAL_TRIGGER_FILE", "/tmp/force_anomaly")
LOG_EVERY_N_MESSAGES = int(os.getenv("LOG_EVERY_N_MESSAGES", "20"))


@dataclass
class MachineState:
    profile: MachineProfile
    device_id: str
    base_temp: float
    base_vib: float
    base_rpm: float
    drift: float = 0.0
    step: int = 0


force_spike_queue: queue.Queue[str] = queue.Queue()
network_down_until = 0.0
sent_counter = 0


def _parse_interval_options(raw: str) -> list[float]:
    """Parse comma-separated interval options into positive float seconds."""
    options: list[float] = []
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            sec = float(value)
            if sec > 0:
                options.append(sec)
        except ValueError:
            continue

    if options:
        return options
    return [max(INTERVAL_MS / 1000.0, 1.0)]


INTERVAL_OPTIONS_SEC = _parse_interval_options(INTERVAL_OPTIONS_SEC_RAW)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_machine(profile: MachineProfile) -> MachineState:
    """Create runtime state object from static machine profile."""
    return MachineState(
        profile=profile,
        device_id=profile.device_id,
        base_temp=profile.temp_base,
        base_vib=profile.vib_base,
        base_rpm=profile.rpm_base,
    )


def select_profiles() -> list[MachineProfile]:
    """Select machine profiles based on MACHINE_IDS and MACHINE_COUNT settings."""
    profiles = CORE_MACHINE_PROFILES

    if MACHINE_IDS:
        selected_ids = {item.strip() for item in MACHINE_IDS.split(",") if item.strip()}
        profiles = [profile for profile in CORE_MACHINE_PROFILES if profile.device_id in selected_ids]

    if not profiles:
        profiles = CORE_MACHINE_PROFILES

    return profiles[: max(1, min(MACHINE_COUNT, len(profiles)))]


def maybe_trigger_network_outage() -> bool:
    """Simulate temporary network outage windows for resilience testing."""
    global network_down_until
    now = time.time()

    if now < network_down_until:
        return True

    if random.random() < NETWORK_DROP_RATE:
        network_down_until = now + NETWORK_DROP_DURATION_SEC
        print(f"[sim] network drop starts for {NETWORK_DROP_DURATION_SEC:.1f}s")
        return True

    return False


def build_payload(machine: MachineState, force_spike: bool) -> dict:
    """Build one telemetry packet.

    This function simulates realistic industrial sensor behavior by combining:
    - baseline values from the machine profile
    - sinusoidal oscillation
    - Gaussian noise
    - slow drift
    - occasional forced anomalies or outliers

    The output is always normalized into the expected packet shape used by MS2.
    """
    phase = machine.step / 14.0
    temp = machine.base_temp + machine.profile.temp_amp * math.sin(phase) + random.gauss(0.0, 0.45) + machine.drift
    vib = machine.base_vib + machine.profile.vib_amp * math.sin(machine.step / 9.0) + random.gauss(0.0, 0.10)
    rpm = machine.base_rpm + machine.profile.rpm_amp * math.sin(machine.step / 17.0) + random.gauss(0.0, 6.0)

    pressure = None
    flow = None
    current = None
    oil_temp = None
    humidity = None
    power_kw = None

    if machine.profile.pressure_bar_base is not None:
        pressure = machine.profile.pressure_bar_base + 0.35 * math.sin(machine.step / 11.0) + random.gauss(0.0, 0.08)
    if machine.profile.flow_lpm_base is not None:
        flow = machine.profile.flow_lpm_base + 11.0 * math.sin(machine.step / 8.0) + random.gauss(0.0, 1.8)
    if machine.profile.current_a_base is not None:
        current = machine.profile.current_a_base + 2.8 * math.sin(machine.step / 10.0) + random.gauss(0.0, 0.5)
    if machine.profile.oil_temp_c_base is not None:
        oil_temp = machine.profile.oil_temp_c_base + 2.4 * math.sin(machine.step / 12.0) + random.gauss(0.0, 0.4)
    if machine.profile.humidity_pct_base is not None:
        humidity = machine.profile.humidity_pct_base + 3.0 * math.sin(machine.step / 14.0) + random.gauss(0.0, 0.6)
    if machine.profile.power_kw_base is not None:
        power_kw = machine.profile.power_kw_base + 1.1 * math.sin(machine.step / 9.0) + random.gauss(0.0, 0.2)

    auto_anomaly = random.random() < BASE_ANOMALY_RATE
    if auto_anomaly or force_spike:
        temp += random.uniform(14.0, 28.0)
        vib += random.uniform(3.8, 7.2)
        rpm += random.uniform(90.0, 170.0)
        if pressure is not None:
            pressure += random.uniform(0.6, 1.4)
        if flow is not None:
            flow -= random.uniform(25.0, 45.0)
        if current is not None:
            current += random.uniform(4.5, 8.0)
        if oil_temp is not None:
            oil_temp += random.uniform(4.5, 9.0)
        if power_kw is not None:
            power_kw += random.uniform(1.5, 3.2)

        # Inject one explicit outlier field so downstream clean/clamp logic is always exercised.
        outlier_field = random.choice(["temperature_c", "vibration_rms", "rpm", "pressure_bar", "current_a"])
        if outlier_field == "temperature_c":
            temp = random.uniform(220.0, 500.0)
        elif outlier_field == "vibration_rms":
            vib = random.uniform(70.0, 120.0)
        elif outlier_field == "rpm":
            rpm = random.uniform(25000.0, 40000.0)
        elif outlier_field == "pressure_bar" and pressure is not None:
            pressure = random.uniform(40.0, 80.0)
        elif outlier_field == "current_a" and current is not None:
            current = random.uniform(1800.0, 3000.0)

    machine.drift = min(machine.drift + 0.0035, 16.0)
    machine.step += 1

    metrics = {
        "temperature_c": round(temp, 2),
        "vibration_rms": round(max(0.1, vib), 3),
        "rpm": round(max(0.0, rpm), 1),
    }

    if pressure is not None:
        metrics["pressure_bar"] = round(max(0.0, pressure), 3)
    if flow is not None:
        metrics["flow_lpm"] = round(max(0.0, flow), 2)
    if current is not None:
        metrics["current_a"] = round(max(0.0, current), 3)
    if oil_temp is not None:
        metrics["oil_temp_c"] = round(max(0.0, oil_temp), 2)
    if humidity is not None:
        metrics["humidity_pct"] = round(min(100.0, max(0.0, humidity)), 2)
    if power_kw is not None:
        metrics["power_kw"] = round(max(0.0, power_kw), 3)

    payload = {
        "device_id": machine.device_id,
        "machine_type": machine.profile.machine_type,
        "line": machine.profile.line,
        "zone": machine.profile.zone,
        "ts": now_utc().isoformat(),
        "metrics": metrics,
    }

    return payload


def start_manual_command_listener() -> None:
    """Start stdin command listener for manual anomaly injection commands."""
    def _listen() -> None:
        print("[sim] commands: spike <device-id|all>")
        while True:
            try:
                raw = input().strip()
                if not raw:
                    continue
                parts = raw.split(maxsplit=1)
                if parts[0].lower() != "spike":
                    continue
                target = parts[1].strip() if len(parts) > 1 else "all"
                force_spike_queue.put(target)
                print(f"[sim] manual spike requested target={target}")
            except EOFError:
                return
            except Exception as exc:
                print(f"[sim] input listener error: {exc}")
                time.sleep(0.3)

    thread = threading.Thread(target=_listen, daemon=True)
    thread.start()


def consume_file_trigger() -> str | None:
    """Read and consume one-shot anomaly trigger from a file if present."""
    if not MANUAL_TRIGGER_FILE:
        return None
    if not os.path.exists(MANUAL_TRIGGER_FILE):
        return None

    try:
        with open(MANUAL_TRIGGER_FILE, "r", encoding="utf-8") as trigger_file:
            content = trigger_file.read().strip()
        os.remove(MANUAL_TRIGGER_FILE)
        return content or "all"
    except Exception as exc:
        print(f"[sim] trigger file read error: {exc}")
        return None


def pick_spike_targets(machines: list[MachineState]) -> set[str]:
    """Resolve which machine IDs should receive forced anomaly spikes this cycle."""
    targets: set[str] = set()

    file_trigger = consume_file_trigger()
    if file_trigger:
        targets.add(file_trigger)

    while True:
        try:
            targets.add(force_spike_queue.get_nowait())
        except queue.Empty:
            break

    if "all" in targets:
        return {m.device_id for m in machines}
    return targets


def main() -> None:
    """Entrypoint: connect MQTT and continuously publish machine telemetry."""
    global sent_counter

    selected_profiles = select_profiles()
    machines = [create_machine(profile) for profile in selected_profiles]
    interval_text = ",".join(str(int(value)) if float(value).is_integer() else f"{value:.1f}" for value in INTERVAL_OPTIONS_SEC)
    print(f"[sim] start: machines={len(machines)}, interval_options_sec=[{interval_text}], topic={TOPIC}")
    print("[sim] selected machines:")
    for machine in machines:
        print(f"  - {machine.device_id} ({machine.profile.machine_type}, line={machine.profile.line}, zone={machine.profile.zone})")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"sim-sensor-{random.randint(100, 999)}"
    )
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
    if PORT == 8883 or str(os.getenv("MQTT_USE_TLS", "")).lower() in ["true", "1", "yes"]:
        client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    # Start a background keyboard listener so operator can manually force
    # an anomaly with "spike <device-id>" or "spike all".
    start_manual_command_listener()

    while True:
        sleep_sec = random.choice(INTERVAL_OPTIONS_SEC)
        if maybe_trigger_network_outage():
            time.sleep(sleep_sec)
            continue

        forced_targets = pick_spike_targets(machines)
        for machine in machines:
            force_spike = machine.device_id in forced_targets
            payload = build_payload(machine, force_spike=force_spike)
            client.publish(TOPIC, json.dumps(payload), qos=1)
            sent_counter += 1

            if force_spike:
                print(f"[sim] manual anomaly injected for {machine.device_id}")

        if sent_counter % LOG_EVERY_N_MESSAGES == 0:
            print(f"[sim] published_messages={sent_counter}")

        time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
