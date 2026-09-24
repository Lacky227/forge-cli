# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows the versioning policy in [docs/development.md](docs/development.md).

## [Unreleased]

### Added

- Stage 1 `authentication` module across all FastAPI, Django REST, and Flask architectures.
- Email identities, Argon2id passwords, strict access JWTs, rotating opaque SQL refresh sessions, replay-family revocation, logout-all, and password change.
- Generic generated-secret plans; `AUTH_JWT_SECRET` is created only in gitignored local `.env` and remains blank in `.env.example`.
- `fastapi-auth` preset and Authentication-aware interactive, YAML, plan, and dry-run flows.
- Stage 2 `authorization` module with reusable authenticated, verified,
  permission, any-permission, and owner-or-permission policies across all nine
  framework/architecture families.
- SQLAlchemy RBAC roles, permissions, assignments, deterministic `member` and
  `admin` provisioning, and Django-native Group/Permission adapters.
- Optional email verification and password reset using digest-only, expiring,
  single-use opaque action tokens and the existing Email capability.
- Optional RQ delivery for account-security email when Background Jobs is
  independently selected, plus the curated `django-auth` preset.
- Stage 3 hardening: process-local sliding-window rate limits (429 +
  `Retry-After`), trusted hosts, restricted CORS, baseline security headers
  (opt-in HSTS in production), auth-route body limits, sensitive-log redaction,
  production host/DEBUG/secret checks, and idempotent auth-state cleanup
  commands — without Redis for throttling and without new wizard questions.

### Compatibility

- Authentication and Authorization require SQL; FastAPI and Flask also require
  Alembic. Authorization implies Authentication. Verification/reset imply
  Email, but not Background Jobs or Redis.
- Rate limits are process-local only; gateway throttling remains a deployment
  concern for multi-instance setups. RQ security-email jobs may carry raw
  tokens in Redis args until the worker runs (SQL stores digests only).
- Existing configurations without security modules and Stage 1
  Authentication-only configurations retain their prior behavior. Existing
  Products, Categories, and Files routes are not automatically protected.

## [0.4.0] - 2026-09-24

Selectable project modules with real generated capabilities: catalog CRUD, files/storage, background jobs, email, and outgoing webhooks.

### Added

- First-class multi-select **project modules**: Products, Categories, Files, Background Jobs, Email, and Webhooks
- Products and Categories CRUD APIs (pagination, filtering, allow-listed sorting); combined selection adds a product→category relationship
- Files module with SQL metadata plus local or S3-compatible object storage (optional MinIO when Docker is enabled)
- Background Jobs via RQ on Redis, with a generated worker process and Compose `worker` service when Docker is on
- Email via SMTP (`EmailService`; no open send-mail HTTP endpoint)
- Outgoing Webhooks delivered through Background Jobs (operator-configured `WEBHOOK_URL`; no inbound webhook framework)
- YAML `modules` / `storage` configuration; interactive multi-select with adaptive follow-ups (storage backend, Redis reuse vs infrastructure)
- Presets `fastapi-catalog` (Products + Categories) and `fastapi-files` (Files + local storage)
- `forge plan` and `forge new --dry-run` awareness of selected modules, implied dependencies, storage, workers, and related env/Docker metadata

### Changed

- Module selection is distinct from developer-workflow capabilities (Docker, testing, linting, CI) and from persistence engines
- Background Jobs reuse an existing NoSQL Redis selection (`REDIS_URL`) instead of inventing a second broker URL

### Fixed

- Redis Compose service is shared when jobs and NoSQL Redis coincide (no duplicate brokers)
- S3 endpoint defaults: empty `S3_ENDPOINT_URL` means the AWS default endpoint
- Django Background Jobs integration aligned with generated apps and worker commands

### Compatibility

- Projects from 0.3 without `modules` remain valid (omit `modules` or use `modules: []`)
- Users / Auth / security modules are reserved for a later release — not part of 0.4
- Webhooks are outgoing-only; Background Jobs use RQ only; Files storage is local or S3-compatible

## [0.3.0] - 2026-09-23

Developer-workflow metadata, optional GitHub Actions CI, generated DX consistency, and `forge new --dry-run`.

### Added

- Optional GitHub Actions CI (`ci: github-actions`) via interactive flow and YAML; requires pytest and/or Ruff
- Generated `.github/workflows/ci.yml` from a shared template (selected Ruff/pytest steps only; no database service containers)
- Richer `forge plan` output: environment variables, Docker dependency services, and health endpoint
- Canonical resolved environment metadata driving shared `.env.example` and generated README configuration
- `forge new --dry-run` — preview concrete output paths with zero filesystem writes (same discovery and destination rules as generation)

### Changed

- Generated README/setup/configuration sections share plan-driven macros for consistency
- `.env.example` emitted only when environment variables exist; Compose `env_file` follows the same gate
- Dockerfile `HEALTHCHECK` uses the resolved liveness path
- FastAPI liveness endpoint normalized to `/health` for all architectures (including Clean)
- Post-generation next steps start Compose **dependency** services only (`db` / `mongodb` / `redis`) when present

### Fixed

- Empty `.env.example` no longer generated when there are no environment variables
- FastAPI Clean health path aligned with other FastAPI layouts (`/health`)
- Drift between resolved plan metadata and generated project documentation/configuration

### Compatibility

- YAML without `ci` remains valid; existing presets leave CI disabled
- `--dry-run` is CLI execution behavior only — not a YAML or plan field
- Generated FastAPI Clean projects: health URL changes from `/api/health` (0.2.x) to `/health` (0.3.0)

## [0.2.0] - 2026-09-23

Independent SQL and NoSQL persistence for generated Python REST API projects.

### Added

- Independent persistence selection: SQL (`postgresql`, `sqlite`) and NoSQL (`mongodb`, `redis`), including SQL + NoSQL combinations
- Interactive flow: optional database → SQL / NoSQL / Both → engine prompts (Django still requires SQL; NoSQL is optional alongside it)
- YAML `persistence` configuration (`sql` / `nosql` keys)
- MongoDB integration via the official PyMongo driver (async for FastAPI; sync for Flask/Django)
- Redis integration via the official redis-py client (async for FastAPI; sync for Flask/Django)
- Docker Compose services for MongoDB and Redis when selected with Docker
- `forge plan` sections that distinguish SQL from NoSQL
- Preset `fastapi-mongo` (FastAPI + Modular Monolith + MongoDB + Docker)

### Changed

- `ProjectDefinition` / `GenerationPlan` model persistence as independent SQL and NoSQL choices (SQLAlchemy, Alembic, and Django ORM remain SQL-only implications)

### Compatibility

- Legacy YAML `database: postgresql` / `sqlite` remains supported as an SQL-only shorthand
- Conflicting `database` + `persistence` values are rejected with a clear error

## [0.1.1] - 2026-09-22

Packaging rename for first PyPI publication.

### Changed

- PyPI distribution name is now **`forge-scaffolder`** (the previous intended name `forge-cli` is already occupied on PyPI by an unrelated project)
- Console script remains **`forge`**; Python import package remains **`forge`**; GitHub repository remains **`Lacky227/forge-cli`**
- Prepares / contains the first PyPI publication under the new distribution name

The existing GitHub release **`v0.1.0`** remains the previous release and was not published to PyPI.

## [0.1.0] - 2026-09-22

First public development release of the Forge CLI (`forge-cli` as the then-intended distribution name; GitHub release `v0.1.0`).

### Added

- Interactive `forge new` flow for Python REST API projects
- Generators for **FastAPI**, **Django**, and **Flask**
- Architecture layouts: **Simple**, **Modular Monolith**, and **Clean Architecture**
- Non-interactive YAML generation via `forge new --config`
- Curated stack presets via `forge new --preset` (e.g. `fastapi-postgres`)
- `forge plan` — inspect the resolved `GenerationPlan` from `--preset` or `--config` without generating files
- Official generation compatibility matrix (`forge.core.compatibility`) with structural and executable smoke coverage
- Packaged CLI distribution with Jinja templates included in the wheel
- CI for Python 3.11–3.13 plus packaging smoke validation
- Licensed under GPL-3.0-only

### Architecture

- Shared domain model: CLI / config / preset → `ProjectDefinition` → `resolve_plan()` → `GenerationPlan` → generator
- Framework implications (ORM, migrations, DRF) resolved in `resolve_plan`, not duplicated in presets or YAML
