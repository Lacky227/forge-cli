# Architecture

This document describes Forge’s architecture. Sections marked as **current** reflect the foundation spike; generation remains future work.

Python is the **first** ecosystem, not a core assumption of the product.

## Conceptual layers

```text
CLI / User Interaction
        ↓
Project Definition / Configuration
        ↓
Architecture Resolution   (future)
        ↓
Generation Engine         (future)
        ↓
Templates / Generators    (future)
        ↓
Generated Project
```

### CLI / User Interaction

**Current:** `forge.cli` — Typer commands, questionary prompts, Rich presentation.

Owns prompts, flags, and display. Collects user intent and produces a **normalized `ProjectDefinition`**. Must not embed generation logic. Future non-interactive paths (`forge new --config …`) will feed the same definition model.

### Project Definition / Configuration

**Current:** `forge.core.definition.ProjectDefinition` (Pydantic).

A validated description of what to build: name, language, project type, framework, architecture style, and capabilities. Generation (when implemented) will consume this definition—not prompt transcripts or UI state.

`ProjectDefinition` must remain importable without loading CLI/UI libraries.

### Architecture Resolution

Future: turns a definition into a concrete generation plan. Today, a small concrete **catalog** (`forge.core.catalog`) encodes supported combinations for adaptive prompting and model validation. That catalog is data + helpers—not a plugin framework.

### Generation Engine

Not implemented. The CLI ends by displaying the definition; a later task will pass that object into generation.

### Templates / Generators

Not implemented.

### Generated Project

Not produced by this spike. Quality bar when generation exists: [generation.md](./generation.md).

## Package layout (current)

```text
src/forge/
├── __init__.py
├── __main__.py          # python -m forge
├── cli/                 # Typer + questionary + Rich (UI only)
│   ├── app.py           # commands
│   ├── flow.py          # adaptive interview → ProjectDefinition
│   └── render.py        # banners / definition panel
└── core/                # no UI dependencies
    ├── types.py         # enums (language, project type, architecture)
    ├── catalog.py       # supported options + compatibility
    └── definition.py    # ProjectDefinition + Capabilities
```

## ProjectDefinition

**Responsibility:** represent the **result of choices** (interactive, config, or future presets)—never prompt indices, widgets, or terminal state.

Conceptual shape (Python model; not a required on-disk YAML schema):

```text
ProjectDefinition
├── name
├── language
├── project_type
├── framework
├── architecture
└── capabilities
    ├── database / database_engine / orm
    ├── docker
    └── testing
```

Validation examples already enforced:

- required, well-formed project name
- framework compatible with language + project type
- architecture allowed for the project type
- database fields only when the framework supports a database and `database=True`

Constructible without the CLI, e.g. `ProjectDefinition.model_validate({...})`, which is the intended path for future `--config` / presets / APIs.

## Normalized definition principle

**The CLI produces a normalized project definition; the generation engine will operate on that definition only.**

Illustrative YAML (future public config—not implemented):

```yaml
name: my-api
language: python
project_type: rest-api
framework: fastapi
architecture: modular-monolith
capabilities:
  database: true
  database_engine: postgresql
  orm: sqlalchemy
  docker: true
  testing: true
```

## Presets

Presets remain planned: compositions of valid project choices resolving to the same `ProjectDefinition`. Not implemented in this spike.

## Extensibility model

Future support should follow:

```text
Language → Framework → Project Type → Architecture → Capabilities → Templates
```

Framework integrations should eventually declare supported types, capabilities, incompatibilities, dependencies, templates, and generation rules.

**Not implemented** as a plugin system. The spike keeps boundaries clean (`cli` vs `core`) and uses a concrete catalog so the design can grow without speculative registries.

## Multi-ecosystem readiness

`Language` is an enum that today only includes Python. Framework lists are keyed by language and project type. Shared core types are not FastAPI- or Python-specific beyond the catalog data for the first ecosystem.

## Repository structure

### Current

```text
forge-cli/
├── docs/
├── .cursor/rules/
├── src/forge/
├── tests/
├── pyproject.toml
├── uv.lock
└── README.md
```

### Planned (not created until needed)

```text
templates/    # generator assets
presets/      # preset compositions
```
