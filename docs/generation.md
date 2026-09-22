# Generated project quality

“Generated successfully” means more than files appearing on disk. The output should be a **usable starting point for a real project**.

## Quality bar

A generated project should:

- have a coherent directory structure for the chosen stack and architecture
- declare dependencies correctly for selected capabilities only
- wire configuration so selected components connect
- **start successfully** (or document minimal steps if a local service is required)
- expose the expected entry point
- include `.env.example` when database/Docker config is needed (never commit secrets as `.env`)
- include pytest and/or Ruff when selected
- include Docker / Alembic when selected—and they must be wired, not empty stubs
- include a README that matches the actual generated commands and layout

## Current FastAPI generator

For Python FastAPI REST APIs, Forge generates projects that support (when selected):

| Capability | Integration |
|------------|-------------|
| PostgreSQL / SQLite | `DATABASE_URL` via pydantic-settings |
| SQLAlchemy | engine + session helpers |
| Alembic | `alembic.ini` + `migrations/env.py` using app metadata/settings |
| pytest | `tests/test_health.py` (no DB required for smoke test) |
| Ruff | `[tool.ruff]` in `pyproject.toml` |
| Docker | `Dockerfile` + `docker-compose.yml` (Postgres service when PostgreSQL selected) |

### Dependency policy

Generated `pyproject.toml` uses **minimum lower bounds** (e.g. `fastapi[standard]>=0.115`, `sqlalchemy>=2.0`) without upper pins unless a known incompatibility requires one. Projects are intended to work with `uv sync`.

### Validation expectation

After generation, a typical check path is:

```text
uv sync → uv run pytest → uv run ruff check .
```

With database + Alembic (example SQLite): `uv run alembic upgrade head`.

Docker Compose files should be valid (`docker compose config`). Live container checks depend on the local Docker daemon and free ports.

## Reflect user choices

Do not emit Docker, Alembic, SQLAlchemy, or Ruff when the user did not select them.

## Working integrations

Selected features must be integrated, not merely mentioned.

**Bad:** empty `db/` folders and a README saying “add SQLAlchemy later.”

**Good:** FastAPI + PostgreSQL + SQLAlchemy + Alembic yields settings, session wiring, migration env, and `.env.example` that fit together.

## Proportional structure

Simple vs modular layouts must differ meaningfully. Avoid microservices, brokers, or deep interface trees unless selections justify them.

## Maintainability

Generated code should be readable by humans who never used Forge. Prefer clear names, conventional layouts, and minimal magic.

## Forge tests vs generated tests

| Suite | Location | Purpose |
|-------|----------|---------|
| Forge tests | `tests/` in this repository | Generator contracts, naming, CLI/domain |
| Generated tests | `tests/` inside each generated project | Smoke tests for that application |

Do not conflate the two.
