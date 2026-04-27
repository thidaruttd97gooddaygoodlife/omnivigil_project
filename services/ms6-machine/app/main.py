from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from pathlib import Path
import json
import os

app = FastAPI(title="MS6 Machine System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path(os.getenv("MACHINE_DATA_FILE", "/data/machines.json"))
OFFLINE_AFTER_MINUTES = float(os.getenv("MACHINE_OFFLINE_AFTER_MINUTES", "5"))

class MachineCreate(BaseModel):
    id: Optional[str] = None
    name: str
    type: str
    location: str
    model: str
    serialNumber: str
    installDate: str
    status: str = "normal"
    healthScore: int = 100
    healthCeiling: int = 100
    failureCount: int = 0
    lastTelemetryAt: Optional[str] = None

class MachineUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    model: Optional[str] = None
    serialNumber: Optional[str] = None
    installDate: Optional[str] = None
    status: Optional[str] = None
    healthScore: Optional[int] = None
    healthCeiling: Optional[int] = None
    failureCount: Optional[int] = None
    lastTelemetryAt: Optional[str] = None

class Machine(MachineCreate):
    id: str
    lastMaintenance: str
    storedStatus: Optional[str] = None
    statusReason: Optional[str] = None

# In-memory storage for demo purposes (normally this would be PostgreSQL)
_machines: List[dict] = []


def _normalize_machine(machine: dict) -> dict:
    machine["status"] = str(machine.get("status", "normal")).strip().lower()
    machine.setdefault("healthCeiling", 100)
    machine.setdefault("failureCount", 0)
    machine.setdefault("lastTelemetryAt", None)
    machine["healthScore"] = max(0, min(100, int(machine.get("healthScore", 100))))
    machine["healthCeiling"] = max(0, min(100, int(machine.get("healthCeiling", 100))))
    machine["failureCount"] = max(0, int(machine.get("failureCount", 0)))
    if machine["lastTelemetryAt"]:
        parsed = _parse_timestamp(machine["lastTelemetryAt"])
        machine["lastTelemetryAt"] = parsed.isoformat() if parsed else None
    return machine


def _parse_timestamp(value: object) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _status_reason(machine: dict) -> str:
    if str(machine.get("status", "")).lower() == "offline":
        return "manual_offline"
    if OFFLINE_AFTER_MINUTES <= 0:
        return "online"

    last_telemetry_at = _parse_timestamp(machine.get("lastTelemetryAt"))
    if last_telemetry_at is None:
        return "telemetry_missing"

    offline_after = timedelta(minutes=OFFLINE_AFTER_MINUTES)
    if datetime.now(timezone.utc) - last_telemetry_at > offline_after:
        return "telemetry_stale"
    return "online"


def _machine_response(machine: dict) -> dict:
    normalized = _normalize_machine(machine)
    response = dict(normalized)
    stored_status = normalized.get("status", "normal")
    reason = _status_reason(normalized)

    response["storedStatus"] = stored_status
    response["statusReason"] = reason
    if reason != "online":
        response["status"] = "offline"
    return response


def _load_machines() -> None:
    global _machines
    if not DATA_FILE.exists():
        return
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            _machines = [_normalize_machine(item) for item in data if isinstance(item, dict)]
    except Exception as exc:
        print(f"[ms6-machine] Failed to load machine registry: {exc}")


def _save_machines() -> None:
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(_machines, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[ms6-machine] Failed to save machine registry: {exc}")


@app.on_event("startup")
def startup():
    _load_machines()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ms6-machine",
        "offline_after_minutes": OFFLINE_AFTER_MINUTES,
    }

@app.get("/machines", response_model=List[Machine])
def get_machines():
    return [_machine_response(machine) for machine in _machines]

@app.get("/machines/{machine_id}", response_model=Machine)
def get_machine(machine_id: str):
    for machine in _machines:
        if machine["id"] == machine_id:
            return _machine_response(machine)
    raise HTTPException(status_code=404, detail="Machine not found")

@app.post("/machines", response_model=Machine)
def create_machine(req: MachineCreate):
    machine_id = req.id or "m" + str(uuid4())[:8]
    if any(machine["id"] == machine_id for machine in _machines):
        raise HTTPException(status_code=400, detail="Machine ID already exists")

    new_machine = req.model_dump(exclude={"id"})
    new_machine["id"] = machine_id
    new_machine["lastMaintenance"] = datetime.now(timezone.utc).date().isoformat()
    _normalize_machine(new_machine)
    _machines.append(new_machine)
    _save_machines()
    return _machine_response(new_machine)

@app.put("/machines/{machine_id}", response_model=Machine)
def update_machine(machine_id: str, req: MachineUpdate):
    for i, m in enumerate(_machines):
        if m["id"] == machine_id:
            update_data = req.model_dump(exclude_unset=True)
            for k, v in update_data.items():
                m[k] = v
            _normalize_machine(m)
            _save_machines()
            return _machine_response(m)
    raise HTTPException(status_code=404, detail="Machine not found")

@app.delete("/machines/{machine_id}")
def delete_machine(machine_id: str):
    global _machines
    initial_length = len(_machines)
    _machines = [m for m in _machines if m["id"] != machine_id]
    if len(_machines) == initial_length:
        raise HTTPException(status_code=404, detail="Machine not found")
    _save_machines()
    return {"status": "deleted"}
