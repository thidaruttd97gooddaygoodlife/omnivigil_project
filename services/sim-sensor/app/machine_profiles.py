from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MachineProfile:
    device_id: str
    machine_type: str
    line: str
    zone: str
    temp_base: float
    temp_amp: float
    vib_base: float
    vib_amp: float
    rpm_base: float
    rpm_amp: float
    pressure_bar_base: float | None = None
    flow_lpm_base: float | None = None
    current_a_base: float | None = None
    oil_temp_c_base: float | None = None
    humidity_pct_base: float | None = None
    power_kw_base: float | None = None


CORE_MACHINE_PROFILES: list[MachineProfile] = [
    MachineProfile(
        device_id="mix-pump-101",
        machine_type="centrifugal_pump",
        line="mixing",
        zone="A1",
        temp_base=61.5,
        temp_amp=4.5,
        vib_base=1.8,
        vib_amp=0.55,
        rpm_base=1480.0,
        rpm_amp=35.0,
        pressure_bar_base=4.2,
        flow_lpm_base=285.0,
        current_a_base=28.0,
        power_kw_base=11.0,
    ),
    MachineProfile(
        device_id="filling-comp-201",
        machine_type="air_compressor",
        line="filling",
        zone="B2",
        temp_base=74.0,
        temp_amp=5.0,
        vib_base=2.2,
        vib_amp=0.65,
        rpm_base=2960.0,
        rpm_amp=70.0,
        pressure_bar_base=7.6,
        current_a_base=33.5,
        oil_temp_c_base=69.0,
        power_kw_base=18.5,
    ),
    MachineProfile(
        device_id="cnc-spindle-301",
        machine_type="cnc_spindle",
        line="machining",
        zone="C3",
        temp_base=67.0,
        temp_amp=6.5,
        vib_base=1.5,
        vib_amp=0.45,
        rpm_base=10800.0,
        rpm_amp=850.0,
        current_a_base=24.0,
        oil_temp_c_base=62.0,
        power_kw_base=7.5,
    ),
    MachineProfile(
        device_id="boiler-feed-401",
        machine_type="boiler_feed_pump",
        line="utilities",
        zone="U1",
        temp_base=83.0,
        temp_amp=4.0,
        vib_base=2.6,
        vib_amp=0.8,
        rpm_base=3520.0,
        rpm_amp=85.0,
        pressure_bar_base=9.8,
        flow_lpm_base=118.0,
        current_a_base=40.5,
        power_kw_base=22.0,
    ),
    MachineProfile(
        device_id="pack-conveyor-501",
        machine_type="conveyor_gearmotor",
        line="packaging",
        zone="D1",
        temp_base=49.0,
        temp_amp=3.8,
        vib_base=1.2,
        vib_amp=0.35,
        rpm_base=92.0,
        rpm_amp=6.0,
        current_a_base=11.5,
        humidity_pct_base=58.0,
        power_kw_base=2.2,
    ),
]
