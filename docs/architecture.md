# Architecture

```text
Browser dashboard
      |
      v
FastAPI service ---- /metrics ----> Prometheus / Grafana (deployment extension)
      |
      v
SQLAlchemy + SQLite (MVP) / PostgreSQL (production target)
      |
      +---- Explainable analytics
      +---- Scenario simulator
      +---- XLSX shift reporting
      +---- Readiness and health probes

GitHub Actions
  +-- Ruff + Pytest
  +-- TypeScript + Playwright
```

## Why SQLite in the first public MVP?

The repository must be runnable in one command and reviewable without external infrastructure.
The database boundary is isolated behind SQLAlchemy and `DATABASE_URL`, so PostgreSQL can be used
without changing the analytics or API contract.

## Explainability rule

Every alert must include:

1. the measured condition,
2. the threshold or concentration that triggered it,
3. a concrete recommended next action.

The system does not claim machine-learning certainty.
