# Generated project quality

“Generated successfully” means a **usable starting point for a real project**.

## Quality bar

Coherent layout, correct dependencies, wired integrations, runnable entrypoint, `.env.example` when needed, pytest/Ruff/Docker/migrations when selected, README matching real commands.

## Resolution before generation

Invalid combinations fail in `resolve_plan` before directories are created.

Examples:

- unsupported framework
- Django + SQLAlchemy
- FastAPI + Django ORM
- Alembic without SQLAlchemy / Django migrations without Django ORM

## Capability implications

### FastAPI

| Selection | Implications |
|-----------|--------------|
| Baseline | `fastapi[standard]`, `pydantic-settings` |
| PostgreSQL / SQLite | SQLAlchemy URL + optional `psycopg` |
| Migrations | Alembic |
| pytest / Ruff / Docker | as before |

### Django

| Selection | Implications |
|-----------|--------------|
| Baseline | Django, `python-dotenv`, `manage.py`, `config` settings |
| REST API | **Django REST Framework**, `GET /api/health/` |
| PostgreSQL / SQLite | Django `DATABASES` (env-aware) |
| Migrations | Django (`makemigrations` / `migrate`) — not Alembic |
| pytest | `pytest-django` |
| Ruff / Docker | configured when selected |

### Dependency policy

Minimum lower bounds; lists come from the resolver into `pyproject.toml`.

### Validation expectation

**FastAPI:** `uv sync` → `pytest` → `ruff` (Alembic/Docker as applicable).

**Django:** `uv sync` → `python manage.py check` → `migrate` → `pytest` → `ruff` (Compose config when Docker selected).

Live PostgreSQL containers are optional and environment-dependent.

## Forge tests vs generated tests

Forge tests live in this repo’s `tests/`. Generated app tests live inside each generated project.
