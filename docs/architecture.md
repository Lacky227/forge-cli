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

**Current:** `forge.cli` — Typer, questionary, Rich.

Builds a **`ProjectDefinition`**, then calls `generate_project`. Adaptive option lists come from `forge.core.catalog`. The CLI asks only questions that change the result; framework-implied details are never presented as false choices. Generation semantics live in the resolver.

### Project Definition / Configuration

**Current:** `forge.core.definition.ProjectDefinition`.

**Explicit user intent only:** language, project type, framework, architecture, and selectable capabilities (`database` / `database_engine`, optional Alembic for FastAPI, `docker`, `testing`, `linting`).

Framework-implied implementation details are **not** required on the definition:

| User chooses | Resolver implies |
|--------------|------------------|
| FastAPI + database | SQLAlchemy |
| FastAPI + migrations | Alembic |
| Django + REST API + database | Django ORM, Django migrations, DRF |

An optional `capabilities.orm` exists for programmatic/config paths that state an ORM explicitly; the interactive CLI leaves it unset. If set, it must be compatible with the framework.

### Resolution

**Current:** `forge.generator.resolve.resolve_plan(definition) → GenerationPlan`.

- reject unsupported / incoherent **explicit** combinations before filesystem writes
- normalize package naming and template path
- resolve framework implications (ORM, migration system, `rest_framework`)
- resolve runtime/dev dependencies per framework (deduplicated)
- compute run / migrate / check commands

Framework resolution is dispatched inside the resolver (FastAPI vs Django functions)—not a plugin system.

### GenerationPlan

Includes definition reference, package/template paths, `GenerationFeatures` (including resolved `orm`, `migration_system`, `rest_framework`), dependency lists, entry/run/migrate/check commands, labels, and `primary_app` (Django).

```text
ProjectDefinition = what the user asked for
GenerationPlan    = what Forge resolved that request into
```

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

- **REST API ⇒ Django REST Framework** — DRF is required to satisfy the REST API project type; resolved as `features.rest_framework` (not a user toggle).
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
