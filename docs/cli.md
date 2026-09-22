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

Non-empty destinations are refused. Unsupported frameworks fail during **resolution** before writes.

## Adaptive questioning

**Ask only questions that affect the generated project.**

- Framework options depend on language + project type (FastAPI, Django, …)
- **FastAPI:** optional database → engine → Alembic confirm; ORM implied (SQLAlchemy)
- **Django (REST API):** database engine only; Django ORM + Django migrations + DRF implied (shown as dim notes, not false choices)
- Docker / pytest / Ruff are explicit confirms for both

## Generation result

Shows framework, architecture, capabilities, and next steps (framework-specific run/migrate commands).

## Interaction modes

| Mode | Status |
|------|--------|
| Interactive | **Implemented** (FastAPI + Django) |
| Presets / `--config` | Planned |
