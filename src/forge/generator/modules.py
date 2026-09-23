"""Resolved module contributions for the generator.

User-selected module ids on ``ProjectDefinition`` are resolved once into
structured contributions. Templates consume contribution lists; they do not
re-implement module dependency rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge.core.definition import ProjectDefinition
from forge.core.modules import MODULE_LABELS, MODULE_SPECS, ModuleId
from forge.core.types import ArchitectureStyle
from forge.generator.errors import GenerationError


@dataclass(frozen=True, slots=True)
class RouterContribution:
    """FastAPI router registration entry."""

    module_id: str
    import_module: str
    router_attr: str
    prefix: str
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BlueprintContribution:
    """Flask blueprint registration entry."""

    module_id: str
    import_module: str
    blueprint_attr: str
    name: str


@dataclass(frozen=True, slots=True)
class DjangoAppContribution:
    """Django app + URL include registration."""

    module_id: str
    app_config: str
    urls_module: str
    url_prefix: str


@dataclass(frozen=True, slots=True)
class ModelImportContribution:
    """Python import path ensuring ORM metadata sees module models."""

    module_id: str
    import_module: str
    symbol: str


@dataclass(frozen=True, slots=True)
class TemplateMount:
    """One template root mounted for module (or foundation) emission.

    ``source_subdir`` is relative to ``templates/<language>/``.
    Files keep their relative paths under that root (with ``__package__``
    substitution), matching base-tree discovery.
    """

    module_id: str
    source_subdir: Path


@dataclass(frozen=True, slots=True)
class ResolvedModule:
    """One selected module after resolution."""

    id: str
    label: str


@dataclass(frozen=True, slots=True)
class ModuleContributions:
    """Aggregated structured contributions from all selected modules."""

    modules: tuple[ResolvedModule, ...] = ()
    has_products: bool = False
    has_categories: bool = False
    products_link_categories: bool = False
    fastapi_routers: tuple[RouterContribution, ...] = ()
    flask_blueprints: tuple[BlueprintContribution, ...] = ()
    django_apps: tuple[DjangoAppContribution, ...] = ()
    model_imports: tuple[ModelImportContribution, ...] = ()
    template_mounts: tuple[TemplateMount, ...] = ()
    api_endpoints: tuple[tuple[str, str, str], ...] = ()
    # (method, path, summary) for README / plan consumers

    @property
    def enabled(self) -> bool:
        return bool(self.modules)


def resolve_module_contributions(
    definition: ProjectDefinition,
    *,
    package_name: str,
) -> ModuleContributions:
    """Build deterministic contributions for ``definition.modules``."""
    if not definition.modules:
        return ModuleContributions()

    if definition.capabilities.sql_database is None:
        raise GenerationError(
            "Cannot generate this project:\n\n"
            "Selected modules require an SQL database "
            "(postgresql or sqlite)."
        )

    framework = definition.framework
    architecture = definition.architecture
    selected = tuple(definition.modules)
    has_products = ModuleId.PRODUCTS.value in selected
    has_categories = ModuleId.CATEGORIES.value in selected
    link = has_products and has_categories

    resolved = tuple(
        ResolvedModule(id=mid, label=MODULE_LABELS.get(mid, mid))
        for mid in selected
    )

    mounts: list[TemplateMount] = [
        TemplateMount(
            module_id="_foundation",
            source_subdir=Path(
                "modules",
                "_foundation",
                framework,
                architecture.value,
            ),
        )
    ]

    fastapi_routers: list[RouterContribution] = []
    flask_blueprints: list[BlueprintContribution] = []
    django_apps: list[DjangoAppContribution] = []
    model_imports: list[ModelImportContribution] = []
    endpoints: list[tuple[str, str, str]] = []

    for mid in selected:
        if mid not in MODULE_SPECS:
            raise GenerationError(f"Unknown module {mid!r}")
        mounts.append(
            TemplateMount(
                module_id=mid,
                source_subdir=Path(
                    "modules",
                    mid,
                    framework,
                    architecture.value,
                ),
            )
        )
        _append_framework_contributions(
            mid,
            framework=framework,
            architecture=architecture,
            package_name=package_name,
            link=link,
            fastapi_routers=fastapi_routers,
            flask_blueprints=flask_blueprints,
            django_apps=django_apps,
            model_imports=model_imports,
            endpoints=endpoints,
        )

    return ModuleContributions(
        modules=resolved,
        has_products=has_products,
        has_categories=has_categories,
        products_link_categories=link,
        fastapi_routers=tuple(fastapi_routers),
        flask_blueprints=tuple(flask_blueprints),
        django_apps=tuple(django_apps),
        model_imports=tuple(model_imports),
        template_mounts=tuple(mounts),
        api_endpoints=tuple(endpoints),
    )


def _append_framework_contributions(
    module_id: str,
    *,
    framework: str,
    architecture: ArchitectureStyle,
    package_name: str,
    link: bool,
    fastapi_routers: list[RouterContribution],
    flask_blueprints: list[BlueprintContribution],
    django_apps: list[DjangoAppContribution],
    model_imports: list[ModelImportContribution],
    endpoints: list[tuple[str, str, str]],
) -> None:
    if framework == "fastapi":
        _fastapi_contributions(
            module_id,
            architecture=architecture,
            package_name=package_name,
            routers=fastapi_routers,
            model_imports=model_imports,
            endpoints=endpoints,
        )
    elif framework == "flask":
        _flask_contributions(
            module_id,
            architecture=architecture,
            package_name=package_name,
            blueprints=flask_blueprints,
            model_imports=model_imports,
            endpoints=endpoints,
        )
    elif framework == "django":
        _django_contributions(
            module_id,
            architecture=architecture,
            apps=django_apps,
            model_imports=model_imports,
            endpoints=endpoints,
        )
    else:
        raise GenerationError(
            f"Modules are not supported for framework {framework!r}"
        )
    # link reserved for schema/README flags via ModuleContributions
    _ = link


def _fastapi_contributions(
    module_id: str,
    *,
    architecture: ArchitectureStyle,
    package_name: str,
    routers: list[RouterContribution],
    model_imports: list[ModelImportContribution],
    endpoints: list[tuple[str, str, str]],
) -> None:
    prefix = f"/{module_id}"
    tag = module_id.capitalize()
    if architecture is ArchitectureStyle.SIMPLE:
        import_module = f"{package_name}.{module_id}"
        model_module = f"{package_name}.{module_id}_models"
        symbol = "Product" if module_id == "products" else "Category"
    elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
        import_module = f"{package_name}.api.routes.{module_id}"
        model_module = f"{package_name}.models.{module_id.rstrip('s')}"
        # products -> product, categories -> category
        singular = "product" if module_id == "products" else "category"
        model_module = f"{package_name}.models.{singular}"
        symbol = singular.capitalize()
    else:  # CLEAN
        import_module = f"{package_name}.presentation.{module_id}"
        singular = "product" if module_id == "products" else "category"
        model_module = (
            f"{package_name}.infrastructure.persistence.{singular}"
        )
        symbol = f"{singular.capitalize()}Model"

    routers.append(
        RouterContribution(
            module_id=module_id,
            import_module=import_module,
            router_attr="router",
            prefix=prefix,
            tags=(tag,),
        )
    )
    model_imports.append(
        ModelImportContribution(
            module_id=module_id,
            import_module=model_module,
            symbol=symbol,
        )
    )
    endpoints.extend(_crud_endpoints(prefix, tag, trailing_slash=False))


def _flask_contributions(
    module_id: str,
    *,
    architecture: ArchitectureStyle,
    package_name: str,
    blueprints: list[BlueprintContribution],
    model_imports: list[ModelImportContribution],
    endpoints: list[tuple[str, str, str]],
) -> None:
    singular = "product" if module_id == "products" else "category"
    if architecture is ArchitectureStyle.SIMPLE:
        import_module = f"{package_name}.{module_id}"
        model_module = f"{package_name}.{module_id}_models"
        symbol = singular.capitalize()
    elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
        import_module = f"{package_name}.api.routes.{module_id}"
        model_module = f"{package_name}.models.{singular}"
        symbol = singular.capitalize()
    else:
        import_module = f"{package_name}.presentation.{module_id}"
        model_module = (
            f"{package_name}.infrastructure.persistence.{singular}"
        )
        symbol = f"{singular.capitalize()}Model"

    blueprints.append(
        BlueprintContribution(
            module_id=module_id,
            import_module=import_module,
            blueprint_attr="bp",
            name=module_id,
        )
    )
    model_imports.append(
        ModelImportContribution(
            module_id=module_id,
            import_module=model_module,
            symbol=symbol,
        )
    )
    prefix = f"/api/{module_id}"
    endpoints.extend(
        _crud_endpoints(prefix, module_id.capitalize(), trailing_slash=False)
    )


def _django_contributions(
    module_id: str,
    *,
    architecture: ArchitectureStyle,
    apps: list[DjangoAppContribution],
    model_imports: list[ModelImportContribution],
    endpoints: list[tuple[str, str, str]],
) -> None:
    singular = "product" if module_id == "products" else "category"
    if architecture is ArchitectureStyle.SIMPLE:
        app_config = module_id
        urls_module = f"{module_id}.urls"
        model_module = f"{module_id}.models"
    elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
        app_config = f"apps.{module_id}"
        urls_module = f"apps.{module_id}.urls"
        model_module = f"apps.{module_id}.models"
    else:
        # Clean: ORM models stay in infrastructure.persistence (already
        # INSTALLED); HTTP routes live under presentation.api.
        app_config = ""
        urls_module = f"presentation.api.{module_id}_urls"
        model_module = f"infrastructure.persistence.{singular}"

    apps.append(
        DjangoAppContribution(
            module_id=module_id,
            app_config=app_config,
            urls_module=urls_module,
            url_prefix=f"{module_id}/",
        )
    )
    model_imports.append(
        ModelImportContribution(
            module_id=module_id,
            import_module=model_module,
            symbol=singular.capitalize(),
        )
    )
    endpoints.extend(
        _crud_endpoints(
            f"/api/{module_id}",
            module_id.capitalize(),
            trailing_slash=True,
        )
    )


def _crud_endpoints(
    prefix: str,
    label: str,
    *,
    trailing_slash: bool,
) -> list[tuple[str, str, str]]:
    slash = "/" if trailing_slash else ""
    collection = f"{prefix}{slash}"
    detail = f"{prefix}/{{id}}{slash}"
    return [
        ("POST", collection, f"Create {label}"),
        ("GET", collection, f"List {label}"),
        ("GET", detail, f"Retrieve {label}"),
        ("PATCH", detail, f"Update {label}"),
        ("DELETE", detail, f"Delete {label}"),
    ]


def contribution_jinja_dict(contributions: ModuleContributions) -> dict[str, object]:
    """Presentation context fragment for Jinja templates."""
    return {
        "modules": [
            {"id": m.id, "label": m.label} for m in contributions.modules
        ],
        "has_modules": contributions.enabled,
        "has_products": contributions.has_products,
        "has_categories": contributions.has_categories,
        "products_link_categories": contributions.products_link_categories,
        "fastapi_routers": [
            {
                "module_id": r.module_id,
                "import_module": r.import_module,
                "router_attr": r.router_attr,
                "prefix": r.prefix,
                "tags": list(r.tags),
            }
            for r in contributions.fastapi_routers
        ],
        "flask_blueprints": [
            {
                "module_id": b.module_id,
                "import_module": b.import_module,
                "blueprint_attr": b.blueprint_attr,
                "name": b.name,
            }
            for b in contributions.flask_blueprints
        ],
        "django_apps": [
            {
                "module_id": a.module_id,
                "app_config": a.app_config,
                "urls_module": a.urls_module,
                "url_prefix": a.url_prefix,
            }
            for a in contributions.django_apps
        ],
        "model_imports": [
            {
                "module_id": m.module_id,
                "import_module": m.import_module,
                "symbol": m.symbol,
            }
            for m in contributions.model_imports
        ],
        "api_endpoints": [
            {"method": method, "path": path, "summary": summary}
            for method, path, summary in contributions.api_endpoints
        ],
    }
