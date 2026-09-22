# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows the versioning policy in [docs/development.md](docs/development.md).

## [0.1.0] - 2026-09-22

First public development release of the Forge CLI (`forge-cli`).

### Added

- Interactive `forge new` flow for Python REST API projects
- Generators for **FastAPI**, **Django**, and **Flask**
- Architecture layouts: **Simple**, **Modular Monolith**, and **Clean Architecture**
- Non-interactive YAML generation via `forge new --config`
- Curated stack presets via `forge new --preset` (e.g. `fastapi-postgres`)
- Packaged CLI distribution with Jinja templates included in the wheel
- CI for Python 3.11–3.13 plus packaging smoke validation

### Architecture

- Shared domain model: CLI / config / preset → `ProjectDefinition` → `resolve_plan()` → `GenerationPlan` → generator
- Framework implications (ORM, migrations, DRF) resolved in `resolve_plan`, not duplicated in presets or YAML
