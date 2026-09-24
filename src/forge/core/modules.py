"""Official project modules — catalog, normalization, and dependency graph.

Modules are first-class, independently selectable domain/API packs (distinct
from ``Capabilities`` developer-workflow toggles). Catalog entries declare
requirements and human labels; resolution into generation contributions lives
in ``forge.generator.modules``.

Infrastructure backends (storage, RQ, SMTP, MinIO) are *not* modules — they
are resolved from module selection plus shallow options (e.g. ``storage``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModuleId(StrEnum):
    """Stable module identifiers used in YAML, CLI, and the resolver."""

    PRODUCTS = "products"
    CATEGORIES = "categories"
    FILES = "files"
    BACKGROUND_JOBS = "background-jobs"
    EMAIL = "email"
    WEBHOOKS = "webhooks"
    AUTHENTICATION = "authentication"


class StorageBackend(StrEnum):
    """Object/file storage backends for the Files module."""

    LOCAL = "local"
    S3 = "s3"


STORAGE_BACKEND_LABELS: dict[str, str] = {
    StorageBackend.LOCAL.value: "Local filesystem",
    StorageBackend.S3.value: "S3-compatible",
}


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    """Catalog entry for one selectable project module."""

    id: ModuleId
    label: str
    description: str
    requires_sql: bool = False
    # Other module ids that must be present when this module is selected.
    # Expansion is deterministic (catalog order); cycles are rejected.
    depends_on: tuple[ModuleId, ...] = ()


MODULE_SPECS: dict[ModuleId, ModuleSpec] = {
    ModuleId.PRODUCTS: ModuleSpec(
        id=ModuleId.PRODUCTS,
        label="Products",
        description="CRUD API for a generic product catalog entity.",
        requires_sql=True,
    ),
    ModuleId.CATEGORIES: ModuleSpec(
        id=ModuleId.CATEGORIES,
        label="Categories",
        description="CRUD API for grouping categories.",
        requires_sql=True,
    ),
    ModuleId.FILES: ModuleSpec(
        id=ModuleId.FILES,
        label="Files",
        description="File upload/download API with pluggable object storage.",
        requires_sql=True,
    ),
    ModuleId.BACKGROUND_JOBS: ModuleSpec(
        id=ModuleId.BACKGROUND_JOBS,
        label="Background Jobs",
        description="RQ worker processes backed by Redis.",
    ),
    ModuleId.EMAIL: ModuleSpec(
        id=ModuleId.EMAIL,
        label="Email",
        description="SMTP-backed transactional email service.",
    ),
    ModuleId.WEBHOOKS: ModuleSpec(
        id=ModuleId.WEBHOOKS,
        label="Webhooks",
        description="Outgoing webhook delivery via background jobs.",
        depends_on=(ModuleId.BACKGROUND_JOBS,),
    ),
    ModuleId.AUTHENTICATION: ModuleSpec(
        id=ModuleId.AUTHENTICATION,
        label="Authentication",
        description="Email/password identity with JWT access and rotating refresh sessions.",
        requires_sql=True,
    ),
}

MODULE_LABELS: dict[str, str] = {
    spec.id.value: spec.label for spec in MODULE_SPECS.values()
}

# Stable catalog order for interactive multi-select and plan display.
MODULE_ORDER: tuple[ModuleId, ...] = (
    ModuleId.PRODUCTS,
    ModuleId.CATEGORIES,
    ModuleId.FILES,
    ModuleId.BACKGROUND_JOBS,
    ModuleId.EMAIL,
    ModuleId.WEBHOOKS,
    ModuleId.AUTHENTICATION,
)

# Modules that share the CRUD foundation (pagination helpers / conftest).
_FOUNDATION_MODULES: frozenset[str] = frozenset(
    {
        ModuleId.PRODUCTS.value,
        ModuleId.CATEGORIES.value,
        ModuleId.FILES.value,
        ModuleId.AUTHENTICATION.value,
    }
)


def known_module_ids() -> frozenset[str]:
    return frozenset(spec.id.value for spec in MODULE_SPECS.values())


def known_storage_backends() -> frozenset[str]:
    return frozenset(b.value for b in StorageBackend)


def normalize_modules(raw: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Normalize module ids: lowercase, unique, catalog order.

    Does **not** expand dependencies — call ``expand_module_dependencies``
    during resolution. Raises ``TypeError`` for non-string ids and
    ``ValueError`` for unknown/empty ids. Empty / None → ``()``.
    """
    if not raw:
        return ()

    known = known_module_ids()
    seen: set[str] = set()
    selected: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise TypeError(f"module id must be a string, got {type(item).__name__}")
        cleaned = item.strip().lower()
        if not cleaned:
            raise ValueError("module id must not be empty")
        if cleaned not in known:
            allowed = ", ".join(sorted(known))
            raise ValueError(
                f"unknown module {cleaned!r}; expected one of: {allowed}"
            )
        if cleaned not in seen:
            seen.add(cleaned)
            selected.add(cleaned)

    return tuple(
        module_id.value
        for module_id in MODULE_ORDER
        if module_id.value in selected
    )


def expand_module_dependencies(
    module_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Expand module dependency edges and return catalog-ordered ids.

    Detects cycles defensively. Idempotent for already-complete selections.
    """
    if not module_ids:
        return ()

    selected: set[str] = set(module_ids)
    path: list[str] = []
    path_set: set[str] = set()
    done: set[str] = set()

    def visit(module_id: str) -> None:
        if module_id in done:
            return
        if module_id in path_set:
            cycle = " → ".join([*path, module_id])
            raise ValueError(f"module dependency cycle detected: {cycle}")
        if module_id not in MODULE_SPECS and module_id not in known_module_ids():
            raise ValueError(f"unknown module {module_id!r}")
        spec = MODULE_SPECS[ModuleId(module_id)]
        path.append(module_id)
        path_set.add(module_id)
        for dep in spec.depends_on:
            selected.add(dep.value)
            visit(dep.value)
        path_set.remove(module_id)
        path.pop()
        done.add(module_id)

    for mid in list(module_ids):
        visit(mid)

    return tuple(
        module_id.value
        for module_id in MODULE_ORDER
        if module_id.value in selected
    )


def implied_modules(
    selected: tuple[str, ...],
    expanded: tuple[str, ...],
) -> tuple[str, ...]:
    """Module ids present only because of dependency expansion."""
    selected_set = set(selected)
    return tuple(mid for mid in expanded if mid not in selected_set)


def modules_require_sql(module_ids: tuple[str, ...]) -> bool:
    """True when any selected (or expanded) module requires SQL persistence."""
    for module_id in expand_module_dependencies(module_ids):
        spec = MODULE_SPECS.get(ModuleId(module_id))
        if spec is not None and spec.requires_sql:
            return True
    return False


def modules_require_redis(module_ids: tuple[str, ...]) -> bool:
    """True when expanded modules need Redis (background jobs / webhooks)."""
    expanded = expand_module_dependencies(module_ids)
    return (
        ModuleId.BACKGROUND_JOBS.value in expanded
        or ModuleId.WEBHOOKS.value in expanded
    )


def modules_need_foundation(module_ids: tuple[str, ...]) -> bool:
    """True when CRUD foundation templates (pagination / conftest) apply."""
    expanded = set(expand_module_dependencies(module_ids))
    return bool(expanded & _FOUNDATION_MODULES)


def normalize_storage_backend(raw: str | None) -> str | None:
    """Normalize a storage backend id; ``None`` stays ``None``."""
    if raw is None:
        return None
    cleaned = raw.strip().lower()
    if cleaned not in known_storage_backends():
        allowed = ", ".join(sorted(known_storage_backends()))
        raise ValueError(
            f"unknown storage backend {cleaned!r}; expected one of: {allowed}"
        )
    return cleaned
