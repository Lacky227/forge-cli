# Generated project quality

“Generated successfully” means more than files appearing on disk. The output should be a **usable starting point for a real project**.

## Quality bar

A generated project should ideally:

- have a coherent directory structure for the chosen stack
- declare dependencies correctly
- wire configuration so selected components connect
- **start successfully** (or document the minimal steps to start, if a local service is required)
- expose the expected entry point (API server, CLI, worker, etc.)
- include required environment configuration (e.g. `.env.example`) when relevant
- include appropriate development tooling when selected (tests, linters, formatters)
- include tests **where they provide value** (smoke/entry-point tests beat empty suites)
- include Docker support when selected—and it should be runnable for the generated app
- include database migrations when selected—and they should match the ORM/framework choice
- include documentation appropriate for continuing work on **that** project (not a copy of Forge’s docs)

## Reflect user choices

Do not require every generated project to contain every tool. Optional capabilities appear only when selected (and valid). Absence of an unselected feature is success, not incompleteness.

## Working integrations

Selected features must be integrated, not merely mentioned.

**Bad:** empty `db/` folders and a README saying “add SQLAlchemy later.”

**Good:** FastAPI + PostgreSQL + SQLAlchemy + Alembic yields a coherent initial app config, models/session wiring, migration setup, and env vars that fit together.

The same standard applies to Redis, JWT auth, Docker, background jobs, testing, and linting when those options are chosen.

## Proportional structure

Layout and abstractions should match project type and selections. Prefer conventions familiar to that ecosystem. Avoid microservices, message brokers, or deep interface trees unless the user’s choices justify them.

## Maintainability

Generated code should be readable by humans who never used Forge. Prefer clear names, conventional layouts, and minimal magic. Opaque generators that users cannot evolve manually fail the product goal—see [product.md](./product.md).
