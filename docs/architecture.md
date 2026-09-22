# Architecture

This document describes Forge’s intended high-level architecture. Implementation details that are not yet decided are left open on purpose.

Python is the **first** ecosystem, not a core assumption of the product.

## Conceptual layers

```text
CLI / User Interaction
        ↓
Project Definition / Configuration
        ↓
Architecture Resolution
        ↓
Generation Engine
        ↓
Templates / Generators
        ↓
Generated Project
```

### CLI / User Interaction

Owns prompts, flags, presets entry points, and presentation (e.g. Rich). Collects user intent and produces a **normalized project definition**. Must not embed generation logic. Supports future non-interactive paths (`forge new --config …`) by feeding the same definition shape.

### Project Definition / Configuration

A language-agnostic (conceptually), validated description of what to build: language, project type, framework, architecture style, capabilities, and options. Format (YAML, JSON, in-memory model) is an implementation choice; the principle is that generation consumes this definition, not raw prompt transcripts.

### Architecture Resolution

Turns a definition into a concrete generation plan: which templates/generators apply, which dependencies and integrations are required, and which combinations are invalid. Enforces framework-aware constraints and capability compatibility.

### Generation Engine

Applies the plan: materializes files, wires integrations, and ensures selected features are connected enough to run. Depends on the project definition and resolution output—not on interactive CLI state.

### Templates / Generators

Ecosystem- and framework-specific assets and code that emit project files. Prefer composition of shared building blocks over one-off mega-templates per preset.

### Generated Project

The output on disk: a coherent, maintainable codebase matching the user’s choices. Quality bar: [generation.md](./generation.md).

## Normalized project definition

**Principle:** the CLI produces a normalized project definition; the generation engine operates on that definition only.

Illustrative shape (not a mandated schema or required internal YAML):

```yaml
language: python
project_type: api
framework:
  name: fastapi
architecture:
  style: modular-monolith
database:
  engine: postgresql
  orm: sqlalchemy
authentication:
  enabled: true
  type: jwt
cache:
  enabled: true
  engine: redis
docker:
  enabled: true
testing:
  enabled: true
```

This separation enables:

```bash
forge new my-api --config forge.yaml
```

and future tooling/integrations that skip interactive prompts.

## Presets

Presets are **compositions of valid project choices**, not separate generators.

Examples of intended commands:

```bash
forge preset list
forge new my-api --preset fastapi-production
```

Potential presets (illustrative):

- FastAPI API
- FastAPI Production
- FastAPI Microservice
- Django REST
- Flask API
- CLI Application
- Worker

Users should be able to start from a preset and customize further. Presets must resolve to the same project definition model as interactive selection.

## Extensibility model

Future support should follow a hierarchy like:

```text
Language
    ↓
Framework
    ↓
Project Type
    ↓
Architecture
    ↓
Capabilities
    ↓
Templates / Generators
```

A framework integration should eventually be able to declare:

- supported project types
- supported capabilities
- incompatible options
- required dependencies
- templates
- generation rules

**Not implemented yet**—this is the architectural goal so the core stays language-agnostic and plugin-friendly.

## Multi-ecosystem readiness

The core must allow multiple languages, frameworks, databases, ORMs, auth systems, infrastructure integrations, architectures, and project types **without rewriting the core**. Avoid Python-specific types, paths, or assumptions in shared layers. Ecosystem specifics live in templates/generators and framework declarations.

## Repository structure

### Current

```text
forge-cli/
├── docs/
├── .cursor/
│   └── rules/
└── README.md
```

### Planned (not created until needed)

```text
forge-cli/
├── docs/
├── .cursor/
│   └── rules/
├── src/                 # Forge application package(s)
├── tests/
├── templates/           # or equivalent generator assets
├── presets/
└── …
```

Do not treat planned paths as existing. Create directories when implementation needs them. Exact package layout (`src/forge/`, naming, packaging) remains an open implementation decision—see [development.md](./development.md).
