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
| `forge plan --preset ID` | Resolve and display `GenerationPlan` (no filesystem writes) |
| `forge plan [NAME] --config FILE` | Same for YAML; name precedence matches `forge new` |

`new` generates projects. `plan` only inspects the resolved plan. Do not add unrelated subcommands.

`--quiet`, `--verbose`, `--dry-run`, and `--force` are **intentionally deferred** — not part of the current contract.

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
| Does not exist | Created |
| Empty directory | Allowed (project files are written into it) |
| Non-empty directory | Error — no overwrite |
| Existing file at that path | Error |

Forge never merges into an existing project and does not offer `--force`.

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
| `fastapi-postgres` | FastAPI + Modular Monolith + PostgreSQL + Alembic + Docker |
| `fastapi-postgres-clean` | FastAPI + Clean Architecture + PostgreSQL + Alembic + Docker |
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
| `database` | no | engine `postgresql` / `sqlite`, or `false`/`null` for none |
| `orm` | no | optional explicit override; usually omit |
| `migrations` | no | default `false` (Alembic for FastAPI/Flask when true) |
| `testing` | no | default `true` |
| `linting` | no | default `true` |
| `docker` | no | default `false` |

Unknown fields are rejected. Do **not** put resolver-owned facts in the file (`migration_system`, `rest_framework`, Django ORM as a required choice, …).

### Examples

FastAPI:

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

Django (implied ORM / migrations / DRF — omit them):

```yaml
name: web
type: rest-api
framework: django
architecture: clean
database: postgresql
testing: true
linting: true
docker: true
```

## Adaptive questioning

**Ask only questions that affect the generated project.**

(Interactive mode only — skipped when `--config` is used.)

- Framework options depend on language + project type (FastAPI, Django, Flask, …)
- Architecture for REST API: Simple, Modular Monolith, Clean Architecture
- **FastAPI:** optional database → engine → Alembic confirm; SQLAlchemy is implied (dim note)
- **Flask:** optional database → engine → Alembic confirm; SQLAlchemy is implied when a DB is selected (dim note). No Django-style forced infrastructure.
- **Django (REST API):** database engine only; Django ORM + Django migrations + DRF are implied (dim notes, not selectable choices)
- Docker / pytest / Ruff are explicit confirms for all three

Architecture questions are independent of framework. Framework implications are applied in `resolve_plan`, not by stuffing implied fields into `ProjectDefinition` during the interview.

## Interaction modes

| Mode | Status |
|------|--------|
| Interactive | **Implemented** |
| Configuration (`--config`) | **Implemented** (YAML) |
| Presets (`--preset`) | **Implemented** (small curated catalog) |
| Plan inspection (`forge plan`) | **Implemented** (non-interactive; `--preset` / `--config`) |
| `--dry-run` | Intentionally deferred |
