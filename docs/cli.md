# CLI experience

Forge’s interactive CLI should feel modern, clear, and pleasant.

## Chosen stack (foundation spike)

| Concern | Choice | Role |
|---------|--------|------|
| Commands / args | **Typer** | Subcommands, help, version, packaging entrypoint |
| Presentation | **Rich** | Banner, definition panel, readable output |
| Interactive prompts | **questionary** | Cross-platform select/confirm/text on prompt_toolkit |
| Domain model | **Pydantic** | `ProjectDefinition` validation (in `forge.core`, not the CLI) |

**Why this mix:** Typer alone does not provide polished arrow-key menus. Rich alone is weak for structured selects. questionary (prompt_toolkit) gives keyboard navigation and solid Windows/macOS/Linux support while staying easy to style alongside Rich. InquirerPy was considered; questionary was chosen for a smaller, mature API that still meets the UX bar. Jinja2 and PyYAML are **not** dependencies yet (no templates or config-file mode in this spike).

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
| `forge new` | Interactive interview; prints a validated project definition |
| `forge new NAME` | Same flow; skips the name prompt |
| `forge --version` / `-V` | Print version |

Generation is **not** implemented. The command completes after showing the definition.

## Example interactive flow

```text
╭────────────────────────────────╮
│    ⚒  FORGE                    │
│    Build your architecture.    │
╰────────────────────────────────╯

What are you building?
❯ REST API
  CLI Application
  Worker

Language
❯ Python

Framework
❯ FastAPI
  Django
  Flask

Architecture
❯ Simple
  Modular Monolith
  Clean Architecture

Include a database? (Y/n)
Database engine
❯ PostgreSQL
  SQLite

Include Docker support? (Y/n)
Include testing setup? (Y/n)
```

Then a **Project Definition** panel summarizes the normalized result.

## Adaptive questioning

**Principle: ask only questions that affect the resulting project.**

Demonstrated in the prototype:

- Framework list depends on language + project type (e.g. CLI → Typer/Click, not FastAPI).
- Architecture is prompted only when more than one style is valid (CLI → Simple only; question skipped).
- Database engine / ORM questions appear only for database-capable frameworks; ORM is implied by framework (e.g. Django → django-orm, FastAPI → sqlalchemy).
- Worker frameworks differ from API frameworks.

## Interaction modes

| Mode | Status |
|------|--------|
| Interactive (`forge new`) | **Implemented** (definition only) |
| Preset-assisted | Planned |
| Config-driven (`--config`) | Planned; same `ProjectDefinition` model already constructible from data |

## Cross-platform behavior

- Prompt stack is prompt_toolkit-based (Linux, macOS, Windows).
- Paths and packaging use Python/`uv` conventions—no shell-specific install scripts.
- Cancel (Ctrl+C / abort) exits cleanly without a partial definition.

## UX guidelines

- Concise questions, useful defaults, clear selection state
- Graceful cancellation and short validation errors
- No huge ASCII art, noisy animations, or long in-prompt essays
