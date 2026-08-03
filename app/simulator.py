from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import random

from .models import ProductionEvent

MACHINES = ["CUT-01", "LAM-02", "GRIND-01"]
PRODUCTS = ["Laminated 6.4", "Tempered 8 mm", "Fire-rated 12 mm"]
SHIFTS = ["A", "B", "C"]


@dataclass
class SimulationState:
    running: bool = True
    scenario: str = "baseline"
    tick: int = 0
    dependency_degraded: bool = False


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def make_event(tick: int, scenario: str, *, timestamp: datetime | None = None) -> ProductionEvent:
    rng = _rng(7_000 + tick * 31 + sum(ord(c) for c in scenario))
    machine = MACHINES[tick % len(MACHINES)]
    product = PRODUCTS[(tick // 2) % len(PRODUCTS)]
    shift = SHIFTS[(tick // 60) % len(SHIFTS)]

    planned = 60.0
    downtime = max(0.0, rng.gauss(2.0, 2.5))
    pressure = rng.gauss(6.5, 0.08)
    cycle = max(4.6, rng.gauss(5.05, 0.18))
    stop_reason = "None"
    defect_type = "None"

    if scenario == "pressure_drift":
        progress = min(1.0, tick / 28)
        pressure = 6.55 + progress * 1.65 + rng.gauss(0, 0.05)
        cycle += progress * 0.35
        if progress > 0.35:
            defect_type = "Edge chip"
        if progress > 0.72 and rng.random() < 0.35:
            downtime += rng.uniform(20, 65)
            stop_reason = "Pressure adjustment"

    elif scenario == "micro_stops":
        if rng.random() < 0.68:
            downtime = rng.uniform(7, 32)
            stop_reason = rng.choice(["Sensor reset", "Alignment check", "Material reposition"])
        pressure += rng.gauss(0, 0.04)

    elif scenario == "defect_cluster":
        product = "Fire-rated 12 mm"
        machine = "LAM-02"
        defect_type = "Delamination" if rng.random() < 0.84 else "Inclusion"
        downtime += rng.uniform(0, 9)

    elif scenario == "dependency_failure":
        downtime += rng.uniform(0, 4)

    run_seconds = max(1.0, planned - downtime)
    theoretical_units = max(1, int(run_seconds / cycle))
    performance_noise = rng.uniform(0.88, 1.0)
    total_units = max(1, int(theoretical_units * performance_noise))

    reject_rate = 0.012
    if scenario == "pressure_drift":
        reject_rate = 0.015 + max(0.0, pressure - 6.8) * 0.055
    elif scenario == "defect_cluster":
        reject_rate = 0.12
    elif scenario == "micro_stops":
        reject_rate = 0.018

    rejects = min(total_units, sum(1 for _ in range(total_units) if rng.random() < reject_rate))
    good = max(0, total_units - rejects)

    if rejects and defect_type == "None":
        defect_type = rng.choice(["Edge chip", "Scratch", "Dimension"])

    return ProductionEvent(
        timestamp=timestamp or datetime.now(UTC),
        machine=machine,
        shift=shift,
        product=product,
        planned_seconds=planned,
        run_seconds=run_seconds,
        ideal_cycle_seconds=5.0,
        good_units=good,
        reject_units=rejects,
        downtime_seconds=downtime,
        stop_reason=stop_reason,
        defect_type=defect_type,
        cutting_pressure_bar=pressure,
        cycle_time_seconds=cycle,
        scenario=scenario,
    )


def baseline_seed(count: int = 90) -> list[ProductionEvent]:
    start = datetime.now(UTC) - timedelta(minutes=count)
    return [
        make_event(i, "baseline", timestamp=start + timedelta(minutes=i))
        for i in range(count)
    ]
