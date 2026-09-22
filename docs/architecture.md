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

Owns prompts and display. Builds a **`ProjectDefinition`**, then calls `generate_project`. Must not embed framework dependency maps, template selection, or filesystem generation. Adaptive option lists come from `forge.core.catalog` (what can be asked), not from generation code.

### Project Definition / Configuration

**Current:** `forge.core.definition.ProjectDefinition` (Pydantic).

User choices only: language, project type, framework, architecture, capabilities. No terminal/UI concepts. Importable without CLI libraries.

### Resolution

**Current:** `forge.generator.resolve.resolve_plan(definition) → GenerationPlan`.

Turns choices into generation instructions **before any filesystem writes**:

- reject unsupported or incoherent combinations (clear `GenerationError`)
- normalize package naming
- select template subdirectory
- resolve capability → features (database engine flags, migrations, docker, …)
- resolve runtime/dev dependency lists (framework-specific mapping)
- compute template presentation values (example `DATABASE_URL`, run command, labels)

### GenerationPlan

**Current:** `forge.generator.plan.GenerationPlan`.

The generator consumes this object. It should not re-decide “is PostgreSQL enabled?” or “which packages does FastAPI need?” from raw CLI answers.

Includes:

- reference to the original `ProjectDefinition`
- `package_name`, `template_subdir`
- `GenerationFeatures` (explicit generation implications)
- `runtime_dependencies` / `dev_dependencies`
- `database_url_example`, `entry_file`, `app_module`, `run_command`
- display labels

### Generator

**Current:** `forge.generator.engine` + `render`.

- `generate_project(definition)` → `resolve_plan` then `generate_from_plan`
- destination safety (no silent overwrite of non-empty paths)
- Jinja2 render from `plan.as_jinja_dict()`
- capability-gated file emission via resolved `features`

### Templates

**Current:** `templates/<language>/<framework>/<architecture>/`

Templates primarily **present** plan data. Dependency lists come from the plan (`runtime_dependencies` / `dev_dependencies`), not from framework `if` trees inside Jinja. Simple presentation conditionals (README sections, optional config blocks) are fine.

```text
templates/python/fastapi/simple/
templates/python/fastapi/modular-monolith/
```

`__package__/` is rewritten to the resolved package name.

### Generated Project

Python FastAPI REST API (Simple / Modular Monolith). Quality bar: [generation.md](./generation.md).

## Package layout (current)

```text
src/forge/
├── cli/
├── core/                 # ProjectDefinition, catalog, naming
└── generator/
    ├── plan.py           # GenerationPlan / GenerationFeatures
    ├── resolve.py        # resolve_plan()
    ├── engine.py         # generate_project / generate_from_plan
    ├── render.py         # Jinja + filesystem
    └── errors.py
templates/python/fastapi/
tests/
```

## What generates today

| Combination | Status |
|-------------|--------|
| Python · FastAPI · REST API · Simple | **Supported** |
| Python · FastAPI · REST API · Modular Monolith | **Supported** |
| Other frameworks / Clean Architecture | Not generated (fails in `resolve_plan`) |

Adding a second framework should mean: catalog entries + resolver mapping + templates — **not** new CLI conditionals or plugin infrastructure.

## Destination and naming

- `forge new my-api` → `./my-api`
- Path traversal rejected; package name via `to_package_name()`
- Non-empty destinations raise `GenerationError`

## Presets / plugins

Still planned. No plugin manager or remote template system.
