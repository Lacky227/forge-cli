# CLI experience

Forge’s interactive CLI should feel modern, clear, and pleasant.

## Stack

| Concern | Choice | Role |
|---------|--------|------|
| Commands / args | **Typer** | Subcommands, help, version |
| Presentation | **Rich** | Banner, definition panel, generation summary |
| Interactive prompts | **questionary** | Select / confirm / text |
| Domain model | **Pydantic** | `ProjectDefinition` |
| Templates | **Jinja2** | Project file generation |

## Current commands

```bash
uv sync
uv run forge --help
uv run forge --version
uv run forge new
uv run forge new my-api
```

| Command | Behavior |
|---------|----------|
| `forge new` | Interactive interview → generate `./<name>` |
| `forge new NAME` | Same flow; skips the name prompt; creates `./NAME` |
| `forge --version` / `-V` | Print version |

Generation refuses an existing **non-empty** destination. There is no `--force` yet.

Unsupported combinations (e.g. Django) fail during **resolution** before any project files are written.

## Generation result

After a successful FastAPI generation, Forge shows a short summary and next steps, for example:

```text
╭─ Project created ─╮
│ ✓ my-api          │
│ FastAPI           │
│ Modular Monolith  │
│ …                 │
╰───────────────────╯

Next steps:
  cd my-api
  uv sync
  uv run fastapi dev src/my_api/main.py
```

## Adaptive questioning

**Ask only questions that affect the resulting project.**

- Framework list depends on language + project type
- Architecture prompted only when multiple styles exist
- Database / Alembic only for database-capable frameworks
- ORM is implied by framework (FastAPI → SQLAlchemy)
- Docker, pytest, and Ruff are explicit confirmations

## Interaction modes

| Mode | Status |
|------|--------|
| Interactive (`forge new`) | **Implemented** (definition + generation for FastAPI) |
| Preset-assisted | Planned |
| Config-driven (`--config`) | Planned; same `ProjectDefinition` model |

## Cross-platform behavior

- Prompt stack is prompt_toolkit-based (Linux, macOS, Windows)
- Paths use `pathlib`; no shell-specific install scripts
- Cancel exits cleanly without writing a project
