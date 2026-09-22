# Forge

Cross-platform CLI for interactively designing and generating application project architectures.

**Status:** generates runnable **Python FastAPI**, **Django**, and **Flask** REST API projects with **Simple**, **Modular Monolith**, or **Clean Architecture** layouts. Supports interactive, `--preset`, and YAML `--config` generation.

**Requires:** Python **3.11+**

## Install (from a built wheel)

PyPI publishing is not set up yet. Build and install locally:

```bash
uv sync
uv build
uv pip install dist/forge_cli-*.whl   # or: pip install dist/forge_cli-*.whl
forge --version
forge new my-api --preset fastapi-postgres
```

Distribution name: **`forge-cli`**. Console script: **`forge`**.

## Development quick start

```bash
uv sync
uv run forge new my-api
uv run forge new my-api --preset fastapi-postgres
# non-interactive config (CI-safe — never prompts):
# uv run forge new --config forge.yaml
# uv run forge new my-api --config forge.yaml
cd my-api
uv sync
```

See [docs/cli.md](docs/cli.md) for the public command surface, presets, destination rules, and exit behavior.

Follow the generated README for framework-specific run commands.

## Documentation

| Document | Contents |
|----------|----------|
| [docs/product.md](docs/product.md) | Product definition, principles, scope |
| [docs/architecture.md](docs/architecture.md) | Resolution, GenerationPlan, frameworks |
| [docs/cli.md](docs/cli.md) | Interactive CLI, presets, and YAML configuration |
| [docs/generation.md](docs/generation.md) | Generated-project quality |
| [docs/development.md](docs/development.md) | Toolchain, packaging, and workflow |

## Layout

```text
src/forge/cli/
src/forge/core/          # ProjectDefinition, YAML config, presets
src/forge/generator/     # resolve → GenerationPlan → render
templates/               # Jinja templates (packaged as forge/templates in the wheel)
tests/
scripts/packaging_smoke.sh
```
