from __future__ import annotations

from datetime import UTC, datetime

from app.analytics import calculate_kpis, detect_alerts
from app.models import ProductionEvent


def event(**overrides):
    values = {
        "timestamp": datetime.now(UTC),
        "machine": "CUT-01",
        "shift": "A",
        "product": "Laminated 6.4",
        "planned_seconds": 60.0,
        "run_seconds": 55.0,
        "ideal_cycle_seconds": 5.0,
        "good_units": 10,
        "reject_units": 0,
        "downtime_seconds": 5.0,
        "stop_reason": "None",
        "defect_type": "None",
        "cutting_pressure_bar": 6.5,
        "cycle_time_seconds": 5.0,
        "scenario": "baseline",
    }
    values.update(overrides)
    return ProductionEvent(**values)


def test_kpis_are_bounded_and_explainable():
    events = [event() for _ in range(20)]
    kpis = calculate_kpis(events)

    assert 0 <= kpis["oee"] <= 100
    assert kpis["availability"] == 91.7
    assert kpis["scrap_rate"] == 0.0
    assert kpis["good_units"] == 200


def test_pressure_drift_generates_explainable_alert():
    events = [
        event(
            cutting_pressure_bar=7.6,
            good_units=8,
            reject_units=2,
            defect_type="Edge chip",
            scenario="pressure_drift",
        )
        for _ in range(24)
    ]
    alerts = detect_alerts(events)
    codes = {alert.code for alert in alerts}

    assert "PRESSURE_DRIFT" in codes
    pressure_alert = next(alert for alert in alerts if alert.code == "PRESSURE_DRIFT")
    assert "bar" in pressure_alert.evidence
    assert "scrap" in pressure_alert.evidence.lower()


def test_micro_stop_cluster_is_detected():
    events = [
        event(
            downtime_seconds=15,
            run_seconds=45,
            stop_reason="Sensor reset",
            scenario="micro_stops",
        )
        for _ in range(10)
    ]
    alerts = detect_alerts(events)
    assert "MICRO_STOP_CLUSTER" in {alert.code for alert in alerts}
