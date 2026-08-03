from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ProductionEvent(Base):
    __tablename__ = "production_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    machine: Mapped[str] = mapped_column(String(32), index=True)
    shift: Mapped[str] = mapped_column(String(8), index=True)
    product: Mapped[str] = mapped_column(String(64), index=True)

    planned_seconds: Mapped[float] = mapped_column(Float, default=60.0)
    run_seconds: Mapped[float] = mapped_column(Float, default=60.0)
    ideal_cycle_seconds: Mapped[float] = mapped_column(Float, default=5.0)

    good_units: Mapped[int] = mapped_column(Integer, default=0)
    reject_units: Mapped[int] = mapped_column(Integer, default=0)
    downtime_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    stop_reason: Mapped[str] = mapped_column(String(64), default="None")
    defect_type: Mapped[str] = mapped_column(String(64), default="None")
    cutting_pressure_bar: Mapped[float] = mapped_column(Float, default=6.5)
    cycle_time_seconds: Mapped[float] = mapped_column(Float, default=5.0)
    scenario: Mapped[str] = mapped_column(String(64), default="baseline", index=True)
