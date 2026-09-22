# Architecture

This document describes Forge’s architecture. Sections mark what is **current** versus still planned.

Python is the **first** ecosystem, not a core assumption of the product.

## Conceptual layers

```text
CLI / User Interaction
        ↓
Project Definition / Configuration
        ↓
Generation Engine
        ↓
Templates (Jinja2)
        ↓
Generated Project
```

Architecture resolution remains a thin catalog of supported combinations today, not a separate plugin runtime.

### CLI / User Interaction

**Current:** `forge.cli` — Typer commands, questionary prompts, Rich presentation.

Owns prompts, flags, and display. Collects user intent into a **normalized `ProjectDefinition`**, then calls the generation engine. Must not embed template or filesystem generation logic. Future non-interactive paths (`forge new --config …`) will feed the same definition model.

### Project Definition / Configuration

**Current:** `forge.core.definition.ProjectDefinition` (Pydantic).

Validated description of what to build. Generation consumes this definition—not prompt transcripts or UI state. Importable without CLI/UI libraries.

### Generation Engine

**Current:** `forge.generator` — `generate_project(definition) → GenerationResult`.

Responsibilities:

- reject unsupported language/framework/architecture combinations
- normalize package names and resolve a safe destination path
- refuse non-empty destinations (no silent overwrite)
- select the template tree from the definition
- render Jinja2 templates and write files
- return a concise result (path, next steps)

The CLI must not contain `if framework == "fastapi": copy…` branches.

### Templates / Generators

**Current:** Jinja2 templates under repository `templates/`, selected as:

```text
templates/<language>/<framework>/<architecture>/
```

First implemented path:

```text
templates/python/fastapi/simple/
templates/python/fastapi/modular-monolith/
```

Template paths use `__package__/` as a placeholder directory renamed to the Python package name. Capability-specific files (Docker, Alembic, tests, database modules) are omitted when not selected.

Packaging includes templates into the wheel via hatchling `force-include` (`templates` → `forge/templates`). At runtime, `forge.generator.render.templates_root()` resolves either the packaged copy or the repo `templates/` directory.

### Generated Project

**Current for Python + FastAPI + REST API:** a runnable uv-compatible project. Quality bar: [generation.md](./generation.md).

## Package layout (current)

```text
src/forge/
├── cli/                 # Typer + questionary + Rich
├── core/                # ProjectDefinition, catalog, naming
└── generator/           # generation engine + Jinja rendering
templates/
└── python/fastapi/
    ├── simple/
    └── modular-monolith/
tests/                   # Forge's own tests (not generated-project tests)
```

## ProjectDefinition

```text
ProjectDefinition
├── name
├── language
├── project_type
├── framework
├── architecture
└── capabilities
    ├── database / database_engine / orm
    ├── migrations   # Alembic when true
    ├── docker
    ├── testing      # pytest
    └── linting      # Ruff
```

## What generates today

| Combination | Status |
|-------------|--------|
| Python · FastAPI · REST API · Simple | **Supported** |
| Python · FastAPI · REST API · Modular Monolith | **Supported** |
| Django / Flask / CLI / Worker / Clean Architecture | Catalog may offer some; **generation not implemented** (clear error) |

## Architecture styles (FastAPI)

- **Simple** — flat package: `main.py`, `config.py`, optional `database.py` / `models.py`
- **Modular Monolith** — layered package: `api/routes`, `core`, `models`, `schemas`, `repositories`, `services`

The architecture choice changes the generated layout; it is not cosmetic.

## Destination and naming

- `forge new my-api` creates `./my-api` under the current working directory
- Project names reject path separators / traversal
- Python package name: `my-api` → `my_awesome_api` style via `to_package_name()`
- Existing non-empty destinations raise `GenerationError`

## Presets / plugins

Still planned. No plugin marketplace, remote templates, or preset system in this release.

## Repository structure

```text
forge-cli/
├── docs/
├── .cursor/rules/
├── src/forge/
├── templates/
├── tests/
├── pyproject.toml
├── uv.lock
└── README.md
```
