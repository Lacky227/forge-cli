# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows the versioning policy in [docs/development.md](docs/development.md).

## [Unreleased]

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
