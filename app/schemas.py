from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    id: int
    timestamp: datetime
    machine: str
    shift: str
    product: str
    planned_seconds: float
    run_seconds: float
    ideal_cycle_seconds: float
    good_units: int
    reject_units: int
    downtime_seconds: float
    stop_reason: str
    defect_type: str
    cutting_pressure_bar: float
    cycle_time_seconds: float
    scenario: str

    model_config = {"from_attributes": True}


class ScenarioRequest(BaseModel):
    scenario: str = Field(
        pattern="^(baseline|pressure_drift|micro_stops|defect_cluster|dependency_failure)$"
    )


class SimulatorState(BaseModel):
    running: bool
    scenario: str
    tick: int
    dependency_degraded: bool
