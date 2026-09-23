"""Official project modules — catalog and normalization.

Modules are first-class, independently selectable domain/API packs (distinct
from ``Capabilities`` developer-workflow toggles). Catalog entries declare
SQL requirements and human labels; resolution into generation contributions
lives in ``forge.generator.modules``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModuleId(StrEnum):
    """Stable module identifiers used in YAML, CLI, and the resolver."""

    PRODUCTS = "products"
    CATEGORIES = "categories"


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    """Catalog entry for one selectable project module."""

    id: ModuleId
    label: str
    description: str
    requires_sql: bool = True


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
}

MODULE_LABELS: dict[str, str] = {
    spec.id.value: spec.label for spec in MODULE_SPECS.values()
}

# Stable catalog order for interactive multi-select and plan display.
MODULE_ORDER: tuple[ModuleId, ...] = (
    ModuleId.PRODUCTS,
    ModuleId.CATEGORIES,
)


def known_module_ids() -> frozenset[str]:
    return frozenset(spec.id.value for spec in MODULE_SPECS.values())


def normalize_modules(raw: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Normalize module ids: lowercase, unique, catalog order.

    Raises ``ValueError`` for unknown ids. Empty / None → ``()``.
    """
    if not raw:
        return ()

    known = known_module_ids()
    seen: set[str] = set()
    selected: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise ValueError(f"module id must be a string, got {type(item).__name__}")
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


def modules_require_sql(module_ids: tuple[str, ...]) -> bool:
    """True when any selected module requires SQL persistence."""
    for module_id in module_ids:
        spec = MODULE_SPECS.get(ModuleId(module_id))
        if spec is not None and spec.requires_sql:
            return True
    return False
