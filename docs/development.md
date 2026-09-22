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
Python >= 3.11 · uv · Typer · Rich · questionary · Pydantic v2 · Jinja2 · pytest
```

### Run

```bash
uv sync
uv run forge new my-api
uv run pytest
```

### Import boundaries

```text
forge.cli → forge.core, forge.generator
forge.generator → forge.core
forge.core → (no UI)
```

### Adding a framework

1. Catalog + `GENERATABLE` entries
2. Resolver mapping (deps, features, implied ORM/migrations/REST) in `forge.generator.resolve`
3. Templates under `templates/<language>/<framework>/<architecture>/`
4. Adaptive CLI prompts (only user-selectable questions; leave implications to the resolver)
5. Tests + generated-project smoke validation

Do not add a plugin manager for the next framework.

Keep the distinction:

```text
ProjectDefinition = explicit user intent
GenerationPlan    = resolved implementation
```

## Open decisions

- `--config` format
- CLI / Worker generators
- Slimmer FastAPI dependency set
- Whether Django should ever support a non-REST project type without DRF
- Whether Flask should ever offer an ORM other than SQLAlchemy
- How far Clean Architecture persistence demos should go beyond a session/port boundary
