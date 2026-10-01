from __future__ import annotations


def test_health_and_readiness(client):
    assert client.get("/health").status_code == 200
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_baseline_data_and_overview(client):
    response = client.get("/api/overview")
    assert response.status_code == 200
    body = response.json()

    assert "kpis" in body
    assert body["kpis"]["good_units"] > 0
    assert len(body["recent_events"]) > 0
    assert body["dependency"]["status"] == "healthy"


def test_scenario_tick_creates_event(client):
    activation = client.post("/api/scenarios", json={"scenario": "pressure_drift"})
    assert activation.status_code == 200

    tick = client.post("/api/simulator/tick")
    assert tick.status_code == 200
    assert tick.json()["scenario"] == "pressure_drift"

    overview = client.get("/api/overview").json()
    assert overview["recent_events"][0]["scenario"] == "pressure_drift"


def test_dependency_failure_changes_readiness(client):
    client.post("/api/scenarios", json={"scenario": "dependency_failure"})
    for _ in range(4):
        client.post("/api/simulator/tick")

    response = client.get("/ready")
    assert response.status_code == 503
    overview = client.get("/api/overview").json()
    assert overview["dependency"]["status"] == "degraded"


def test_excel_shift_report_is_downloadable(client):
    response = client.get("/api/reports/shift.xlsx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.content[:2] == b"PK"


def test_unknown_urls_share_one_metrics_label(client):
    from app.main import REQUESTS

    counter = REQUESTS.labels(method="GET", path="unmatched", status=404)
    before = counter._value.get()
    for path in ("/unknown-alpha", "/unknown-beta", "/unknown-gamma"):
        assert client.get(path).status_code == 404
    assert counter._value.get() == before + 3
    metrics = client.get("/metrics").text
    assert 'path="unmatched"' in metrics
    assert 'path="/unknown-alpha"' not in metrics
    assert 'path="/unknown-beta"' not in metrics
