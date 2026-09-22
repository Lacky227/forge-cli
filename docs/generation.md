# Generated project quality

“Generated successfully” means a **usable starting point for a real project**.

## Quality bar

Coherent layout, correct dependencies, wired integrations, runnable entrypoint, `.env.example` when needed, pytest/Ruff/Docker/migrations when selected, README matching real commands.

## Resolution before generation

Invalid combinations fail in `resolve_plan` before directories are created. The same checks apply to interactive choices, YAML `--config` input, and `--preset` expansions after mapping to `ProjectDefinition`.

Examples of invalid **explicit** combinations:

- unsupported framework / architecture / project type
- Django + SQLAlchemy
- FastAPI or Flask + Django ORM
- Alembic without SQLAlchemy / migrations without a database

Framework-implied capabilities (Django ORM, Django migrations, DRF) are resolved internally and do not need to appear on `ProjectDefinition`.

## Capability implications

Implications are the same across Simple, Modular Monolith, and Clean — architecture changes layout, not the dependency policy.

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

Flask does not imply persistence infrastructure. No database → no SQLAlchemy, no driver, no Alembic, no persistence ports/packages.

### Django

| Selection | Resolved into GenerationPlan |
|-----------|------------------------------|
| Baseline | Django, `python-dotenv`, `manage.py`, `config` settings |
| REST API | REST → Django REST Framework, `GET /api/health/` |
| Database engine | ORM → Django ORM; `DATABASES` (env-aware) |
| (implied) | migration system → Django (`makemigrations` / `migrate`) |
| pytest | `pytest-django` |
| Ruff / Docker | configured when selected |

### Clean Architecture quality notes

- Domain code must not import FastAPI, Flask, Django, or SQLAlchemy.
- Health goes through application/domain layers.
- Persistence ports and infrastructure packages appear only when a database is selected (except Django, which always has a database for REST API).

### Dependency policy

Minimum lower bounds; lists come from the resolver into `pyproject.toml` and are deduplicated. FastAPI and Flask share the SQLAlchemy / Alembic / `psycopg` strategy when persistence is selected.

### Validation expectation

**FastAPI / Flask:** `uv sync` → `pytest` → `ruff` (Alembic/Docker as applicable).

**Django:** `uv sync` → `python manage.py check` → `migrate` → `pytest` → `ruff` (Compose config when Docker selected).

Live PostgreSQL containers are optional and environment-dependent.

## Forge tests vs generated tests

Forge tests live in this repo’s `tests/`. Generated app tests live inside each generated project.
