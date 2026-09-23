# Forge

Cross-platform CLI for interactively designing and generating application project architectures.

**Status:** public development release **`0.2.0`** (`forge-scaffolder` on PyPI). Generates runnable **Python FastAPI**, **Django**, and **Flask** REST API projects with **Simple**, **Modular Monolith**, or **Clean Architecture** layouts. Persistence supports independent **SQL** (PostgreSQL, SQLite) and **NoSQL** (MongoDB, Redis) selections. Supports interactive / `--preset` / YAML `--config` generation and `forge plan` inspection.

**Requires:** Python **3.11+** (tested on 3.11, 3.12, 3.13)

## Supported today

| | Simple | Modular Monolith | Clean |
|--|--------|------------------|-------|
| FastAPI | yes | yes | yes |
| Django | yes | yes | yes |
| Flask | yes | yes | yes |

**Persistence:** SQL (PostgreSQL, SQLite) and NoSQL (MongoDB, Redis) are independent — choose neither, either, or both.

## Install

```bash
uv tool install forge-scaffolder
# or: pip install forge-scaffolder
forge --version
forge new my-api --preset fastapi-postgres
```

Naming:

| Role | Name |
|------|------|
| PyPI distribution | **`forge-scaffolder`** |
| Console script | **`forge`** |
| Python package | **`forge`** |
| GitHub repository | [Lacky227/forge-cli](https://github.com/Lacky227/forge-cli) |

Build and install from this repository:

```bash
uv sync
uv build
uv pip install dist/forge_scaffolder-*.whl   # or: pip install dist/forge_scaffolder-*.whl
forge --version
forge new my-api --preset fastapi-postgres
```

## Quick start (development checkout)

```bash
uv sync
uv run forge new my-api
uv run forge new my-api --preset fastapi-postgres
# non-interactive config (CI-safe — never prompts):
# uv run forge new --config forge.yaml
cd my-api
uv sync
```

Follow the generated project README for framework-specific run commands.

## Configuration and presets

- **Interactive:** `forge new [NAME]` — adaptive prompts only for choices that affect the project
- **YAML:** `forge new [NAME] --config forge.yaml` — fully non-interactive
- **Preset:** `forge new NAME --preset fastapi-postgres` — curated stack; no prompts
- **Plan:** `forge plan --preset fastapi-postgres` — show resolved `GenerationPlan` without writing files

`--preset` and `--config` cannot be combined. Details: [docs/cli.md](docs/cli.md).

## Documentation

| Document | Contents |
|----------|----------|
| [docs/product.md](docs/product.md) | Product definition, principles, scope |
| [docs/architecture.md](docs/architecture.md) | Resolution, GenerationPlan, frameworks |
| [docs/cli.md](docs/cli.md) | Commands, presets, YAML configuration |
| [docs/generation.md](docs/generation.md) | Generated-project quality |
| [docs/development.md](docs/development.md) | Toolchain, packaging, versioning |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

## Development / contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and architecture orientation.

```bash
uv sync
uv run pytest
```

## Versioning

`0.2.0` is the current public development release (PyPI distribution `forge-scaffolder`). See the versioning policy in [docs/development.md](docs/development.md).

## License

GPL-3.0-only. See [`LICENSE`](LICENSE).

## Repository

- Source: [https://github.com/Lacky227/forge-cli](https://github.com/Lacky227/forge-cli)
- Issues: [https://github.com/Lacky227/forge-cli/issues](https://github.com/Lacky227/forge-cli/issues)

## Layout

```text
src/forge/cli/
src/forge/core/          # ProjectDefinition, YAML config, presets
src/forge/generator/     # resolve → GenerationPlan → render
templates/               # Jinja templates (packaged as forge/templates in the wheel)
tests/
scripts/packaging_smoke.sh
docs/
```
