# Development

Guidance for implementing Forge.

## Documentation philosophy

Keep documentation **useful and small**. Update authoritative docs in the same task when behavior changes.

| Document | Role |
|----------|------|
| [product.md](./product.md) | Product definition, principles, scope, non-goals |
| [architecture.md](./architecture.md) | Layers, resolution, plan, generator, templates |
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
uv · Typer · Rich · questionary · Pydantic v2 · Jinja2 · pytest (dev)
```

### Run Forge locally

```bash
uv sync
uv run forge new my-api
uv run pytest
```

### Import boundaries

```text
forge.cli         → forge.core, forge.generator
forge.generator   → forge.core
forge.core        → (no cli / UI libs)
```

### Generation flow for contributors

```text
ProjectDefinition
    → resolve_plan()      # forge.generator.resolve
    → GenerationPlan
    → generate_from_plan()  # filesystem + Jinja
```

- Put framework/capability → dependency and feature mapping in **resolve**, not the CLI.
- Keep Jinja templates presentational; pass resolved dependency lists from the plan.
- Do not add a plugin manager for the next framework—add resolver mapping + templates.

### Generated dependency policy

Minimum lower bounds in generated `pyproject.toml`; selected by the resolver.

## Open decisions

- Public `--config` format and UX
- PyPI distribution name long-term
- Django / Flask / Clean Architecture generators
- Slimmer FastAPI dependency set vs `fastapi[standard]`
- How far to data-drive catalog vs small resolver functions per framework

## Git discipline

Do not stage, commit, or push unless a human explicitly asks.
