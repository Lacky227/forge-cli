# Generated project quality

“Generated successfully” means a **usable starting point for a real project**.

## Quality bar

Coherent layout, correct dependencies, wired integrations, runnable entrypoint, `.env.example` when needed, pytest/Ruff/Docker/migrations when selected, README matching real commands.

## Official generation compatibility matrix

Canonical product contract for what Forge **officially supports** generating today.

`resolve_plan()` remains the authority for validity. The matrix in
`forge.core.compatibility` documents representative supported cases used for
smoke coverage — it is **not** a second compatibility engine.

### Supported frameworks × architectures

| Framework \\ Architecture | Simple | Modular Monolith | Clean |
|---------------------------|--------|------------------|-------|
| FastAPI | Supported | Supported | Supported |
| Django | Supported | Supported | Supported |
| Flask | Supported | Supported | Supported |

Python **REST API** only. CLI / Worker project types are catalogued but not generated yet.

### Persistence

| Framework | No database | SQLite | PostgreSQL |
|-----------|-------------|--------|------------|
| FastAPI | Supported | Supported | Supported |
| Flask | Supported | Supported | Supported |
| Django | **Unsupported** (REST API requires a database) | Supported | Supported |

### Framework-implied (resolved into `GenerationPlan`, not user toggles)

| Framework | Implied when applicable |
|-----------|-------------------------|
| FastAPI + database | SQLAlchemy; Alembic only if migrations selected |
| Flask + database | SQLAlchemy; Alembic only if migrations selected |
| Django REST API | Django ORM, Django migrations, Django REST Framework |

### Unsupported (fail in `resolve_plan` before writes)

Examples:

- Django + SQLAlchemy
- FastAPI or Flask + Django ORM
- Migrations without a database / Alembic without SQLAlchemy
- Non-generatable language / framework / project-type combinations

### Representative smoke cases

Official list: `SUPPORTED_GENERATION_CASES` in `forge.core.compatibility`.

| Case ID | Intent |
|---------|--------|
| `fastapi-simple-sqlite` | FastAPI Simple + SQLite + Alembic |
| `fastapi-modular-postgres` | FastAPI Modular + PostgreSQL + Alembic |
| `fastapi-clean-sqlite-migrations` | FastAPI Clean + SQLite + Alembic |
| `fastapi-clean-postgres-docker` | FastAPI Clean + PostgreSQL + Docker |
| `django-simple-sqlite` | Django Simple + SQLite |
| `django-modular-postgres` | Django Modular + PostgreSQL |
| `django-clean-sqlite` | Django Clean + SQLite |
| `django-clean-postgres-docker` | Django Clean + PostgreSQL + Docker |
| `flask-simple-nodb` | Flask Simple, no database |
| `flask-modular-postgres` | Flask Modular + PostgreSQL + Alembic |
| `flask-clean-sqlite` | Flask Clean + SQLite + Alembic |
| `flask-clean-postgres-docker` | Flask Clean + PostgreSQL + Docker |

Default tests generate every case structurally. Executable install/test smoke
(`pytest -m generation_smoke`) runs SQLite / no-database cases only so CI does
not require a live PostgreSQL server. PostgreSQL + Docker cases are still
generated and checked for files/compose consistency.

```bash
uv run pytest -q                          # excludes packaging + generation_smoke
uv run pytest -q -m generation_smoke      # uv sync + check/pytest/ruff
```

## Resolution before generation

Invalid combinations fail in `resolve_plan` before directories are created. The same checks apply to interactive choices, YAML `--config` input, and `--preset` expansions after mapping to `ProjectDefinition`.

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
