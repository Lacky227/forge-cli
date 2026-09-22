# Generated project quality

“Generated successfully” means a **usable starting point for a real project**.

## Quality bar

Coherent layout, correct dependencies, wired integrations, runnable entrypoint, `.env.example` when needed, pytest/Ruff/Docker/migrations when selected, README matching real commands.

## Resolution before generation

Invalid combinations fail in `resolve_plan` before directories are created.

Examples of invalid **explicit** combinations:

- unsupported framework / architecture
- Django + SQLAlchemy
- FastAPI or Flask + Django ORM
- Alembic without SQLAlchemy / migrations without a database

Framework-implied capabilities (Django ORM, Django migrations, DRF) are resolved internally and do not need to appear on `ProjectDefinition`.

## Capability implications

### FastAPI

| Selection | Resolved into GenerationPlan |
|-----------|------------------------------|
| Baseline | `fastapi[standard]`, `pydantic-settings` |
| Database | ORM → SQLAlchemy; URL + optional `psycopg` |
| Migrations (user choice) | migration system → Alembic |
| pytest / Ruff / Docker | as selected |

### Flask

| Selection | Resolved into GenerationPlan |
|-----------|------------------------------|
| Baseline | Flask, `python-dotenv` (no ORM unless asked) |
| Database | ORM → SQLAlchemy; URL + optional `psycopg` |
| Migrations (user choice) | migration system → Alembic |
| pytest / Ruff / Docker | as selected |

Flask does not imply persistence infrastructure. No database → no SQLAlchemy, no driver, no Alembic.

### Django

| Selection | Resolved into GenerationPlan |
|-----------|------------------------------|
| Baseline | Django, `python-dotenv`, `manage.py`, `config` settings |
| REST API | REST → Django REST Framework, `GET /api/health/` |
| Database engine | ORM → Django ORM; `DATABASES` (env-aware) |
| (implied) | migration system → Django (`makemigrations` / `migrate`) |
| pytest | `pytest-django` |
| Ruff / Docker | configured when selected |

### Dependency policy

Minimum lower bounds; lists come from the resolver into `pyproject.toml` and are deduplicated. FastAPI and Flask share the SQLAlchemy / Alembic / `psycopg` strategy when persistence is selected.

### Validation expectation

**FastAPI:** `uv sync` → `pytest` → `ruff` (Alembic/Docker as applicable).

**Flask:** `uv sync` → `pytest` → `ruff` (Alembic/Docker as applicable); health via Flask test client.

**Django:** `uv sync` → `python manage.py check` → `migrate` → `pytest` → `ruff` (Compose config when Docker selected).

Live PostgreSQL containers are optional and environment-dependent.

## Forge tests vs generated tests

Forge tests live in this repo’s `tests/`. Generated app tests live inside each generated project.
