# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows the versioning policy in [docs/development.md](docs/development.md).

## [Unreleased]

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
