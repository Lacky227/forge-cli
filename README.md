# Forge

Cross-platform CLI for interactively designing and generating application project architectures.

**Status:** first vertical slice — generates runnable **Python FastAPI** projects (Simple / Modular Monolith) from an interactive interview.

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
| [docs/product.md](docs/product.md) | Product definition, principles, scope, non-goals |
| [docs/architecture.md](docs/architecture.md) | Architecture, `ProjectDefinition`, generator, templates |
| [docs/cli.md](docs/cli.md) | Interactive CLI, commands |
| [docs/generation.md](docs/generation.md) | Quality requirements for generated projects |
| [docs/development.md](docs/development.md) | Toolchain and development workflow |

## Layout

```text
src/forge/cli/         # Typer + questionary + Rich
src/forge/core/        # ProjectDefinition (no UI deps)
src/forge/generator/   # Jinja2 generation engine
templates/python/fastapi/
tests/                 # Forge's own tests
```
