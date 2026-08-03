from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean

from .models import ProductionEvent


@dataclass(frozen=True)
class Alert:
    code: str
    severity: str
    title: str
    evidence: str
    recommendation: str


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def calculate_kpis(events: list[ProductionEvent]) -> dict[str, float | int]:
    planned = sum(event.planned_seconds for event in events)
    run = sum(event.run_seconds for event in events)
    good = sum(event.good_units for event in events)
    rejects = sum(event.reject_units for event in events)
    total = good + rejects
    ideal_cycle = mean([event.ideal_cycle_seconds for event in events]) if events else 5.0

    availability = safe_div(run, planned)
    performance = min(1.0, safe_div(ideal_cycle * total, run))
    quality = safe_div(good, total)
    oee = availability * performance * quality

    failures = [
        event
        for event in events
        if event.stop_reason
        not in {
            "None",
            "Sensor reset",
            "Alignment check",
            "Material reposition",
        }
        and event.downtime_seconds >= 20
    ]
    mtbf_minutes = safe_div(run / 60, len(failures)) if failures else run / 60
    mttr_minutes = mean([event.downtime_seconds / 60 for event in failures]) if failures else 0.0

    return {
        "oee": round(oee * 100, 1),
        "availability": round(availability * 100, 1),
        "performance": round(performance * 100, 1),
        "quality": round(quality * 100, 1),
        "scrap_rate": round(safe_div(rejects, total) * 100, 2),
        "good_units": good,
        "reject_units": rejects,
        "downtime_minutes": round(sum(e.downtime_seconds for e in events) / 60, 1),
        "mtbf_minutes": round(mtbf_minutes, 1),
        "mttr_minutes": round(mttr_minutes, 1),
    }


def pareto(events: list[ProductionEvent], field: str, limit: int = 5) -> list[dict[str, int | str]]:
    values = [
        getattr(event, field)
        for event in events
        if getattr(event, field) not in {"None", "", None}
    ]
    return [{"name": name, "count": count} for name, count in Counter(values).most_common(limit)]


def detect_alerts(events: list[ProductionEvent]) -> list[Alert]:
    if not events:
        return []

    recent = events[-24:]
    alerts: list[Alert] = []
    kpis = calculate_kpis(recent)

    avg_pressure = mean(event.cutting_pressure_bar for event in recent)
    reject_rate = float(kpis["scrap_rate"])
    if avg_pressure > 7.15 and reject_rate > 3:
        alerts.append(
            Alert(
                code="PRESSURE_DRIFT",
                severity="critical",
                title="Cutting pressure drift is driving defects",
                evidence=(
                    f"24-event pressure average is {avg_pressure:.2f} bar "
                    f"and scrap is {reject_rate:.2f}%."
                ),
                recommendation=(
                    "Inspect pressure regulation and edge quality before the next batch."
                ),
            )
        )

    micro_stops = [
        event
        for event in recent
        if 5 <= event.downtime_seconds <= 40
        and event.stop_reason in {"Sensor reset", "Alignment check", "Material reposition"}
    ]
    if len(micro_stops) >= 7:
        alerts.append(
            Alert(
                code="MICRO_STOP_CLUSTER",
                severity="warning",
                title="Repeated micro-stops are eroding availability",
                evidence=(
                    f"{len(micro_stops)} short stops occurred "
                    "in the latest 24 production events."
                ),
                recommendation=(
                    "Group the stops by reason and inspect the dominant "
                    "sensor or alignment condition."
                ),
            )
        )

    defects = Counter(
        event.defect_type
        for event in recent
        if event.defect_type not in {"None", "", None}
        for _ in range(max(1, event.reject_units))
    )
    total_defects = sum(defects.values())
    if total_defects >= 8:
        defect_name, defect_count = defects.most_common(1)[0]
        share = safe_div(defect_count, total_defects)
        if share >= 0.6:
            alerts.append(
                Alert(
                    code="DEFECT_CONCENTRATION",
                    severity="critical" if share >= 0.78 else "warning",
                    title=f"{defect_name} dominates current rejects",
                    evidence=(
                        f"{defect_count} of {total_defects} weighted reject "
                        f"observations ({share * 100:.0f}%)."
                    ),
                    recommendation=(
                        "Contain the affected machine/product combination "
                        "and verify process parameters."
                    ),
                )
            )

    if float(kpis["oee"]) < 70:
        alerts.append(
            Alert(
                code="OEE_DROP",
                severity="warning",
                title="OEE has fallen below the operating threshold",
                evidence=f"Latest rolling OEE is {kpis['oee']}%, below the 70% warning threshold.",
                recommendation=(
                    "Review availability loss first, then the dominant "
                    "reject and stop categories."
                ),
            )
        )

    return alerts


def build_overview(events: list[ProductionEvent], dependency_degraded: bool) -> dict:
    kpis = calculate_kpis(events)
    alerts = detect_alerts(events)
    recent = list(reversed(events[-18:]))

    return {
        "kpis": kpis,
        "alerts": [alert.__dict__ for alert in alerts],
        "stop_pareto": pareto(events[-60:], "stop_reason"),
        "defect_pareto": pareto(events[-60:], "defect_type"),
        "recent_events": [
            {
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "machine": event.machine,
                "product": event.product,
                "good_units": event.good_units,
                "reject_units": event.reject_units,
                "downtime_seconds": round(event.downtime_seconds, 1),
                "stop_reason": event.stop_reason,
                "defect_type": event.defect_type,
                "pressure": round(event.cutting_pressure_bar, 2),
                "scenario": event.scenario,
            }
            for event in recent
        ],
        "dependency": {
            "name": "production database",
            "status": "degraded" if dependency_degraded else "healthy",
        },
    }
