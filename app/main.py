from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from .analytics import build_overview
from .database import Base, build_session_factory, default_database_url, get_session
from .models import ProductionEvent
from .reports import make_shift_workbook
from .schemas import ScenarioRequest, SimulatorState
from .simulator import SimulationState, baseline_seed, make_event

REQUESTS = Counter("linepulse_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("linepulse_http_request_duration_seconds", "HTTP request duration", ["path"])
EVENTS_CREATED = Counter(
    "linepulse_events_created_total",
    "Production events generated",
    ["scenario"],
)
READINESS = Gauge("linepulse_readiness", "Readiness state: 1 healthy, 0 degraded")


def create_app(database_url: str | None = None) -> FastAPI:
    database_url = database_url or os.getenv("DATABASE_URL") or default_database_url()
    engine, session_factory = build_session_factory(database_url)
    state = SimulationState()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        with session_factory() as session:
            count = session.scalar(select(ProductionEvent).limit(1))
            if count is None:
                session.add_all(baseline_seed())
                session.commit()
        READINESS.set(1)
        yield
        engine.dispose()

    app = FastAPI(
        title="LinePulse Industrial Intelligence",
        version="0.1.0",
        description=(
            "Explainable quality, reliability and observability "
            "for a simulated production line."
        ),
        lifespan=lifespan,
    )
    app.state.session_factory = session_factory
    app.state.simulation = state

    static_dir = Path(__file__).parent / "static"
    templates_dir = Path(__file__).parent / "templates"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    def session_dependency():
        yield from get_session(session_factory)

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        LATENCY.labels(path=route_path).observe(time.perf_counter() - start)
        REQUESTS.labels(
            method=request.method, path=route_path, status=response.status_code
        ).inc()
        return response

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(templates_dir / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "linepulse", "time": datetime.now(UTC).isoformat()}

    @app.get("/ready")
    def ready(session: Session = Depends(session_dependency)):
        if state.dependency_degraded:
            READINESS.set(0)
            raise HTTPException(
                status_code=503,
                detail="Simulated production database dependency is degraded.",
            )
        session.execute(text("SELECT 1"))
        READINESS.set(1)
        return {"status": "ready", "database": "connected"}

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/api/overview")
    def overview(session: Session = Depends(session_dependency)):
        events = list(session.scalars(select(ProductionEvent).order_by(ProductionEvent.id)).all())
        return build_overview(events, state.dependency_degraded)

    @app.get("/api/state", response_model=SimulatorState)
    def simulator_state():
        return SimulatorState(
            running=state.running,
            scenario=state.scenario,
            tick=state.tick,
            dependency_degraded=state.dependency_degraded,
        )

    @app.post("/api/simulator/tick")
    def tick(session: Session = Depends(session_dependency)):
        if not state.running:
            return {"created": False, "state": simulator_state()}

        state.tick += 1
        if state.scenario == "dependency_failure":
            state.dependency_degraded = 4 <= state.tick % 18 <= 10
        else:
            state.dependency_degraded = False

        event = make_event(state.tick, state.scenario)
        session.add(event)
        session.commit()
        session.refresh(event)
        EVENTS_CREATED.labels(scenario=state.scenario).inc()

        return {
            "created": True,
            "event_id": event.id,
            "scenario": state.scenario,
            "dependency_degraded": state.dependency_degraded,
        }

    @app.post("/api/simulator/toggle")
    def toggle():
        state.running = not state.running
        return simulator_state()

    @app.post("/api/scenarios")
    def activate_scenario(payload: ScenarioRequest):
        state.scenario = payload.scenario
        state.tick = 0
        state.dependency_degraded = False
        READINESS.set(1)
        return simulator_state()

    @app.post("/api/reset")
    def reset(session: Session = Depends(session_dependency)):
        session.execute(delete(ProductionEvent))
        session.add_all(baseline_seed())
        session.commit()
        state.running = True
        state.scenario = "baseline"
        state.tick = 0
        state.dependency_degraded = False
        READINESS.set(1)
        return {"status": "reset", "events": 90}

    @app.get("/api/reports/shift.xlsx")
    def shift_report(session: Session = Depends(session_dependency)):
        events = list(session.scalars(select(ProductionEvent).order_by(ProductionEvent.id)).all())
        content = make_shift_workbook(events, state.dependency_degraded)
        headers = {"Content-Disposition": 'attachment; filename="linepulse-shift-report.xlsx"'}
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    return app


app = create_app()
