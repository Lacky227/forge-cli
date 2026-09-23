<div align="center">

# FORGE

**Build your architecture.**

A cross-platform CLI that generates runnable Python backend projects<br>
with deliberate architecture, persistence, tooling, and infrastructure choices.

[![PyPI](https://img.shields.io/pypi/v/forge-scaffolder.svg)](https://pypi.org/project/forge-scaffolder/)
[![Python](https://img.shields.io/pypi/pyversions/forge-scaffolder.svg)](https://pypi.org/project/forge-scaffolder/)
[![CI](https://github.com/Lacky227/forge-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Lacky227/forge-cli/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](https://github.com/Lacky227/forge-cli)

**Current release:** [0.2.0](https://github.com/Lacky227/forge-cli/releases/tag/v0.2.0) · PyPI: [`forge-scaffolder`](https://pypi.org/project/forge-scaffolder/) · CLI: `forge`

</div>

---

## Quick start

```bash
uv tool install forge-scaffolder
forge new my-api
cd my-api
uv sync
```

Run and migration commands depend on the resolved stack. Forge prints them after generation, and the generated project README repeats the ones that apply.

Or skip installation for a one-off run:

```bash
uvx --from forge-scaffolder forge new my-api
```

| Role | Name |
|------|------|
| PyPI package | **`forge-scaffolder`** |
| CLI command | **`forge`** |
| Repository | [Lacky227/forge-cli](https://github.com/Lacky227/forge-cli) |

---

## What Forge is

Starting a backend project means deciding framework, project structure, persistence, migrations, Docker, testing, and linting — often from scratch, every time.

Forge turns those explicit decisions into a coherent, runnable project. It resolves implications (ORM, clients, dependencies, commands) and generates a codebase you can install, run, and keep developing by hand.

It is a **scaffolder**, not a runtime dependency of the projects it creates.

---

## Interactive experience

```text
$ forge new my-api

What are you building?
> REST API

Language
> Python

Framework
> FastAPI

Architecture
> Modular Monolith

Add a database?
> Yes

Database type
> Both

SQL database
> PostgreSQL

Include Alembic migrations?
> Yes

NoSQL database
> Redis

Include Docker support?
> Yes

Include testing setup (pytest)?
> Yes

Include Ruff linting?
> Yes

✓ Created my-api

Location:
  ./my-api

Stack:
  FastAPI
  Modular Monolith
  PostgreSQL
  SQLAlchemy
  Alembic
  Redis
  redis

Next steps:
  cd my-api
  uv sync
  docker compose up -d db redis
  ...
```

Prompts adapt to the stack. Django, for example, always asks for SQL and offers NoSQL as an optional addition — it never asks for SQLAlchemy or Alembic.

---

## Supported stack

Python **REST API** generation for FastAPI, Django, and Flask.

| | Simple | Modular Monolith | Clean Architecture |
|--|:------:|:----------------:|:------------------:|
| **FastAPI** | ✓ | ✓ | ✓ |
| **Django** | ✓ | ✓ | ✓ |
| **Flask** | ✓ | ✓ | ✓ |

| Capability | Options | Resolved into |
|------------|---------|---------------|
| **SQL** | PostgreSQL, SQLite | FastAPI/Flask → SQLAlchemy (+ optional Alembic); Django → Django ORM + migrations |
| **NoSQL** | MongoDB, Redis | MongoDB → PyMongo; Redis → redis-py |
| **Tooling** | pytest, Ruff, Docker | Wired when selected |

---

## Persistence

SQL and NoSQL are independent first-class choices:

```text
Persistence
├── SQL
│   ├── PostgreSQL
│   └── SQLite
│
└── NoSQL
    ├── MongoDB
    └── Redis
```

Choose **none**, **SQL only**, **NoSQL only**, or **both** (at most one engine from each category).

**Django note:** Django REST APIs always require SQL. MongoDB or Redis can be added alongside it as separate clients — not as Django ORM backends.

---

## Generated project

Example: FastAPI · Modular Monolith · PostgreSQL · Redis · Alembic · Docker

```text
my-api/
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── pyproject.toml
├── README.md
├── migrations/
├── src/
│   └── my_api/
│       ├── main.py
│       ├── api/
│       │   └── routes/
│       ├── core/
│       │   ├── config.py
│       │   ├── database.py
│       │   └── redis_client.py
│       ├── models/
│       ├── repositories/
│       ├── schemas/
│       └── services/
└── tests/
    └── test_health.py
```

Generated projects are conventional Python packages — installable with `uv`, runnable immediately, and editable without Forge.

---

## Architecture styles

| Style | Best for |
|-------|----------|
| **Simple** | Small APIs and prototypes that prefer minimal structure |
| **Modular Monolith** | Growing applications organized around features/modules |
| **Clean Architecture** | Projects that need explicit boundaries and dependency direction |

Architecture chooses layout. Framework chooses how HTTP and persistence are wired. The same three styles work across FastAPI, Django, and Flask.

---

## Presets

Presets are named compositions of valid Forge choices — not separate generators. They still go through the same resolution pipeline.

| Preset | Stack |
|--------|--------|
| `fastapi-postgres` | FastAPI · Modular Monolith · PostgreSQL · Alembic · Docker |
| `fastapi-postgres-clean` | FastAPI · Clean Architecture · PostgreSQL · Alembic · Docker |
| `fastapi-mongo` | FastAPI · Modular Monolith · MongoDB · Docker |
| `flask-postgres` | Flask · Modular Monolith · PostgreSQL · Alembic · Docker |
| `django-postgres` | Django · Modular Monolith · PostgreSQL · Docker |

```bash
forge new my-api --preset fastapi-postgres
forge plan --preset fastapi-mongo
```

---

## Inspect before you generate

`forge plan` resolves a configuration and prints the full `GenerationPlan` — without writing any files.

```bash
forge plan --preset fastapi-mongo
```

```text
Project
  Framework:     FastAPI
  Architecture:  Modular Monolith

NoSQL
  Database:      MongoDB
  Client:        pymongo

Tooling
  Testing:       pytest
  Linting:       Ruff
  Docker:        yes
```

Use it to verify implied ORM/clients, dependencies, and commands before scaffolding.

---

## YAML configuration

Fully non-interactive generation for scripts and CI:

```yaml
name: my-api
type: rest-api
framework: fastapi
architecture: modular-monolith

persistence:
  sql: postgresql
  nosql: redis

migrations: true
testing: true
linting: true
docker: true
```

```bash
forge new --config forge.yaml
```

Legacy `database: postgresql` remains supported as an SQL-only shorthand. Prefer the `persistence` model for new configs.

`--preset` and `--config` cannot be combined.

---

## Philosophy

- **Working software first** — selected integrations are wired, not stubbed.
- **Explicit resolution** — Forge shows what it inferred (ORM, migrations, clients).
- **Proportional architecture** — no layers or dependencies you did not ask for.
- **Owned code** — output should look like a normal project a team would maintain.
- **Scaffolder, not a framework** — Forge leaves the generated tree; it is not a runtime.

---

## Documentation

| Document | Contents |
|----------|----------|
| [docs/product.md](docs/product.md) | Product definition, principles, scope |
| [docs/architecture.md](docs/architecture.md) | Resolution model, frameworks, layouts |
| [docs/cli.md](docs/cli.md) | Commands, presets, YAML schema |
| [docs/generation.md](docs/generation.md) | Compatibility matrix and quality bar |
| [docs/development.md](docs/development.md) | Toolchain, packaging, versioning |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

---

## Project status

**Current release: [0.2.0](https://github.com/Lacky227/forge-cli/releases/tag/v0.2.0)** — public development / alpha.

Current limitations:

- Other languages and non-REST project types are not generated yet
- Django REST APIs require SQL (NoSQL alone is not enough)
- Redis integration is a client wiring — not cache/session/queue abstractions
- MongoDB uses PyMongo directly — no ODM layer
- At most one SQL database and one NoSQL database per project

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/development.md](docs/development.md).

```bash
uv sync
uv run pytest
uv run forge --help
```

---

## License

[GPL-3.0-only](LICENSE)

<div align="center">

[PyPI](https://pypi.org/project/forge-scaffolder/) · [Releases](https://github.com/Lacky227/forge-cli/releases) · [Issues](https://github.com/Lacky227/forge-cli/issues)

</div>
