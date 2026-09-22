# Development

Guidance for implementing Forge.

## Documentation philosophy

Keep documentation **useful and small**. Update authoritative docs in the same task when behavior changes. Do not create progress reports, diaries, or duplicate architecture docs.

| Document | Role |
|----------|------|
| [product.md](./product.md) | Product definition, principles, scope, non-goals |
| [architecture.md](./architecture.md) | Layers, package layout, generator, templates |
| [cli.md](./cli.md) | UX, commands, prompt stack |
| [generation.md](./generation.md) | Generated-project quality bar |
| [development.md](./development.md) | Workflow, toolchain, how to run |

## Development workflow

1. Read relevant `docs/` and `.cursor/rules/`.
2. Inspect the existing implementation.
3. Implement the smallest coherent change that works.
4. Run validation (`uv run pytest`; generate and smoke-test when touching generation).
5. Update documentation if behavior/architecture changed.
6. Summarize and suggest a GitFlow-style commit message.
7. **Do not** run `git add` / `git commit` / `git push` unless explicitly asked.

## Technology (current)

```text
Python >= 3.11
uv
Typer
Rich
questionary
Pydantic v2
Jinja2
pytest (dev)
```

PyYAML is still unused (no config-file mode yet).

### Run Forge locally

```bash
uv sync
uv run forge new my-api
uv run pytest
```

### Import boundaries

```text
forge.cli        → forge.core, forge.generator
forge.generator  → forge.core
forge.core       → (no cli / generator / UI libs)
```

### Templates

- Source of truth: repository `templates/`
- Selected by `language/framework/architecture`
- Rendered only by `forge.generator`, never by CLI prompt handlers

### Generated dependency policy

Minimum lower bounds in generated `pyproject.toml`; no upper pins by default. Prefer `uv`-friendly packaging (hatchling, `src/` layout).

## Open decisions

- Public `--config` format and UX
- PyPI distribution name long-term
- Django / Flask / Clean Architecture generators
- Whether `fastapi[standard]` vs slimmer FastAPI + uvicorn pins is preferable long-term
- Plugin declaration model beyond the concrete catalog

## Git discipline

Do not stage, commit, or push unless a human explicitly asks. Suggest one coherent GitFlow-style commit message per completed change.
