# Product

## What Forge is

Forge is a cross-platform CLI for interactively designing and generating application project architectures. A developer runs something like `forge new`, answers clear questions about what they want to build, and receives a coherent, runnable project structured from those choices.

Forge is intended as a serious open-source developer tool—not a disposable scaffold dump.

## Problem

Developers repeatedly spend time deciding and manually creating:

- project layout and conventions
- framework boilerplate
- configuration and environment wiring
- database / ORM / migration setup
- auth, cache, Docker, and other integrations
- baseline testing and linting tooling

Those decisions are often made under time pressure, inconsistently documented, and re-solved from scratch. Forge makes the decisions explicit through a pleasant interactive CLI and turns valid combinations into working software.

## Who it is for

- Individual developers starting new services or apps
- Teams that want consistent, reviewable project baselines
- Maintainers who prefer generated structure they can still own and evolve by hand

Forge assumes the user will continue developing the project manually after generation.

## Core user experience

1. Launch an interactive flow (`forge new`, optionally with a name or preset).
2. Answer adaptive questions: project type, language/ecosystem, framework, architecture style, and only the capabilities that matter.
3. Review a normalized project definition (conceptually; formatting is an implementation detail).
4. Generate a project that starts, reflects the selections, and is ready for real work.

The CLI should feel modern and pleasant. See [cli.md](./cli.md).

## What Forge generates

Forge generates a **project**, not a pile of empty folders. Depending on selections, that may include:

- directory layout conventional for the chosen stack
- application entry points and wiring between selected components
- dependency manifests
- environment configuration samples
- database / ORM / migration setup when selected
- Docker support when selected
- development tooling (e.g. tests, linters) when selected
- short project documentation useful for continuing development

Generated projects should be understandable, runnable, conventional, maintainable, and suitable as the start of a real codebase.

## What Forge does not try to do

See **Non-goals** below. In short: Forge assists architectural choices and implements a sound baseline; it does not replace IDEs, cloud platforms, package managers, or ongoing engineering judgment.

## Long-term vision

- First-class support for multiple languages and ecosystems
- Extensible framework and capability plugins
- Interactive and non-interactive generation from the same project definition
- Presets as compositions of validated choices
- Quality bar: working integrations, proportional architecture, cross-platform CLI

Python (FastAPI, Django, potentially Flask) is the first ecosystem. It is not the permanent boundary of the product.

## Initial scope

The first product version targets **Python** project generation.

**Potential project types**

- REST API
- CLI application
- Worker / background service

**Potential frameworks**

- FastAPI
- Django
- Flask

**Potential capabilities / integrations** (not all combinations are valid)

- Databases: PostgreSQL, SQLite
- ORMs: SQLAlchemy, Django ORM
- Redis
- JWT authentication
- Docker
- pytest, Ruff
- Environment configuration
- Migrations (e.g. Alembic where appropriate)

**Design requirement:** the system must validate incompatible or meaningless combinations. Framework-specific options stay framework-aware (e.g. do not offer SQLAlchemy-centric paths for a pure Django stack without a conscious design).

**Generation status:** Python FastAPI REST APIs (Simple and Modular Monolith) are generated as runnable projects. Other frameworks remain catalog options or future work until their generators exist.

## Product principles

### Working software first

Generate projects that actually work together. Do not ship fake architecture of empty directories and placeholders. If a feature requires integration (e.g. FastAPI + PostgreSQL + SQLAlchemy + Alembic), include coherent initial configuration that can run. The same applies to Docker, Redis, auth, jobs, testing, etc.

### Avoid unnecessary complexity

Do not add technologies or layers only because they are popular. Avoid microservices without reason, unnecessary abstractions, excessive interfaces, needless brokers, surplus configuration, empty-value tests, and documentation that does not help development. Architecture must be proportional to selections.

### Do not artificially minimize tasks

A change should be complete enough that the resulting functionality is genuinely usable. Do not split work into tiny artificial tasks merely to look smaller. Keep changes logically understandable and reviewable.

### Cross-platform by design

Forge must work on Linux, macOS, and Windows. Avoid shell-specific behavior unless there is no reasonable alternative. Avoid hardcoded Unix paths. Prefer platform-independent APIs (especially in Python).

### Ask only questions that affect the resulting project

The interactive flow is adaptive. Irrelevant questions must not appear. See [cli.md](./cli.md).

### Explicit choices, owned code

Forge surfaces decisions; it does not hide architecture behind opacity. Users should be able to read and continue the generated project without reverse-engineering a black box.

## Non-goals

By default, Forge is **not**:

- an IDE
- a full deployment platform
- a cloud provisioning platform
- a replacement for package managers
- a tool that hides all architectural decisions from developers
- a generator of gigantic opaque applications users cannot understand
- a single forced architecture for every project

Forge helps developers make and implement architectural choices—then gets out of the way.
