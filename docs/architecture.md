# Architecture

This document describes Forge’s architecture. Sections mark what is **current** versus still planned.

Python is the **first** ecosystem, not a core assumption of the product.

## Conceptual layers

```text
CLI / User Interaction
        ↓
Project Definition / Configuration
        ↓
Resolution → GenerationPlan
        ↓
Generator (filesystem + Jinja2)
        ↓
Generated Project
```

### CLI / User Interaction

**Current:** `forge.cli` — Typer, questionary, Rich.

Builds a **`ProjectDefinition`**, then calls `generate_project`. Adaptive option lists come from `forge.core.catalog`. Framework-specific prompts (e.g. Alembic vs Django migrations) stay presentation-only; generation semantics live in the resolver.

### Project Definition / Configuration

**Current:** `forge.core.definition.ProjectDefinition`.

User choices: language, project type, framework, architecture, capabilities (`database`, `orm`, `migrations`, `docker`, `testing`, `linting`).

ORM/migration meaning is framework-specific and resolved later:

| Framework | ORM | Migrations |
|-----------|-----|------------|
| FastAPI | SQLAlchemy | Alembic |
| Django | Django ORM | Django migrations |

### Resolution

**Current:** `forge.generator.resolve.resolve_plan(definition) → GenerationPlan`.

- reject unsupported / incoherent combinations before filesystem writes
- normalize package naming and template path
- resolve features (including `rest_framework` for Django REST API)
- resolve runtime/dev dependencies per framework
- compute run / migrate / check commands

Framework resolution is dispatched inside the resolver (FastAPI vs Django functions)—not a plugin system.

### GenerationPlan

Includes definition reference, package/template paths, `GenerationFeatures`, dependency lists, entry/run/migrate/check commands, labels, and `primary_app` (Django).

### Generator / Templates

```text
templates/python/fastapi/{simple,modular-monolith}/
templates/python/django/{simple,modular-monolith}/
```

Templates present plan data. Django uses conventional `manage.py` + `src/config` + apps; FastAPI keeps its ASGI package layout.

## What generates today

| Combination | Status |
|-------------|--------|
| Python · FastAPI · REST API · Simple / Modular | **Supported** |
| Python · Django · REST API · Simple / Modular | **Supported** |
| Flask / CLI / Worker / Clean Architecture | Not generated |

### Django decisions

- **REST API ⇒ Django REST Framework** — DRF is required to satisfy the REST API project type; resolved as `features.rest_framework` (not a separate interactive toggle).
- **Simple** — `src/config` + one app `src/core`
- **Modular Monolith** — `src/config` + domain apps under `src/apps/` (starts with `apps.core`)
- Database always selected for Django REST API (SQLite or PostgreSQL)
- No SQLAlchemy / Alembic for Django

## Package layout

```text
src/forge/{cli,core,generator}/
templates/python/{fastapi,django}/
tests/
```

## Destination and naming

Unchanged: `./<name>`, path-safe names, `to_package_name()`, no silent overwrite.
