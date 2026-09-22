# Development

Guidance for implementing Forge.

## Documentation philosophy

Keep documentation **useful and small**.

Do **not** create progress reports, diaries, “task completed” write-ups, duplicate architecture docs, or changelogs for every tiny change.

When implementation changes something already documented, **update the existing authoritative document** in the same logical task.

| Document | Role |
|----------|------|
| [product.md](./product.md) | Product definition, principles, scope, non-goals |
| [architecture.md](./architecture.md) | Layers, package layout, `ProjectDefinition`, extensibility |
| [cli.md](./cli.md) | UX, commands, prompt stack |
| [generation.md](./generation.md) | Generated-project quality bar |
| [development.md](./development.md) | Workflow, toolchain, how to run |

Root [README.md](../README.md) is a short entry point; it must not diverge from these docs.

## Development workflow

1. Read relevant documentation under `docs/`.
2. Read relevant `.cursor/rules/`.
3. Inspect the existing implementation.
4. Understand the current architecture.
5. Plan the smallest coherent implementation that works.
6. Implement the feature completely enough to be usable.
7. Run appropriate validation.
8. Update relevant documentation/rules if behavior or architecture changed.
9. Review the resulting diff.
10. Provide a concise summary.
11. Provide a suggested GitFlow-style commit message when the change is coherent and complete.
12. **Do not** run `git add`, `git commit`, or `git push`.

## Technology (current)

Decided for the foundation spike (revisitable if evidence warrants):

```text
Python >= 3.11
uv                 # local env, lockfile, scripts
Typer              # CLI commands
Rich               # presentation
questionary        # interactive prompts
Pydantic v2        # ProjectDefinition
pytest             # tests (dev)
```

**Not added yet:** Jinja2, PyYAML (no templates / config-file mode).

Packaging: `pyproject.toml` + hatchling, import package `forge`, console script `forge`.

### Run locally

```bash
uv sync
uv run forge new
uv run pytest
uv run python -m forge new
```

### Import boundary

```text
forge.cli  →  forge.core   (allowed)
forge.core →  forge.cli    (forbidden)
```

UI libraries must not appear in `forge.core`.

## Open decisions

- Public config file format and `--config` UX
- PyPI distribution name long-term (`forge` vs `forge-cli`)
- Template engine and template layout (when generation starts)
- How framework plugins declare compatibility (beyond today’s catalog)
- Whether to stay on questionary or revisit InquirerPy if UX needs grow

## Scope and quality expectations

- Prefer working integrations over placeholders.
- Prefer quality over ceremony: no tests, abstractions, files, or dependencies without meaningful value.
- Do not expand tasks into unrelated refactors; do make small architectural fixes required for correctness.
- Stay cross-platform.

## Git discipline

Do **not** stage, commit, or push unless a human explicitly asks.

Suggested commit messages use GitFlow-style prefixes for coherent, completed changes:

```text
feat: add project definition model
fix: resolve template selection
refactor: separate generation engine from cli
docs: define generator architecture
chore: configure packaging
```
