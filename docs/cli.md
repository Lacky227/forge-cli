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
uv run forge new --config forge.yaml
uv run forge new my-api --config forge.yaml
```

| Command | Behavior |
|---------|----------|
| `forge` | Shows help (same as `forge --help`) and exits non-zero |
| `forge --version` / `-V` | Prints `forge <version>` from package metadata |
| `forge new [NAME]` | Interactive interview → generate `./<name>` |
| `forge new [NAME] --config FILE` | Load YAML config (no prompts) → generate |

No additional subcommands (`init`, `generate`, `doctor`, …) are part of the public surface. `new` is the generation command.

`--quiet`, `--verbose`, `--dry-run`, and `--force` are **intentionally deferred** — not part of the current contract.

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
Error: invalid Forge configuration
  architecture: Input should be 'simple', 'modular-monolith' or 'clean'
```

Domain and config exceptions are translated at the CLI boundary; validation rules are not duplicated just for formatting.

## Success output

After generation, Forge prints project name, location, a short stack summary from the resolved `GenerationPlan`, and next steps (from plan metadata — not hard-coded framework conditionals in the CLI).

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
| Presets | Planned |
| `--dry-run` | Intentionally deferred |
