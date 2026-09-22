# Contributing

Thanks for your interest in Forge. Keep changes small, coherent, and aligned with the existing docs.

## Prerequisites

- Python **>= 3.11**
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Run the CLI locally

```bash
uv run forge --help
uv run forge --version
uv run forge new my-api
uv run forge new my-api --preset fastapi-postgres
```

## Test

```bash
uv run pytest
```

Packaging checks (slower; builds wheels):

```bash
uv run pytest -m packaging
bash scripts/packaging_smoke.sh
```

## Architecture (short)

```text
CLI / config / preset
        ↓
ProjectDefinition          # explicit user intent
        ↓
resolve_plan()
        ↓
GenerationPlan             # resolved implementation
        ↓
generator + templates
```

Details: [docs/architecture.md](docs/architecture.md).  
CLI / presets / config: [docs/cli.md](docs/cli.md).  
Generated-project quality: [docs/generation.md](docs/generation.md).

## Changing generators

Do not add a plugin system for the next framework. Follow [docs/development.md](docs/development.md): catalog + resolver mapping + templates under `templates/<language>/<framework>/<architecture>/` + tests.

Presets are compositions of valid user choices — not separate generators.

## Documentation

`docs/` and `.cursor/rules/` are living sources of truth. When behavior or architecture changes, update the relevant authoritative document in the same change.

## Git workflow

- Prefer focused GitFlow-style commits (e.g. `feat:`, `fix:`, `docs:`, `chore:`)
- Agents and automated helpers must **not** `git add` / `commit` / `push` unless explicitly asked
- Full workflow notes: [docs/development.md](docs/development.md)

## Pull requests

Use the PR template. Include what changed, why, how you validated, and whether docs were updated.
