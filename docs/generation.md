# Generated project quality

“Generated successfully” means a **usable starting point for a real project**.

## Quality bar

Coherent layout, correct dependencies, wired integrations, runnable entrypoint, `.env.example` when env vars exist, pytest/Ruff/Docker/migrations/CI when selected, README matching real commands and resolved environment metadata. Health endpoints are liveness-only (`{"status":"ok"}`) — no readiness/dependency probes.

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

### Project modules

Optional selectable modules (`products`, `categories`, `files`, `background-jobs`,
`email`, `webhooks`) add architecture-native capabilities. See [modules.md](./modules.md)
for the catalog, storage options, Redis/RQ implications, and composition model.
Representative cases are included in `SUPPORTED_GENERATION_CASES`.

### Persistence

SQL and NoSQL are independent. At most one engine from each category.

| Framework | No persistence | SQLite | PostgreSQL | MongoDB | Redis | SQL + NoSQL |
|-----------|----------------|--------|------------|---------|-------|-------------|
| FastAPI | Supported | Supported | Supported | Supported | Supported | Supported |
| Flask | Supported | Supported | Supported | Supported | Supported | Supported |
| Django | **Unsupported** (REST API requires SQL) | Supported | Supported | With SQL | With SQL | Supported |

```text
Persistence
├── SQL
│   ├── PostgreSQL
│   └── SQLite
└── NoSQL
    ├── MongoDB
    └── Redis
```

### Framework-implied (resolved into `GenerationPlan`, not user toggles)

| Framework | Implied when applicable |
|-----------|-------------------------|
| FastAPI + SQL | SQLAlchemy; Alembic only if migrations selected |
| Flask + SQL | SQLAlchemy; Alembic only if migrations selected |
| Django REST API + SQL | Django ORM, Django migrations, Django REST Framework |
| MongoDB | pymongo (AsyncMongoClient for FastAPI; MongoClient for Flask/Django) |
| Redis | redis package (redis.asyncio for FastAPI; sync Redis for Flask/Django) |

### Unsupported (fail in `resolve_plan` before writes)

Examples:

- Django + SQLAlchemy
- FastAPI or Flask + Django ORM
- Migrations without SQL / Alembic without SQLAlchemy
- Django REST API without SQL (NoSQL alone is not enough)
- `ci: github-actions` with both testing and linting disabled
- Non-generatable language / framework / project-type combinations
- Unknown CI providers
### Representative smoke cases

Official list: `SUPPORTED_GENERATION_CASES` in `forge.core.compatibility`.

| Case ID | Intent |
|---------|--------|
| `fastapi-simple-sqlite` | FastAPI Simple + SQLite + Alembic |
| `fastapi-modular-postgres` | FastAPI Modular + PostgreSQL + Alembic |
| `fastapi-clean-sqlite-migrations` | FastAPI Clean + SQLite + Alembic |
| `fastapi-clean-postgres-docker` | FastAPI Clean + PostgreSQL + Docker |
| `fastapi-modular-mongodb` | FastAPI Modular + MongoDB + Docker |
| `fastapi-simple-postgres-redis` | FastAPI Simple + PostgreSQL + Redis + Docker |
| `fastapi-clean-mongodb` | FastAPI Clean + MongoDB |
| `django-simple-sqlite` | Django Simple + SQLite |
| `django-modular-postgres` | Django Modular + PostgreSQL |
| `django-clean-sqlite` | Django Clean + SQLite |
| `django-clean-postgres-docker` | Django Clean + PostgreSQL + Docker |
| `django-modular-postgres-redis` | Django Modular + PostgreSQL + Redis + Docker |
| `flask-simple-nodb` | Flask Simple, no persistence |
| `flask-modular-postgres` | Flask Modular + PostgreSQL + Alembic |
| `flask-clean-sqlite` | Flask Clean + SQLite + Alembic |
| `flask-clean-postgres-docker` | Flask Clean + PostgreSQL + Docker |
| `flask-simple-sqlite-mongodb` | Flask Simple + SQLite + MongoDB |

Default tests generate every case structurally. Executable install/test smoke
(`pytest -m generation_smoke`) runs SQLite / no-persistence cases only so CI does
not require live PostgreSQL, MongoDB, or Redis servers. Docker / external-DB cases
are still generated and checked for files/compose consistency.

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
| SQL | ORM → SQLAlchemy; URL + optional `psycopg` |
| Migrations (user choice) | migration system → Alembic |
| MongoDB | client → pymongo; `MONGODB_URL` / `MONGODB_DATABASE` |
| Redis | client → redis (asyncio); `REDIS_URL` |
| pytest / Ruff / Docker | as selected |
| CI | optional `github-actions` (requires testing or linting) → `.github/workflows/ci.yml` |

### Flask

| Selection | Resolved into GenerationPlan |
|-----------|------------------------------|
| Baseline | Flask, `python-dotenv` (no ORM unless asked) |
| SQL | ORM → SQLAlchemy; URL + optional `psycopg` |
| Migrations (user choice) | migration system → Alembic |
| MongoDB | client → pymongo (sync); env settings |
| Redis | client → redis (sync); `REDIS_URL` |
| pytest / Ruff / Docker | as selected |
| CI | optional `github-actions` (requires testing or linting) → `.github/workflows/ci.yml` |

Flask does not imply persistence infrastructure. No SQL → no SQLAlchemy, no driver, no Alembic, no SQL persistence ports/packages. NoSQL clients are independent of SQL.

### Django

| Selection | Resolved into GenerationPlan |
|-----------|------------------------------|
| Baseline | Django, `python-dotenv`, `manage.py`, `config` settings |
| REST API | REST → Django REST Framework, `GET /api/health/` |
| SQL engine | ORM → Django ORM; `DATABASES` (env-aware) |
| (implied) | migration system → Django (`makemigrations` / `migrate`) |
| MongoDB / Redis | separate client modules; not Django ORM backends |
| pytest | `pytest-django` |
| Ruff / Docker | configured when selected |
| CI | optional `github-actions` (requires testing or linting) → `.github/workflows/ci.yml` |

### Clean Architecture quality notes

- Domain code must not import FastAPI, Flask, Django, SQLAlchemy, pymongo, or redis.
- Health goes through application/domain layers.
- SQL persistence ports and infrastructure packages appear only when SQL is selected (except Django, which always has SQL for REST API).
- MongoDB / Redis helpers live in infrastructure (or framework core packages) — not in domain.

### Dependency policy

Minimum lower bounds; lists come from the resolver into `pyproject.toml` and are deduplicated. FastAPI and Flask share the SQLAlchemy / Alembic / `psycopg` strategy when SQL is selected. NoSQL dependencies (`pymongo`, `redis`) appear only when that engine is selected.

### Resolved developer-workflow metadata

`resolve_plan` also fills plan fields used by `forge plan`, templates, and `forge new --dry-run`:

- `environment_variables` — names/examples/purposes matching current generated settings and `.env.example` (framework-specific SQL models preserved)
- `docker_services` — dependency Compose services only (`db` / `mongodb` / `redis` / `minio`)
- `health_path` — liveness route (FastAPI `/health` for all architectures; Flask `/api/health`; Django `/api/health/`)
- `emits_env_example` — true when `environment_variables` is non-empty (Docker alone does not emit an empty `.env.example`)
- `ci_provider` — when `github-actions`, generation emits `.github/workflows/ci.yml` from `templates/python/_shared/` (Python **3.12**, `uv sync`, then selected Ruff/pytest; no DB service containers)
- `generated_secrets` — sensitive values materialized only during real rendering; Authentication contributes `AUTH_JWT_SECRET`

Post-generation **next steps** (CLI summary and dry-run informational commands) follow the local-dev path: start dependency containers with `docker compose up -d <docker_services>` when that list is non-empty, then migrate/run on the host. Bare `docker compose up -d` is never emitted. Full-stack `docker compose up --build` is documented in the generated README Docker section (and is the only Compose command when Docker is selected without persistence).

`forge new --dry-run` reuses the same template discovery as real generation to list concrete destination-relative paths without writing files. Destination conflict validation matches generation. See [cli.md](./cli.md).

Generated projects expose a **liveness** health endpoint only (`{"status":"ok"}`). There is no readiness/dependency probe.

### Validation expectation

**FastAPI / Flask:** `uv sync` → `pytest` → `ruff` (Alembic/Docker as applicable).

**Django:** `uv sync` → `python manage.py check` → `migrate` → `pytest` → `ruff` (Compose config when Docker selected).

Live PostgreSQL containers are optional and environment-dependent.

Authentication adds structural generation across all nine families, SQLite
migration and lifecycle execution for representative FastAPI/Flask/Django
Simple/Modular/Clean projects, PostgreSQL/Compose structure checks, pairwise
existing-module composition, and installed-wheel generation. Real generation
writes a random `AUTH_JWT_SECRET` only to gitignored `.env`; `.env.example` is
blank for that value, and plan/dry-run never create or display it.

## Forge tests vs generated tests

Forge tests live in this repo’s `tests/`. Generated app tests live inside each generated project.
