from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from uuid import uuid4

app = FastAPI(title="MS6 Machine System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MachineCreate(BaseModel):
    name: str
    type: str
    location: str
    model: str
    serialNumber: str
    installDate: str
    status: str = "normal"
    healthScore: int = 100

class MachineUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    model: Optional[str] = None
    serialNumber: Optional[str] = None
    installDate: Optional[str] = None
    status: Optional[str] = None
    healthScore: Optional[int] = None

class Machine(MachineCreate):
    id: str
    lastMaintenance: str

# In-memory storage for demo purposes (normally this would be PostgreSQL)
_machines: List[dict] = []

@app.get("/health")
def health():
    return {"status": "ok", "service": "ms6-machine"}

@app.get("/machines", response_model=List[Machine])
def get_machines():
    return _machines

@app.post("/machines", response_model=Machine)
def create_machine(req: MachineCreate):
    new_machine = req.model_dump()
    new_machine["id"] = "m" + str(uuid4())[:8]
    new_machine["lastMaintenance"] = datetime.now(timezone.utc).date().isoformat()
    _machines.append(new_machine)
    return new_machine

@app.put("/machines/{machine_id}", response_model=Machine)
def update_machine(machine_id: str, req: MachineUpdate):
    for i, m in enumerate(_machines):
        if m["id"] == machine_id:
            update_data = req.model_dump(exclude_unset=True)
            for k, v in update_data.items():
                m[k] = v
            return m
    raise HTTPException(status_code=404, detail="Machine not found")

@app.delete("/machines/{machine_id}")
def delete_machine(machine_id: str):
    global _machines
    initial_length = len(_machines)
    _machines = [m for m in _machines if m["id"] != machine_id]
    if len(_machines) == initial_length:
        raise HTTPException(status_code=404, detail="Machine not found")
    return {"status": "deleted"}
