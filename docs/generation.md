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

## Resolution before generation

Invalid combinations fail in `resolve_plan` **before** directories are created.

Examples:

- unsupported framework/architecture
- Alembic without a SQLAlchemy-compatible ORM/database setup

## Capability implications (FastAPI)

Resolved centrally in `forge.generator.resolve` (not in the CLI):

| Selection | Generation implications |
|-----------|-------------------------|
| FastAPI baseline | `fastapi[standard]`, `pydantic-settings`, app entrypoint |
| PostgreSQL | `psycopg`, `DATABASE_URL`, Compose `db` service when Docker on |
| SQLite | SQLite `DATABASE_URL` (no Postgres driver) |
| SQLAlchemy | `sqlalchemy`, database session/models wiring |
| Alembic | `alembic`, `alembic.ini`, `migrations/` |
| pytest | `pytest`/`httpx`, `tests/` |
| Ruff | `ruff` + `[tool.ruff]` |
| Docker | `Dockerfile`, `docker-compose.yml` |

### Dependency policy

Minimum lower bounds, no upper pins by default. Lists are produced by the resolver and rendered into `pyproject.toml`.

### Validation expectation

```text
uv sync → uv run pytest → uv run ruff check .
```

Alembic (e.g. SQLite): `uv run alembic upgrade head`.

Docker: `docker compose config` (live containers optional; not required for Forge’s own tests).

## Reflect user choices

Do not emit Docker, Alembic, SQLAlchemy, or Ruff when not selected.

## Working integrations

Selected features must be integrated, not merely mentioned.

## Proportional structure

Simple vs modular layouts must differ meaningfully.

## Forge tests vs generated tests

| Suite | Location | Purpose |
|-------|----------|---------|
| Forge tests | `tests/` here | Resolution, generator contracts, domain |
| Generated tests | inside each generated project | Application smoke tests |
