# Project modules

Forge can generate **project modules** — selectable packs that add real
application capabilities to a generated REST API.

Modules are distinct from developer-workflow **capabilities** (Docker, testing,
linting, CI) and from persistence engines. Supporting infrastructure (storage
backends, RQ, Redis, SMTP, MinIO) is *resolved* from module selection — it is
not a parallel catalog of user-facing modules. See
[architecture.md](./architecture.md) for how modules resolve into structured
contributions.

## Current modules

| Module | Id | Requires SQL | Notes |
|--------|-----|--------------|-------|
| Products | `products` | yes | Generic product CRUD API |
| Categories | `categories` | yes | Generic category CRUD API |
| Files | `files` | yes | Upload/download API + object storage |
| Background Jobs | `background-jobs` | no | RQ workers (implies Redis) |
| Email | `email` | no | SMTP email service |
| Webhooks | `webhooks` | no | Outgoing delivery via Background Jobs |

Modules are independently multi-selectable. Selecting **Webhooks** expands to
include **Background Jobs** (and therefore Redis). When **both** Products and
Categories are selected, Forge generates a many-to-one relationship.

Authentication, users, and security modules are reserved for a later release
(not part of 0.4).

**Django Clean note:** Django Clean module packs wire presentation (DRF) and ORM
models in `infrastructure.persistence`; they do **not** add full
domain/application ports the way FastAPI/Flask Clean modules do.

## User intent vs infrastructure

```text
User-facing modules          Resolved infrastructure
─────────────────────        ─────────────────────────
files                   →    storage (local | s3)
                             optional MinIO (s3 + docker)
background-jobs         →    RQ + Redis
webhooks                →    background-jobs → RQ + Redis
email                   →    SMTP configuration
```

Redis may already be selected as NoSQL persistence. Background Jobs **reuse**
that Redis (`REDIS_URL`) rather than inventing a second broker URL. When Redis
was not selected as NoSQL, Forge adds it as required infrastructure and
surfaces that in `forge plan` / interactive output — it does **not** pretend
the user chose Redis as application NoSQL.

## Configuration

```yaml
modules:
  - products
  - categories
  - files
  - background-jobs
  - email
  - webhooks

storage:
  backend: s3          # local | s3 (required shape when files is selected)
  minio: true          # only with backend: s3 and docker: true
```

A smaller catalog-only selection is also valid:

```yaml
modules:
  - products
  - categories
```

- Omitted `modules` or `modules: []` → no modules (scaffold-only, as in 0.3)
- Unknown ids / backends are rejected
- Duplicates are removed; order is normalized to the catalog order
- SQL-requiring modules without SQL fail validation (YAML) or prompt
  interactively (FastAPI/Flask)
- `storage` without `files` is rejected; `minio` without `s3` or without
  Docker is rejected

## Interactive flow

After architecture selection, Forge shows a multi-select checklist for all
modules. Follow-ups are adaptive:

- **Files** → storage backend (local / S3-compatible); if S3 + Docker → MinIO?
- **Webhooks** → announces implied Background Jobs
- **Background Jobs / Webhooks** → announces Redis (reuse NoSQL or required infra)
- **Django** — SQL remains required as before
- **FastAPI / Flask** — if modules requiring SQL are selected, Forge asks for
  an SQL engine (it does **not** silently pick one)

## Files

### Metadata decision

File **bytes** live in object storage. **Metadata** (id, filename, content_type,
size, storage_key, created_at) is persisted in SQL so listing and id-based
APIs stay consistent across local and S3 backends. Therefore Files requires
SQL. The API never exposes filesystem paths — only opaque `storage_key` values.

### API (conceptual)

```text
POST   /files
GET    /files
GET    /files/{id}
GET    /files/{id}/content
DELETE /files/{id}
```

### Validation

Empty uploads, maximum size (`UPLOAD_MAX_BYTES`, default 10 MiB), unsafe
filenames / path traversal, and uuid-based storage keys. MIME headers are not
treated as strong content security.

### Storage

| Backend | Behavior |
|---------|----------|
| `local` | Files under `STORAGE_LOCAL_ROOT` (default `./var/storage`); gitignored |
| `s3` | Generic S3-compatible client (`boto3`) via `S3_ENDPOINT_URL` (empty = AWS default endpoint), keys, bucket, region |

Bucket auto-creation is **off** by default (`S3_CREATE_BUCKET=false`). Enable
explicitly when you want startup to create a missing bucket.

### MinIO

When Files + S3 + Docker + `minio: true`, Compose includes a MinIO service and
wires `S3_ENDPOINT_URL` to it. MinIO is optional — external S3 endpoints work
without it.

## Background Jobs

Single implementation in 0.4: **RQ** on Redis.

Generated artifacts include queue helpers, an example deterministic task
(`ping` / `enqueue_ping`), a worker process, tests (mocked Redis/RQ), and README/worker
commands. The resolved plan exposes processes:

```text
Processes
  API
  Worker
```

With Docker, Compose adds a `worker` service using the same image and the
resolved worker command.

## Email

SMTP via stdlib `smtplib`. Configuration: `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `EMAIL_FROM`.

Forge generates an `EmailService` exercised by tests with a fake SMTP client.
There is **no** public arbitrary-send HTTP endpoint.

## Webhooks (outgoing only)

Outgoing delivery only — no inbound framework, signatures, or subscription UI.

Delivery POSTs JSON to configured `WEBHOOK_URL` through RQ with timeout and a
**bounded** retry count (`WEBHOOK_MAX_RETRIES`). There is **no** public
open-proxy endpoint that accepts arbitrary target URLs.

## Composition model

```text
ProjectDefinition.modules (+ storage options)
        ↓
expand_module_dependencies()   # e.g. webhooks → background-jobs
        ↓
resolve_module_contributions()
        ↓
ModuleContributions + GenerationFeatures
  (routers, apps, mounts, deps, env, docker, processes)
        ↓
base templates + module mounts
```

Module templates live under `templates/python/modules/`. Dependency edges,
env vars, Docker services, and processes are plan-owned — templates do not
re-derive the infrastructure graph.

## `forge plan`

Selected modules appear under **Modules** (implied ones marked). Additional
sections when applicable: Storage, Background Jobs, Email, Webhooks,
Processes, Infrastructure (Redis when implied), Docker services.

## Testing

Generated projects include module tests that do **not** require live
PostgreSQL, Redis, MinIO, SMTP, or network access for the default unit suite
(mocks/fakes/tmp paths).
