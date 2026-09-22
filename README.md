# Forge

Cross-platform CLI for interactively designing and generating application project architectures.

**Status:** foundation spike — interactive `forge new` builds a normalized `ProjectDefinition`. Project generation is not implemented yet.

## Quick start

```bash
uv sync
uv run forge new
uv run forge new my-api
uv run pytest
```

## Documentation

| Document | Contents |
|----------|----------|
| [docs/product.md](docs/product.md) | Product definition, principles, scope, non-goals |
| [docs/architecture.md](docs/architecture.md) | Architecture, `ProjectDefinition`, package layout |
| [docs/cli.md](docs/cli.md) | Interactive CLI, commands, prompt stack |
| [docs/generation.md](docs/generation.md) | Quality requirements for generated projects |
| [docs/development.md](docs/development.md) | Toolchain and development workflow |

## Layout

```text
src/forge/cli/    # Typer + questionary + Rich
src/forge/core/   # ProjectDefinition (no UI deps)
tests/
docs/
```

## First ecosystem

Python — FastAPI, Django, Flask (and CLI/worker frameworks in the adaptive catalog). Core types stay open to additional languages later.
