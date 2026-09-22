# Development

Guidance for people (and agents) implementing Forge. Application code is not present yet; follow this when it is.

## Documentation philosophy

Keep documentation **useful and small**.

Do **not** create:

- progress reports or daily logs
- implementation diaries
- “task completed” write-ups
- duplicate architecture documents
- changelog-like notes for every tiny change

Documentation should describe the system, decisions, usage, and important constraints.

When implementation changes something already documented, **update the existing authoritative document** in the same logical task. Do not add a parallel doc.

Authoritative set today:

| Document | Role |
|----------|------|
| [product.md](./product.md) | Product definition, principles, scope, non-goals |
| [architecture.md](./architecture.md) | Layers, definition model, presets, extensibility, repo layout |
| [cli.md](./cli.md) | Interactive and non-interactive UX |
| [generation.md](./generation.md) | Generated-project quality bar |
| [development.md](./development.md) | Workflow, stack recommendation, docs rules |

Root [README.md](../README.md) is a short entry point; it must not diverge from these docs.

## Development workflow

For each task:

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

Do not require a formal report for every task. Final responses should be concise and useful.

## Technology direction (revisitable)

**Recommendation before implementation—may be revisited:**

```text
Python
Typer
Rich
Jinja2
Pydantic
PyYAML (only if the chosen config format needs it)
uv
```

Interactive prompts may use Typer’s ecosystem, questionary, InquirerPy, or another cross-platform option. **Do not add dependencies until justified.**

Forge should ship as a normal CLI usable on Linux, macOS, and Windows.

Open decisions before (or early in) implementation:

- Exact prompt library
- Config file format (YAML vs other) and whether it is public
- Package layout and distribution (PyPI name, `src` layout, entry points)
- Template engine conventions and template repository layout
- How framework plugins declare compatibility

## Scope and quality expectations

- Prefer working integrations over placeholders (see [generation.md](./generation.md) and [product.md](./product.md)).
- Prefer quality over ceremony: no tests, abstractions, files, or dependencies without meaningful value.
- Do not expand tasks into unrelated refactors; do make small architectural fixes required for a feature to work correctly.
- Stay cross-platform: no OS-specific assumptions in core paths or tooling without a portable fallback.

## Git discipline

Agents and contributors following the Cursor rules must **not** stage, commit, or push unless a human explicitly asks outside the default agent rules for this project.

Suggested commit messages use GitFlow-style prefixes for coherent, completed changes, for example:

```text
feat: add project definition model
fix: resolve template selection
refactor: separate generation engine from cli
docs: define generator architecture
chore: configure packaging
```

Do not suggest a commit after every tiny edit—only after a logically complete change.
