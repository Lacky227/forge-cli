# Forge

Cross-platform CLI for interactively designing and generating application project architectures.

**Status:** first vertical slice — `forge new` can generate a runnable **Python FastAPI** REST API (Simple or Modular Monolith) with optional PostgreSQL/SQLite, SQLAlchemy, Alembic, Docker, pytest, and Ruff.

## Quick start

```bash
uv sync
uv run forge new my-api
cd my-api
uv sync
uv run fastapi dev src/my_api/main.py
```

## Documentation

| Document | Contents |
|----------|----------|
| [docs/product.md](docs/product.md) | Product definition, principles, scope |
| [docs/architecture.md](docs/architecture.md) | Architecture, generator, templates |
| [docs/cli.md](docs/cli.md) | Interactive CLI and commands |
| [docs/generation.md](docs/generation.md) | Generated-project quality bar |
| [docs/development.md](docs/development.md) | Toolchain and workflow |

## Layout

```text
src/forge/cli/         # interaction
src/forge/core/        # ProjectDefinition
src/forge/generator/   # generation engine
templates/             # Jinja2 project templates
tests/                 # Forge tests
```
