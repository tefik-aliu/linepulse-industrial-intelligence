from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def build_session_factory(database_url: str):
    engine = build_engine(database_url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory


def default_database_url() -> str:
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return "sqlite:///data/linepulse.db"


def get_session(factory) -> Generator[Session, None, None]:
    with factory() as session:
        yield session
