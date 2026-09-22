# Forge

Cross-platform CLI for interactively designing and generating application project architectures.

**Status:** generates runnable **Python FastAPI**, **Django**, and **Flask** REST API projects (Simple / Modular Monolith).

## Quick start

```bash
uv sync
uv run forge new my-api
cd my-api
uv sync
```

Follow the generated README for framework-specific run commands.

## Documentation

| Document | Contents |
|----------|----------|
| [docs/product.md](docs/product.md) | Product definition, principles, scope |
| [docs/architecture.md](docs/architecture.md) | Resolution, GenerationPlan, frameworks |
| [docs/cli.md](docs/cli.md) | Interactive CLI |
| [docs/generation.md](docs/generation.md) | Generated-project quality |
| [docs/development.md](docs/development.md) | Toolchain and workflow |

## Layout

```text
src/forge/cli/
src/forge/core/
src/forge/generator/     # resolve → GenerationPlan → render
templates/python/fastapi/
templates/python/django/
templates/python/flask/
tests/
```
