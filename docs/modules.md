# Project modules

Forge can generate **project modules** — selectable domain/API packs that add
real CRUD functionality to a generated REST API.

Modules are distinct from developer-workflow **capabilities** (Docker, testing,
linting, CI) and from persistence engines. See [architecture.md](./architecture.md)
for how modules resolve into structured contributions.

## Current modules (Stage 1)

| Module | Id | Requires SQL | Description |
|--------|-----|--------------|-------------|
| Products | `products` | yes | Generic product CRUD API |
| Categories | `categories` | yes | Generic category CRUD API |

Modules are independently selectable:

```text
none | products | categories | products + categories
```

When **both** Products and Categories are selected, Forge generates a
many-to-one relationship: each product may optionally reference a category.

Authentication, users, and security modules are reserved for Forge **0.5**.

## User intent

```yaml
modules:
  - products
  - categories
```

- Omitted `modules` or `modules: []` → no modules (0.3 scaffold shape)
- Unknown ids are rejected
- Duplicates are removed; order is normalized to the catalog order
- SQL-requiring modules without SQL fail validation (YAML/config) or prompt
  for an SQL engine interactively (FastAPI/Flask)

## Interactive flow

After architecture selection, Forge shows a multi-select checklist for
modules. Persistence questions adapt:

- **Django** — SQL remains required as before; modules do not change that
- **FastAPI / Flask** — if modules requiring SQL are selected, Forge asks for
  an SQL engine (it does **not** silently pick PostgreSQL or SQLite)

## Generated API (conceptual)

```text
POST   /products          GET /products
GET    /products/{id}     PATCH /products/{id}     DELETE /products/{id}

POST   /categories        GET /categories
GET    /categories/{id}   PATCH /categories/{id}   DELETE /categories/{id}
```

Django uses trailing slashes (`/api/products/`). FastAPI prefixes are
`/products` and `/categories`. Flask uses `/api/products` and `/api/categories`.

### Collection behavior

Bundled with CRUD modules (not a separate Forge checkbox):

| Concern | Contract |
|---------|----------|
| Pagination | `page` (default 1), `page_size` (default 20, max 100) |
| Envelope | `{ "items", "page", "page_size", "total" }` (DRF uses its pagination shape) |
| Filtering | Products: `q`, `is_active`, `min_price`, `max_price`, `category_id` (when linked); Categories: `q` |
| Sorting | Allow-listed `ordering` fields only |

### Domain fields

**Product:** `id`, `name`, `description`, `price` (precise decimal), `is_active`,
timestamps; optional `category_id` when both modules selected.

**Category:** `id`, `name`, `slug` (unique; derived from name when omitted),
`description`, timestamps.

## Architecture-aware layout

| Style | Shape |
|-------|--------|
| Simple | Compact route/schema/model modules beside the existing package |
| Modular Monolith | Feature packages / Django apps with routes, schemas, services, repositories |
| Clean | Domain + application use cases + infrastructure adapters + presentation |

## Composition model

```text
ProjectDefinition.modules
        ↓
resolve_module_contributions()
        ↓
ModuleContributions (routers, apps, model imports, template mounts, …)
        ↓
base templates loop contributions + module template mounts emit files
```

Module templates live under `templates/python/modules/` (not nine full copies
inside each framework×architecture scaffold). Base trees only gain contribution
loops. `planned_outputs` discovers module mounts with the same gates as real
generation (dry-run parity).

## `forge plan`

When modules are selected, the plan includes a **Modules** section (and a
**Relationship** row when Products and Categories are linked).

## Testing

Generated projects include CRUD tests (create/list/retrieve/update/delete,
validation, pagination, filtering, and the linked relationship when both
modules are selected).
