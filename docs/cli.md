# CLI experience

Forge’s interactive CLI should feel modern, clear, and pleasant.

## Stack

Typer · Rich · questionary · Pydantic · Jinja2 (generation)

## Current commands

```bash
uv sync
uv run forge new
uv run forge new my-api
uv run forge --version
```

| Command | Behavior |
|---------|----------|
| `forge new [NAME]` | Interview → generate `./<name>` |

Non-empty destinations are refused. Unsupported combinations fail during **resolution** before writes.

## Adaptive questioning

**Ask only questions that affect the generated project.**

Users think in terms of *what they are building*, not which internal implementation classes Forge uses.

- Framework options depend on language + project type (FastAPI, Django, Flask, …)
- Architecture for REST API: Simple, Modular Monolith, Clean Architecture
- **FastAPI:** optional database → engine → Alembic confirm; SQLAlchemy is implied (dim note)
- **Flask:** optional database → engine → Alembic confirm; SQLAlchemy is implied when a DB is selected (dim note). No Django-style forced infrastructure.
- **Django (REST API):** database engine only; Django ORM + Django migrations + DRF are implied (dim notes, not selectable choices)
- Docker / pytest / Ruff are explicit confirms for all three

Architecture questions are independent of framework. Framework implications are applied in `resolve_plan`, not by stuffing implied fields into `ProjectDefinition` during the interview.

## Generation result

Shows framework, architecture, capabilities, and next steps (framework-specific run/migrate commands). Resolved details (ORM, migration system, DRF) appear in the success summary from the `GenerationPlan`.

## Interaction modes

| Mode | Status |
|------|--------|
| Interactive | **Implemented** (FastAPI + Django + Flask; Simple / Modular / Clean) |
| Presets / `--config` | Planned |
