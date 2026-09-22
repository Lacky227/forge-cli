# Forge

Cross-platform CLI for interactively designing and generating application project architectures.

Run something like `forge new`, answer clear questions about what you want to build, and get a coherent, runnable project structured from those choices.

**Status:** documentation and project conventions only. Application implementation has not started.

## Documentation

| Document | Contents |
|----------|----------|
| [docs/product.md](docs/product.md) | Product definition, principles, scope, non-goals |
| [docs/architecture.md](docs/architecture.md) | Architecture layers, project definition, presets, extensibility |
| [docs/cli.md](docs/cli.md) | Interactive CLI experience |
| [docs/generation.md](docs/generation.md) | Quality requirements for generated projects |
| [docs/development.md](docs/development.md) | Development workflow and technology direction |

Cursor agent rules: [`.cursor/rules/`](.cursor/rules/).

## First ecosystem

Python — FastAPI, Django, and potentially Flask — with a core designed so other languages and frameworks can be added later without rewriting Forge.
