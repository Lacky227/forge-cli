# Architecture

This document describes Forge’s architecture. Sections mark what is **current** versus still planned.

Python is the **first** ecosystem, not a core assumption of the product.

## Conceptual layers

```text
CLI / User Interaction
        ↓
Project Definition / Configuration   ← explicit user intent
        ↓
Resolution → GenerationPlan          ← resolved implementation
        ↓
Generator (filesystem + Jinja2)
        ↓
Generated Project
```

### CLI / User Interaction

**Current:** `forge.cli` — Typer, questionary, Rich, optional YAML via `--config`, optional `--preset`.

Builds a **`ProjectDefinition`** from interactive prompts, configuration, or a named preset, then calls `generate_project`. Adaptive option lists come from `forge.core.catalog`. Presets live in `forge.core.presets` and only compose explicit choices. Generation semantics live in the resolver.

```text
Interactive prompts ─┐
YAML (--config)      ├→ ProjectDefinition → resolve_plan() → GenerationPlan
Preset (--preset)    ─┘
```

All input paths share the same domain model and generation pipeline. A preset is **not** a generator: it expands to a `ProjectDefinition` and does not bypass validation, resolution, or templates.

### Project Definition / Configuration

**Current:** `forge.core.definition.ProjectDefinition`.

**Explicit user intent only:** language, project type, framework, architecture, and selectable capabilities (`database` / `database_engine`, optional Alembic for SQLAlchemy stacks, `docker`, `testing`, `linting`).

Framework-implied implementation details are **not** required on the definition:

| User chooses | Resolver implies |
|--------------|------------------|
| FastAPI + database | SQLAlchemy |
| FastAPI + migrations | Alembic |
| Flask + database | SQLAlchemy |
| Flask + migrations | Alembic |
| Django + REST API + database | Django ORM, Django migrations, DRF |

Flask does **not** imply a database, ORM, or migrations merely because Flask is selected.

An optional `capabilities.orm` exists for programmatic/config paths that state an ORM explicitly; the interactive CLI leaves it unset. If set, it must be compatible with the framework.

### Resolution

**Current:** `forge.generator.resolve.resolve_plan(definition) → GenerationPlan`.

- reject unsupported / incoherent **explicit** combinations before filesystem writes
- normalize package naming and template path (`templates/<lang>/<framework>/<architecture>/`)
- resolve framework implications (ORM, migration system, `rest_framework`)
- resolve runtime/dev dependencies per framework (deduplicated)
- compute run / migrate / check commands

Architecture is independent of framework selection: the same `GenerationPlan` path serves Simple, Modular Monolith, and Clean templates. Framework resolution stays inside the resolver—not a plugin system.

### GenerationPlan

Includes definition reference, package/template paths, `GenerationFeatures` (including resolved `orm`, `migration_system`, `rest_framework`), dependency lists, entry/run/migrate/check commands, labels, and `primary_app` (Django).

```text
ProjectDefinition = what the user asked for
GenerationPlan    = what Forge resolved that request into
```

### Generator / Templates

```text
templates/python/{fastapi,django,flask}/{simple,modular-monolith,clean}/
```

Templates present plan data. Architecture chooses layout; framework chooses presentation/persistence adapters.

In the built wheel, the same tree is installed as ``forge/templates/`` (Hatch force-include). Runtime resolution is handled by ``forge.generator.render.templates_root()``.

## What generates today

| Framework \\ Architecture | Simple | Modular Monolith | Clean |
|---------------------------|--------|------------------|-------|
| FastAPI | **Supported** | **Supported** | **Supported** |
| Django | **Supported** | **Supported** | **Supported** |
| Flask | **Supported** | **Supported** | **Supported** |

CLI / Worker project types are catalogued but not generated yet.

### Framework semantics

```text
Django REST API
    → framework-implied ORM / migrations / DRF

FastAPI
    → explicit persistence choices (DB optional; SQLAlchemy + optional Alembic)

Flask
    → intentionally minimal; persistence only when selected
      (SQLAlchemy + optional Alembic — same strategy as FastAPI)
```

### Architecture styles

#### Simple

Flat, minimal package layout for the chosen framework.

#### Modular Monolith

Framework-conventional modular packaging (FastAPI/Flask layered packages; Django domain apps under `apps/`).

#### Clean Architecture

Layered packages with dependency rule **presentation → application → domain**; infrastructure implements ports at the edges.

```text
domain/           pure concepts (no framework / ORM imports)
application/      use cases (+ persistence ports when a DB is selected)
infrastructure/   config, ORM/session, persistence adapters
presentation/     HTTP API (FastAPI / Flask / DRF)
```

- Health flows through `presentation` → `application` → `domain` (not a one-line route stub).
- Persistence directories and ports are omitted when no database is selected (FastAPI/Flask).
- Django Clean keeps ORM models in `infrastructure.persistence` (Django app) and DRF views in `presentation.api`.

### Django decisions

- **REST API ⇒ Django REST Framework** — resolved as `features.rest_framework` (not a user toggle).
- **Simple** — `src/config` + one app `src/core`
- **Modular Monolith** — `src/config` + domain apps under `src/apps/` (starts with `apps.core`)
- **Clean** — `src/{domain,application,infrastructure,presentation,config}`; `primary_app` = `infrastructure.persistence`
- Database always selected for Django REST API (SQLite or PostgreSQL)
- No SQLAlchemy / Alembic for Django

### Flask decisions

- Database is optional (None / SQLite / PostgreSQL)
- SQLAlchemy only when a database is selected
- Alembic only when migrations are explicitly enabled
- **Simple** — flat package with `create_app` + `routes.py`
- **Modular Monolith** — `api/`, `core/`, and layered packages when persistence is selected
- **Clean** — same Clean layering as FastAPI, with Flask presentation

## Package layout

```text
src/forge/{cli,core,generator}/
templates/python/{fastapi,django,flask}/
tests/
```

## Destination and naming

Project name → `./<name>` under the process working directory.

- Names are path-safe directory identifiers (no separators / traversal).
- Package import name via `to_package_name()`.
- Empty destinations may be reused; non-empty destinations are refused (no silent overwrite, no `--force`).
- See [cli.md](./cli.md) for the public destination contract.
