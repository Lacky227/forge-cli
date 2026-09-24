# CLI experience

Forge’s interactive CLI should feel modern, clear, and pleasant.

## Stack

Typer · Rich · questionary · Pydantic · Jinja2 · PyYAML (config loading)

## Public command surface

```bash
uv sync
uv run forge
uv run forge --help
uv run forge --version
uv run forge new
uv run forge new --help
uv run forge new my-api
uv run forge new my-api --preset fastapi-postgres
uv run forge new my-api --preset fastapi-postgres --dry-run
uv run forge new --config forge.yaml
uv run forge new my-api --config forge.yaml
uv run forge plan --help
uv run forge plan --preset fastapi-postgres
uv run forge plan --config forge.yaml
uv run forge plan my-api --config forge.yaml
```

| Command | Behavior |
|---------|----------|
| `forge` | Shows help (same as `forge --help`) and exits non-zero |
| `forge --version` / `-V` | Prints `forge <version>` from package metadata |
| `forge new [NAME]` | Interactive interview → generate `./<name>` |
| `forge new NAME --preset ID` | Expand preset → `ProjectDefinition` → generate (no prompts) |
| `forge new [NAME] --config FILE` | Load YAML config (no prompts) → generate |
| `forge new … --dry-run` | Preview concrete output paths for the same inputs; write nothing |
| `forge plan --preset ID` | Resolve and display `GenerationPlan` (no filesystem writes) |
| `forge plan [NAME] --config FILE` | Same for YAML; name precedence matches `forge new` |

`new` generates projects (or previews them with `--dry-run`). `plan` only inspects the resolved plan. Do not add unrelated subcommands.

`--quiet`, `--verbose`, and `--force` are **intentionally deferred** — not part of the current contract. `--dry-run` is supported on `forge new` only.

`--preset` and `--config` **cannot** be combined (rejected with a clear error). ForgeConfig field defaults would make merge precedence ambiguous; keep one non-interactive source of truth.

## Destination behavior

The project name is a **directory name under the current working directory**, not an arbitrary filesystem path.

| Input | Result |
|-------|--------|
| `forge new my-api` | Creates `./my-api` |
| `forge new ./my-api` | Rejected (name must be a simple directory name) |
| `forge new /some/path/my-api` | Rejected (path separators are not allowed) |

Names must start with a letter and contain only letters, digits, hyphens, and underscores (max 64 characters).

### Existing destination

| Destination state | Behavior |
|-------------------|----------|
| Does not exist | Created (dry-run previews without creating) |
| Empty directory | Allowed (project files are written into it; dry-run leaves it empty) |
| Non-empty directory | Error — no overwrite (dry-run rejects the same way; contents untouched) |
| Existing file at that path | Error (dry-run rejects; file untouched) |

Forge never merges into an existing project and does not offer `--force`.

## `forge new --dry-run`

Preview the **concrete filesystem output** Forge would generate for the same definition sources as normal generation (`interactive` / `--preset` / `--config`).

```bash
forge new my-api --dry-run
forge new my-api --preset fastapi-postgres --dry-run
forge new my-api --config forge.yml --dry-run
```

| Concern | `forge plan` | `forge new --dry-run` |
|---------|--------------|------------------------|
| Question answered | What did Forge resolve? | What exactly would Forge create here? |
| Primary output | Resolved `GenerationPlan` summary | Destination + concrete relative file paths |
| Writes files | No | No |
| Destination rules | N/A (no destination) | Same conflict validation as real generation |

`--dry-run` is execution behavior only — it is **not** part of `ProjectDefinition`, YAML, presets, or `GenerationPlan`. Output discovery reuses the same template walk, `_shared` overlay, `_includes` exclusion, and `should_emit` gates as real generation. Suggested next steps are shown as informational and are not executed.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| non-zero | User cancellation, config error, validation failure, or generation failure |

Bare `forge` (help) exits with Typer’s standard “no command” code (`2`). There is no large exit-code taxonomy.

## Cancellation

Interactive prompts cancelled with Esc / Ctrl+C print a concise message and exit non-zero:

```text
Cancelled.
```

No Python traceback is shown for normal cancellation.

## Errors

CLI errors are concise and actionable. User/config/generation failures do **not** print Python tracebacks by default.

Examples:

```text
Error: configuration file not found: forge.yaml
```

```text
Error: destination already exists and is not empty: /path/to/my-api
```

```text
Error: unknown preset 'fastapi-prod'.
Available presets:
  fastapi-postgres
  fastapi-postgres-clean
  fastapi-mongo
  flask-postgres
  django-postgres
```

```text
Error: --preset and --config cannot be used together.
```

Domain and config exceptions are translated at the CLI boundary; validation rules are not duplicated just for formatting.

## Success output

After generation, Forge prints project name, location, optional preset title, a short stack summary from the resolved `GenerationPlan`, and next steps (from plan metadata — not hard-coded framework conditionals in the CLI).

## `forge plan`

Inspect the resolved `GenerationPlan` **without generating files**.

```text
--preset / --config
        ↓
ProjectDefinition
        ↓
resolve_plan()
        ↓
GenerationPlan  →  Rich summary (no writes)
```

```bash
forge plan --preset fastapi-postgres
forge plan --config forge.yaml
forge plan my-api --config forge.yaml
```

- Requires `--preset` or `--config` (not interactive in this release).
- `--preset` and `--config` cannot be combined.
- With `--preset` and no CLI name, the plan uses the display name `project` (nothing is written to disk).
- With `--config`, name precedence matches `forge new`.
- Framework-implied values (ORM, migration system, DRF, commands, dependencies) come from `GenerationPlan`, not from re-reading the definition in the CLI.
- Tooling includes testing, linting, Docker, and CI (provider label or `no`).
- When applicable, the summary also shows **Environment** (variable name + purpose), **Docker** dependency services, and **HTTP** liveness (`GET <health_path>`).
- When modules are selected, the summary includes a **Modules** section (and **Relationship** when Products and Categories are linked).
- File lists belong to `forge new --dry-run`, not `forge plan`.

## Presets

A **preset** is a named composition of valid **explicit user choices**. It is not a generator and does not own templates or resolution.

```text
--preset ID
    ↓
Preset catalog
    ↓
ProjectDefinition   (same model as interactive / config)
    ↓
resolve_plan()
    ↓
GenerationPlan → generator
```

Presets do **not** store resolved facts (`migration_system`, `rest_framework`, implied ORM, dependencies, commands). Those remain owned by `resolve_plan()`.

### Available presets

| ID | Stack |
|----|--------|
| `fastapi-auth` | FastAPI + Modular Monolith + Authentication + PostgreSQL + Alembic + Docker |
| `django-auth` | Django + Modular Monolith + Authentication + Authorization + PostgreSQL + Docker |
| `fastapi-postgres` | FastAPI + Modular Monolith + PostgreSQL + Alembic + Docker |
| `fastapi-postgres-clean` | FastAPI + Clean Architecture + PostgreSQL + Alembic + Docker |
| `fastapi-mongo` | FastAPI + Modular Monolith + MongoDB + Docker |
| `fastapi-catalog` | FastAPI + Modular Monolith + Products + Categories + PostgreSQL + Alembic + Docker |
| `fastapi-files` | FastAPI + Simple + Files (local storage) + SQLite + Alembic |
| `flask-postgres` | Flask + Modular Monolith + PostgreSQL + Alembic + Docker |
| `django-postgres` | Django + Modular Monolith + PostgreSQL + Docker (ORM / migrations / DRF implied) |

### Usage

```bash
forge new my-api --preset fastapi-postgres
forge new my-api -p django-postgres
```

- Project **name is required** on the CLI (`forge new <name> --preset …`). Presets do not own the project name.
- Generation is fully non-interactive.
- Unknown preset ids fail with a list of available presets.

### Input modes (mutually exclusive non-interactive sources)

| Mode | Command | Prompts? |
|------|---------|----------|
| Interactive | `forge new [NAME]` | Yes |
| Preset | `forge new NAME --preset ID` | No |
| Config | `forge new [NAME] --config FILE` | No |
| Dry-run | `forge new … --dry-run` | Same as the chosen mode above |
| Plan (preset) | `forge plan --preset ID` | No |
| Plan (config) | `forge plan [NAME] --config FILE` | No |

## Configuration-driven generation

`--config` skips interactive prompts. YAML expresses **explicit user choices** only; framework implications still come from `resolve_plan`.

```text
YAML → ForgeConfig → ProjectDefinition → resolve_plan() → GenerationPlan → project
```

Configuration mode must never open interactive prompts. Missing required fields fail with a clear error (important for CI). TTY detection is not used as a substitute for `--config`.

### Project name

1. CLI `NAME` argument wins when provided.
2. Otherwise `name` or `project.name` from the config is required.
3. Conflicting `name` and `project.name` in the same file is an error.

```bash
forge new my-api --config forge.yaml   # uses my-api
forge new --config forge.yaml          # uses name from YAML
```

### Schema

| Field | Required | Notes |
|-------|----------|-------|
| `name` or `project.name` | yes\* | \*unless CLI name is passed |
| `language` | no | default `python` |
| `type` | yes | e.g. `rest-api` |
| `framework` | yes | e.g. `fastapi`, `django`, `flask` |
| `architecture` | yes | `simple`, `modular-monolith`, `clean` |
| `modules` | no | list of module ids (`products`, `categories`, `files`, `background-jobs`, `email`, `webhooks`); omit or `[]` for none — see [modules.md](./modules.md) |
| `storage` | no | `{ backend: local\|s3, minio?: bool }` when `files` is selected |
| `persistence` | no | mapping with optional `sql` / `nosql` keys (see below) |
| `database` | no | **legacy SQL shorthand** — engine `postgresql` / `sqlite`, or `false`/`null` for none |
| `orm` | no | optional explicit override; usually omit |
| `migrations` | no | default `false` (Alembic for FastAPI/Flask when true; requires SQL) |
| `testing` | no | default `true` |
| `linting` | no | default `true` |
| `docker` | no | default `false` |
| `ci` | no | omit / null = none; only `github-actions` today — requires `testing` or `linting` |

Unknown fields are rejected. Do **not** put resolver-owned facts in the file (`migration_system`, `rest_framework`, Django ORM as a required choice, …).

Selecting `ci: github-actions` generates `.github/workflows/ci.yml` (GitHub Actions only). The workflow installs dependencies with `uv sync` and runs selected checks (`uv run ruff check .` and/or `uv run pytest -q`). No PostgreSQL/MongoDB/Redis service containers are added — generated tests stay service-independent. Existing presets leave CI disabled.

#### Persistence schema

```text
Persistence
├── SQL          (optional — at most one)
│   ├── postgresql
│   └── sqlite
└── NoSQL        (optional — at most one)
    ├── mongodb
    └── redis
```

Preferred form:

```yaml
persistence:
  sql: postgresql   # or sqlite, or omit
  nosql: redis      # or mongodb, or omit
```

SQL-only / NoSQL-only / none:

```yaml
persistence:
  sql: sqlite

persistence:
  nosql: mongodb

persistence: null
```

Legacy `database: postgresql` remains supported as an SQL-only shorthand. Combining `database` and `persistence` is allowed when they agree (e.g. `database: postgresql` + `persistence: {nosql: redis}`). Conflicting values are rejected with a clear error.

### Examples

FastAPI with Products + Categories:

```yaml
name: catalog-api
type: rest-api
framework: fastapi
architecture: modular-monolith
modules:
  - products
  - categories
persistence:
  sql: postgresql
migrations: true
testing: true
linting: true
docker: true
```

FastAPI with Authorization and both optional account-security flows:

```yaml
name: secure-api
type: rest-api
framework: fastapi
architecture: clean
modules:
  - authorization # implies authentication
authentication:
  registration: true
  email_verification: true # implies email
  password_reset: true     # implies email
persistence:
  sql: postgresql
migrations: true
testing: true
linting: true
docker: true
```

Unknown Authentication fields are rejected. Background Jobs is still an
independent module; when selected, security mail uses its existing RQ worker.

FastAPI with SQL + Redis:

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
ci: github-actions
```

FastAPI (legacy SQL shorthand still works):

```yaml
name: my-api
type: rest-api
framework: fastapi
architecture: modular-monolith
database: postgresql
orm: sqlalchemy
migrations: true
testing: true
linting: true
docker: true
```

Django (implied ORM / migrations / DRF — omit them; optional NoSQL):

```yaml
name: web
type: rest-api
framework: django
architecture: clean
persistence:
  sql: postgresql
  nosql: mongodb
testing: true
linting: true
docker: true
```

## Adaptive questioning

**Ask only questions that affect the generated project.**

(Interactive mode only — skipped when `--config` is used.)

- Framework options depend on language + project type (FastAPI, Django, Flask, …)
- Architecture for REST API: Simple, Modular Monolith, Clean Architecture
- **Project modules:** optional multi-select (Products, Categories, Files, Background Jobs, Email, Webhooks, Authentication, Authorization). See [modules.md](./modules.md)
- **Authentication:** announces its SQL requirement, requires Alembic on FastAPI/Flask, asks about registration, then offers optional Email verification and Password reset
- **Authorization:** announces that Authentication is implied; account-security email flows announce that Email is implied
- **FastAPI / Flask:** if modules requiring SQL are selected, ask for an SQL engine (no silent default); otherwise optional “Add a database?” → SQL / NoSQL / Both → engine prompts; Alembic only when SQL is selected; SQLAlchemy is implied for SQL (dim note); pymongo / redis clients noted for NoSQL
- **Django (REST API):** SQL engine required; optional “Also add a NoSQL database?”; Django ORM + Django migrations + DRF are implied (dim notes, not selectable choices)
- Docker / pytest / Ruff are explicit confirms for all three
- **CI:** after testing/linting, if either is Yes, ask “Add CI?” with GitHub Actions / No; skipped when both tooling options are No

Generated project READMEs document stack, setup (`uv sync`, `cp .env.example .env` when env vars exist), configuration table from resolved environment metadata, run/health (liveness only), migrations/tests/lint/Docker/CI when selected, and a short layout section.

Architecture questions are independent of framework. Framework implications are applied in `resolve_plan`, not by stuffing implied fields into `ProjectDefinition` during the interview.

## Interaction modes

| Mode | Status |
|------|--------|
| Interactive | **Implemented** |
| Configuration (`--config`) | **Implemented** (YAML) |
| Presets (`--preset`) | **Implemented** (small curated catalog) |
| Plan inspection (`forge plan`) | **Implemented** (non-interactive; `--preset` / `--config`) |
| Dry-run (`forge new --dry-run`) | **Implemented** (preview outputs; zero writes) |
