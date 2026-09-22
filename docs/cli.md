# CLI experience

Forge’s interactive CLI should feel modern, clear, and pleasant. Presentation may use libraries such as Rich; the exact UI toolkit is an implementation choice.

## Example flow

```text
╭──────────────────────────────────────╮
│             ⚒ FORGE                  │
│     Build your architecture.         │
╰──────────────────────────────────────╯

What are you building?

❯ REST API
  Web App
  CLI
  Worker
  Microservice
  Library
```

Subsequent questions depend on prior answers. Only ask what changes the generated project.

## Adaptive questioning

**Principle: ask only questions that affect the resulting project.**

Examples:

- If the user chooses Django, do not ask questions that only make sense for FastAPI.
- If the user disables a database, hide database engine, ORM, and migration questions.
- If Docker is disabled, do not ask Docker-only options.
- Framework-specific capabilities stay behind framework selection.

The flow should progressively narrow options and avoid long questionnaires full of irrelevant choices.

## Interaction modes (intended)

| Mode | Intent |
|------|--------|
| Interactive | `forge new` — guided prompts |
| Preset-assisted | `forge new … --preset …` — start from a valid composition, optionally customize |
| Config-driven | `forge new … --config …` — non-interactive, same definition model |

All modes should feed the same normalized project definition. See [architecture.md](./architecture.md).

## Cross-platform behavior

- Works on Linux, macOS, and Windows
- Avoid shell-specific prompts or scripts as the primary UX
- Paths, line endings, and terminal capabilities must be handled portably
- Degrade gracefully when fancy terminal features are unavailable where practical

## Public commands (conceptual)

Exact command set will solidify during implementation. Expected early surface:

- `forge new` — create a project
- `forge preset list` (and related preset commands) — browse/use presets
- Help and version commands consistent with normal CLI practice

Document real flags and behavior here when they exist; do not invent a stable public API ahead of implementation beyond the concepts above.
