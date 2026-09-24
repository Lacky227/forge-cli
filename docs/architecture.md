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
Preset (--preset)    ─┘                                      ├→ generator (forge new)
                                                             ├→ preview (forge new --dry-run)
                                                             └→ Rich summary (forge plan)
```

All input paths share the same domain model and resolution pipeline. `forge plan` stops after `resolve_plan` and never writes a project. `forge new --dry-run` resolves the same plan, applies destination conflict rules, and lists concrete output paths via shared template discovery — without creating or modifying files. A preset is **not** a generator: it expands to a `ProjectDefinition` and does not bypass validation, resolution, or templates.

### Project Definition / Configuration

**Current:** `forge.core.definition.ProjectDefinition`.

**Explicit user intent only:** language, project type, framework, architecture,
selectable **modules** (`products`, `categories`, `files`, …), and selectable capabilities
(`sql_database` / `nosql_database`, optional Alembic for SQLAlchemy stacks,
`docker`, `testing`, `linting`, optional `ci`).

Modules are first-class and distinct from capabilities. See [modules.md](./modules.md).
SQL-requiring modules fail validation when no SQL engine is selected.

SQL and NoSQL are **independent** first-class choices. A project may have neither, either, or both (one engine from each category).

Optional CI is an explicit provider choice (`github-actions`) or none. CI is valid only when testing and/or linting is enabled — Forge does not silently enable those tools. When selected, the generator emits `.github/workflows/ci.yml` from the language-level shared template (`templates/python/_shared/…`). The workflow runs `uv sync` plus the selected Ruff and/or pytest steps; it does not add database service containers.

Framework-implied implementation details are **not** required on the definition:

| User chooses | Resolver implies |
|--------------|------------------|
| FastAPI + SQL | SQLAlchemy |
| FastAPI + SQL migrations | Alembic |
| Flask + SQL | SQLAlchemy |
| Flask + SQL migrations | Alembic |
| Django + REST API + SQL | Django ORM, Django migrations, DRF |
| MongoDB | pymongo client (async for FastAPI; sync for Flask/Django) |
| Redis | redis client (async for FastAPI; sync for Flask/Django) |

Flask does **not** imply a database, ORM, or migrations merely because Flask is selected.
NoSQL never implies SQLAlchemy, Alembic, Django ORM, or Django migrations.

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

Includes definition reference, package/template paths, `GenerationFeatures` (including resolved `orm`, `migration_system`, `nosql_client`, `rest_framework`, optional `ci_provider`), dependency lists, entry/run/migrate/check commands, labels, `primary_app` (Django), **module contributions** (`ModuleContributions`: routers, Django apps, model imports, template mounts, API endpoint summaries), plus resolved developer-workflow metadata:

- `environment_variables` / `emits_env_example` — canonical `EnvVarSpec` list; `.env.example` is emitted only when the list is non-empty (shown by `forge plan` and consumed by templates)
- `docker_services` — Compose **dependency** service names (`db`, `mongodb`, `redis`, `minio`) when Docker is enabled; empty when Docker is off or there are no dependency services
- `processes` — runtime processes (`API`, optional `Worker` when Background Jobs are resolved)
- `health_path` — generated liveness path (FastAPI `/health`; Flask `/api/health`; Django `/api/health/`)

```text
ProjectDefinition = what the user asked for
GenerationPlan    = what Forge resolved that request into
```

Module template mounts live under `templates/python/modules/` and are discovered
alongside the framework tree and `_shared` overlay. Base templates loop structured
contributions for shared-file wiring (routers, `INSTALLED_APPS`, blueprints).
See [modules.md](./modules.md).

### Generator / Templates

```text
templates/python/{fastapi,django,flask}/{simple,modular-monolith,clean}/
templates/python/_shared/     ← emitted overlays (GitHub Actions CI, `.env.example`)
templates/python/_includes/   ← Jinja macros/includes (not copied into projects)
```

Templates present plan data. Architecture chooses layout; framework chooses presentation/persistence adapters. Language-level ``_shared`` templates are merged after the framework/architecture tree when applicable (capability-gated via ``should_emit``). README capability sections are shared via ``_includes/readme_macros.j2``.

Real generation and `forge new --dry-run` share the same planned-output discovery (`planned_outputs` / `planned_output_paths` in `forge.generator.render`): framework tree + `_shared` overlay, `_includes` never emitted, `should_emit` gates, and output path transformation. Dry-run lists those paths; generation renders them.

In the built wheel, the same tree is installed as ``forge/templates/`` (Hatch force-include). Runtime resolution is handled by ``forge.generator.render.templates_root()``.

## What generates today

See the **official generation compatibility matrix** in [generation.md](./generation.md)
(`forge.core.compatibility.SUPPORTED_GENERATION_CASES`).

| Framework \\ Architecture | Simple | Modular Monolith | Clean |
|---------------------------|--------|------------------|-------|
| FastAPI | **Supported** | **Supported** | **Supported** |
| Django | **Supported** | **Supported** | **Supported** |
| Flask | **Supported** | **Supported** | **Supported** |

CLI / Worker project types are catalogued but not generated yet.

### Framework semantics

```text
Django REST API
    → framework-implied ORM / migrations / DRF (SQL required)
    → optional NoSQL clients (MongoDB / Redis) as separate infrastructure

FastAPI
    → explicit persistence choices (SQL and/or NoSQL optional)
    → SQL ⇒ SQLAlchemy + optional Alembic
    → MongoDB ⇒ pymongo AsyncMongoClient
    → Redis ⇒ redis.asyncio

Flask
    → intentionally minimal; persistence only when selected
    → SQL ⇒ SQLAlchemy + optional Alembic (same strategy as FastAPI)
    → MongoDB / Redis ⇒ sync clients
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
- Persistence directories and SQL ports are omitted when no SQL database is selected (FastAPI/Flask).
- MongoDB / Redis clients live in infrastructure (Clean) or core/package modules — domain must not import them.
- Django Clean keeps ORM models in `infrastructure.persistence` (Django app) and DRF views in `presentation.api`.
- Django Clean **module** packs follow the same presentation + ORM shape; they do not add full domain/application ports (unlike FastAPI/Flask Clean modules). See [modules.md](./modules.md).

### Django decisions

- **REST API ⇒ Django REST Framework** — resolved as `features.rest_framework` (not a user toggle).
- **Simple** — `src/config` + one app `src/core`
- **Modular Monolith** — `src/config` + domain apps under `src/apps/` (starts with `apps.core`)
- **Clean** — `src/{domain,application,infrastructure,presentation,config}`; `primary_app` = `infrastructure.persistence`
- SQL always selected for Django REST API (SQLite or PostgreSQL)
- Optional NoSQL (MongoDB / Redis) as separate clients — not Django ORM backends
- No SQLAlchemy / Alembic for Django

### Flask decisions

- SQL is optional (None / SQLite / PostgreSQL)
- NoSQL is optional (None / MongoDB / Redis)
- SQLAlchemy only when SQL is selected
- Alembic only when migrations are explicitly enabled
- **Simple** — flat package with `create_app` + `routes.py`
- **Modular Monolith** — `api/`, `core/`, and layered packages when SQL is selected
- **Clean** — same Clean layering as FastAPI, with Flask presentation

### Authentication decisions

Authentication follows the existing definition → resolution → contribution →
template pipeline. `AuthenticationOptions` stores the Stage 1 registration
choice; `ModuleContributions` owns routes, model discovery, dependencies,
environment metadata, and all nine template mounts. A reusable
`GeneratedSecretSpec` on `GenerationPlan` declares sensitive outputs without
sampling entropy during plan or dry-run.

FastAPI and Flask use SQLAlchemy, pwdlib Argon2id, PyJWT, and Alembic. Their
Clean variants keep framework-free policy/ports in domain/application and
concrete persistence/crypto in infrastructure. Django deliberately keeps its
project-owned `AbstractUser`, native password API, authentication adapter, and
refresh model in its infrastructure boundary rather than duplicating them.

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
