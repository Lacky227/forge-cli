# Development

## Documentation philosophy

Keep docs useful and small. Update authoritative documents when behavior changes.

## Development workflow

1. Read `docs/` and `.cursor/rules/`
2. Inspect implementation
3. Smallest coherent change
4. `uv run pytest` (+ generate/smoke-test when touching generation)
5. Sync docs
6. Suggest a GitFlow commit message
7. Do not `git add` / `commit` / `push` unless asked

## Technology

```text
Python >= 3.11 · uv · Typer · Rich · questionary · Pydantic v2 · Jinja2 · PyYAML · pytest · hatchling
```

Supported interpreters: **3.11, 3.12, 3.13** (`requires-python = ">=3.11"`).

### Run

```bash
uv sync
uv run forge --help
uv run forge --version
uv run forge new my-api
uv run forge new my-api --preset fastapi-postgres
uv run forge new my-api --preset fastapi-postgres --dry-run
uv run forge plan --preset fastapi-postgres
uv run forge new --config forge.yaml
uv run pytest
```

Public CLI contract: `tests/test_cli.py`, `tests/test_presets.py`, `tests/test_plan.py`, `tests/test_dry_run.py`, `tests/test_modules.py`, `tests/test_modules_stage2.py`.
See [cli.md](./cli.md) for the full command surface, presets, and destination/exit behavior.
Module catalog and composition: [modules.md](./modules.md).

When adding a module: update `forge.core.modules`, contribution builders in
`forge.generator.modules`, templates under `templates/python/modules/`, base
contribution loops, tests, and docs in the same change.

### Packaging and distribution

| Role | Name |
|------|------|
| PyPI distribution | **`forge-scaffolder`** |
| Console script / entry point | **`forge`** |
| Python import package | **`forge`** |
| GitHub repository | [Lacky227/forge-cli](https://github.com/Lacky227/forge-cli) |

Jinja templates live at the repository root (`templates/`) for editable development. Hatch **force-includes** them into the wheel as `forge/templates/`, so an installed package is self-contained. `forge.generator.render.templates_root()` resolves:

1. `FORGE_TEMPLATES_ROOT` (override)
2. Packaged `forge/templates` (installed wheel)
3. Repository `templates/` next to `pyproject.toml` (editable checkout only)

```bash
# Build wheel + sdist
uv build

# Clean-install smoke (venv outside the repo; generates FastAPI/Django/Flask projects)
bash scripts/packaging_smoke.sh

# Packaging-focused pytest (builds wheels; skipped by default via addopts)
uv run pytest -m packaging

# Generation smoke (uv sync + framework check/pytest/ruff; SQLite / no-db cases)
uv run pytest -m generation_smoke
```

Canonical repository: [https://github.com/Lacky227/forge-cli](https://github.com/Lacky227/forge-cli).

### Versioning

Current version: **`0.5.0`** — public development version; PyPI distribution **`forge-scaffolder`**.

| Version | Meaning |
|---------|---------|
| `0.x` | Public development releases |
| `0.1.x` | Backwards-compatible fixes and small improvements |
| `0.2.0` through `0.5.0` | Meaningful new capabilities or intentional public-interface changes |
| `1.0.0` | Stable public CLI / domain contract |

Record user-facing changes in [CHANGELOG.md](../CHANGELOG.md). Do not introduce automated semantic-release tooling for routine work.

### Import boundaries

```text
forge.cli → forge.core, forge.generator
forge.generator → forge.core
forge.core → (no UI; may load YAML config → ProjectDefinition)
```

### Adding a framework

1. Catalog + `GENERATABLE` entries
2. Resolver mapping (deps, features, implied ORM/migrations/REST) in `forge.generator.resolve`
3. Templates under `templates/<language>/<framework>/<architecture>/`
4. Adaptive CLI prompts (only user-selectable questions; leave implications to the resolver)
5. Tests + generated-project smoke validation

Security changes additionally require the nine-family SQLite executable matrix
in [generation.md](./generation.md), Django
`makemigrations --check --dry-run`, and wheel-content checks for every
Authentication and Authorization template family (including Stage 3 hardening
includes and cleanup commands). FastAPI TestClient may need to run outside a
restricted worker-thread sandbox.

Do not add a plugin manager for the next framework.

Keep the distinction:

```text
ProjectDefinition = explicit user intent
GenerationPlan    = resolved implementation
```

## Open decisions

- CLI / Worker generators
- Slimmer FastAPI dependency set
- Whether Django should ever support a non-REST project type without DRF
- Whether Flask should ever offer an ORM other than SQLAlchemy
- How far Clean Architecture persistence demos should go beyond a session/port boundary
- Whether Redis should gain first-class cache/session/queue semantics beyond a client
- Config export / round-trip tooling
- Whether preset + config merging is ever worth the precedence complexity (currently rejected)
- Author / maintainer contact metadata for PyPI
- Whether generated projects should inherit Forge's GPL-3.0-only license (they do **not** automatically; decision not made)

Forge itself is licensed **GPL-3.0-only** (see [`LICENSE`](../LICENSE)).
