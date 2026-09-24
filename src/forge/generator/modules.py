"""Resolved module contributions for the generator.

User-selected module ids on ``ProjectDefinition`` are expanded (dependency
graph) and resolved once into structured contributions. Templates consume
contribution lists; they do not re-implement module dependency rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge.core.definition import ProjectDefinition
from forge.core.modules import (
    MODULE_LABELS,
    MODULE_SPECS,
    ModuleId,
    expand_module_dependencies,
    implied_modules,
    modules_need_foundation,
    modules_require_sql,
)
from forge.core.types import ArchitectureStyle
from forge.generator.errors import GenerationError

# Modules that expose HTTP routers/blueprints/Django URL includes.
_HTTP_API_MODULES: frozenset[str] = frozenset(
    {
        ModuleId.PRODUCTS.value,
        ModuleId.CATEGORIES.value,
        ModuleId.FILES.value,
        ModuleId.AUTHENTICATION.value,
    }
)

# Modules that register SQLAlchemy / Django ORM models via model_imports.
_MODEL_MODULES: frozenset[str] = frozenset(
    {
        ModuleId.PRODUCTS.value,
        ModuleId.CATEGORIES.value,
        ModuleId.FILES.value,
        ModuleId.AUTHENTICATION.value,
    }
)


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
    """One selected (or implied) module after resolution."""

    id: str
    label: str
    implied: bool = False


@dataclass(frozen=True, slots=True)
class ModuleContributions:
    """Aggregated structured contributions from all effective modules."""

    modules: tuple[ResolvedModule, ...] = ()
    selected_modules: tuple[str, ...] = ()
    implied_module_ids: tuple[str, ...] = ()
    has_products: bool = False
    has_categories: bool = False
    has_files: bool = False
    has_background_jobs: bool = False
    has_email: bool = False
    has_webhooks: bool = False
    has_authentication: bool = False
    authentication_registration: bool = False
    products_link_categories: bool = False
    fastapi_routers: tuple[RouterContribution, ...] = ()
    flask_blueprints: tuple[BlueprintContribution, ...] = ()
    django_apps: tuple[DjangoAppContribution, ...] = ()
    model_imports: tuple[ModelImportContribution, ...] = ()
    template_mounts: tuple[TemplateMount, ...] = ()
    api_endpoints: tuple[tuple[str, str, str], ...] = ()
    # Extra runtime dependency pins contributed by modules (deduped later).
    runtime_dependencies: tuple[str, ...] = ()
    # Env var specs contributed by modules (merged into the plan).
    environment_variables: tuple[tuple[str, str, str], ...] = ()
    # (name, example, purpose)

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

    try:
        expanded = expand_module_dependencies(definition.modules)
    except ValueError as exc:
        raise GenerationError(f"Cannot generate this project:\n\n{exc}") from exc

    implied = implied_modules(definition.modules, expanded)

    if modules_require_sql(expanded) and definition.capabilities.sql_database is None:
        raise GenerationError(
            "Cannot generate this project:\n\n"
            "Selected modules require an SQL database "
            "(postgresql or sqlite)."
        )

    if ModuleId.FILES.value in expanded and definition.storage is None:
        raise GenerationError(
            "Cannot generate this project:\n\n"
            "The files module requires storage options "
            "(backend: local or s3)."
        )

    framework = definition.framework
    architecture = definition.architecture
    has_products = ModuleId.PRODUCTS.value in expanded
    has_categories = ModuleId.CATEGORIES.value in expanded
    has_files = ModuleId.FILES.value in expanded
    has_jobs = ModuleId.BACKGROUND_JOBS.value in expanded
    has_email = ModuleId.EMAIL.value in expanded
    has_webhooks = ModuleId.WEBHOOKS.value in expanded
    has_authentication = ModuleId.AUTHENTICATION.value in expanded
    link = has_products and has_categories
    implied_set = set(implied)

    resolved = tuple(
        ResolvedModule(
            id=mid,
            label=MODULE_LABELS.get(mid, mid),
            implied=mid in implied_set,
        )
        for mid in expanded
    )

    mounts: list[TemplateMount] = []
    if modules_need_foundation(expanded):
        mounts.append(
            TemplateMount(
                module_id="_foundation",
                source_subdir=Path(
                    "modules",
                    "_foundation",
                    framework,
                    architecture.value,
                ),
            )
        )

    fastapi_routers: list[RouterContribution] = []
    flask_blueprints: list[BlueprintContribution] = []
    django_apps: list[DjangoAppContribution] = []
    model_imports: list[ModelImportContribution] = []
    endpoints: list[tuple[str, str, str]] = []
    runtime_deps: list[str] = []
    env_vars: list[tuple[str, str, str]] = []

    for mid in expanded:
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
        if mid in _HTTP_API_MODULES or mid in {
            ModuleId.BACKGROUND_JOBS.value,
            ModuleId.EMAIL.value,
            ModuleId.WEBHOOKS.value,
        }:
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

    _append_module_dependencies(
        expanded,
        definition=definition,
        runtime_deps=runtime_deps,
        env_vars=env_vars,
        package_name=package_name,
    )
    if has_authentication and not definition.authentication_options.registration:
        endpoints = [
            item for item in endpoints if not item[1].rstrip("/").endswith("/register")
        ]

    return ModuleContributions(
        modules=resolved,
        selected_modules=tuple(definition.modules),
        implied_module_ids=implied,
        has_products=has_products,
        has_categories=has_categories,
        has_files=has_files,
        has_background_jobs=has_jobs,
        has_email=has_email,
        has_webhooks=has_webhooks,
        has_authentication=has_authentication,
        authentication_registration=(
            definition.authentication_options.registration if has_authentication else False
        ),
        products_link_categories=link,
        fastapi_routers=tuple(fastapi_routers),
        flask_blueprints=tuple(flask_blueprints),
        django_apps=tuple(django_apps),
        model_imports=tuple(model_imports),
        template_mounts=tuple(mounts),
        api_endpoints=tuple(endpoints),
        runtime_dependencies=tuple(runtime_deps),
        environment_variables=tuple(env_vars),
    )


def _append_module_dependencies(
    expanded: tuple[str, ...],
    *,
    definition: ProjectDefinition,
    runtime_deps: list[str],
    env_vars: list[tuple[str, str, str]],
    package_name: str,
) -> None:
    """Module-owned deps and env metadata (merged centrally by resolve_plan)."""
    storage = definition.storage
    if ModuleId.FILES.value in expanded:
        env_vars.append(
            (
                "UPLOAD_MAX_BYTES",
                "10485760",
                "Maximum upload size in bytes (default 10 MiB)",
            )
        )
        if storage is not None and storage.backend == "local":
            env_vars.append(
                (
                    "STORAGE_LOCAL_ROOT",
                    "./var/storage",
                    "Local filesystem root for uploaded objects",
                )
            )
        if storage is not None and storage.backend == "s3":
            runtime_deps.append("boto3>=1.35")
            s3_endpoint_example = (
                "http://localhost:9000"
                if storage.minio and definition.capabilities.docker
                else ""
            )
            env_vars.extend(
                [
                    (
                        "S3_ENDPOINT_URL",
                        s3_endpoint_example,
                        "S3-compatible endpoint URL (empty for AWS default)",
                    ),
                    (
                        "S3_ACCESS_KEY",
                        "minioadmin" if storage.minio else "changeme",
                        "S3 access key id",
                    ),
                    (
                        "S3_SECRET_KEY",
                        "minioadmin" if storage.minio else "changeme",
                        "S3 secret access key",
                    ),
                    (
                        "S3_BUCKET",
                        f"{package_name}-files",
                        "S3 bucket name for uploaded objects",
                    ),
                    (
                        "S3_REGION",
                        "us-east-1",
                        "S3 region (required by some clients)",
                    ),
                    (
                        "S3_CREATE_BUCKET",
                        "false",
                        "Create the S3 bucket on startup if missing (opt-in)",
                    ),
                ]
            )
            if storage.minio and definition.capabilities.docker:
                env_vars.extend(
                    [
                        (
                            "MINIO_ROOT_USER",
                            "minioadmin",
                            "MinIO root user (local development)",
                        ),
                        (
                            "MINIO_ROOT_PASSWORD",
                            "minioadmin",
                            "MinIO root password (local development)",
                        ),
                    ]
                )

    if ModuleId.BACKGROUND_JOBS.value in expanded:
        runtime_deps.append("rq>=2.0")
        # redis package is added by resolve_plan when Redis is required

    if ModuleId.AUTHENTICATION.value in expanded:
        runtime_deps.append("PyJWT>=2.10")
        if definition.framework in {"fastapi", "flask"}:
            runtime_deps.extend(["pwdlib[argon2]>=0.3", "email-validator>=2.2"])
        else:
            runtime_deps.append("argon2-cffi>=23.1")
        env_vars.extend(
            [
                ("APP_ENV", "development", "Runtime environment (production enables secret checks)"),
                ("AUTH_JWT_SECRET", "", "JWT signing secret (generated locally; required in production)"),
                ("AUTH_ISSUER", package_name, "Expected JWT issuer"),
                ("AUTH_AUDIENCE", f"{package_name}-api", "Expected JWT audience"),
                ("AUTH_ACCESS_TOKEN_TTL_SECONDS", "900", "Access-token lifetime in seconds"),
                ("AUTH_REFRESH_TOKEN_TTL_DAYS", "30", "Absolute refresh-family lifetime in days"),
            ]
        )

    if ModuleId.EMAIL.value in expanded:
        env_vars.extend(
            [
                ("SMTP_HOST", "localhost", "SMTP server hostname"),
                ("SMTP_PORT", "587", "SMTP server port"),
                ("SMTP_USERNAME", "", "SMTP username (optional)"),
                ("SMTP_PASSWORD", "", "SMTP password (optional)"),
                ("SMTP_USE_TLS", "true", "Use STARTTLS for SMTP"),
                (
                    "EMAIL_FROM",
                    f"noreply@{package_name}.local",
                    "Default From address for outbound email",
                ),
            ]
        )

    if ModuleId.WEBHOOKS.value in expanded:
        runtime_deps.append("httpx>=0.27")
        env_vars.extend(
            [
                (
                    "WEBHOOK_URL",
                    "https://example.com/hooks/forge",
                    "Configured outgoing webhook target URL",
                ),
                (
                    "WEBHOOK_TIMEOUT_SECONDS",
                    "10",
                    "HTTP timeout for webhook delivery",
                ),
                (
                    "WEBHOOK_MAX_RETRIES",
                    "3",
                    "Maximum delivery attempts (bounded)",
                ),
            ]
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
    _ = link


def _singular(module_id: str) -> str:
    mapping = {
        "products": "product",
        "categories": "category",
        "files": "file",
        "background-jobs": "jobs",
        "email": "email",
        "webhooks": "webhook",
        "authentication": "authentication",
    }
    return mapping.get(module_id, module_id.rstrip("s"))


def _fastapi_contributions(
    module_id: str,
    *,
    architecture: ArchitectureStyle,
    package_name: str,
    routers: list[RouterContribution],
    model_imports: list[ModelImportContribution],
    endpoints: list[tuple[str, str, str]],
) -> None:
    if module_id not in _HTTP_API_MODULES:
        # Jobs / email / webhooks contribute services + tests via mounts only.
        return

    prefix = f"/{module_id}"
    tag = MODULE_LABELS.get(module_id, module_id.capitalize())
    singular = _singular(module_id)

    if module_id == ModuleId.AUTHENTICATION.value:
        prefix = "/auth"
        if architecture is ArchitectureStyle.SIMPLE:
            import_module = f"{package_name}.auth"
            model_module = f"{package_name}.auth_models"
            symbol = "User"
        elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
            import_module = f"{package_name}.api.routes.auth"
            model_module = f"{package_name}.models.authentication"
            symbol = "User"
        else:
            import_module = f"{package_name}.presentation.auth"
            model_module = f"{package_name}.infrastructure.persistence.authentication"
            symbol = "UserModel"
        routers.append(
            RouterContribution(module_id=module_id, import_module=import_module, router_attr="router", prefix=prefix, tags=(tag,))
        )
        model_imports.append(
            ModelImportContribution(module_id=module_id, import_module=model_module, symbol=symbol)
        )
        endpoints.extend(_authentication_endpoints(prefix, registration=True, trailing_slash=False))
        return

    if architecture is ArchitectureStyle.SIMPLE:
        import_module = f"{package_name}.{module_id.replace('-', '_')}"
        if module_id == ModuleId.FILES.value:
            import_module = f"{package_name}.files"
        model_module = f"{package_name}.{module_id.replace('-', '_')}_models"
        if module_id == ModuleId.FILES.value:
            model_module = f"{package_name}.files_models"
        symbol = singular.capitalize()
    elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
        import_module = f"{package_name}.api.routes.{module_id.replace('-', '_')}"
        if module_id == ModuleId.FILES.value:
            import_module = f"{package_name}.api.routes.files"
        model_module = f"{package_name}.models.{singular}"
        symbol = singular.capitalize()
    else:  # CLEAN
        import_module = f"{package_name}.presentation.{module_id.replace('-', '_')}"
        if module_id == ModuleId.FILES.value:
            import_module = f"{package_name}.presentation.files"
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
    if module_id in _MODEL_MODULES:
        model_imports.append(
            ModelImportContribution(
                module_id=module_id,
                import_module=model_module,
                symbol=symbol,
            )
        )
    if module_id == ModuleId.FILES.value:
        endpoints.extend(_files_endpoints(prefix, trailing_slash=False))
    else:
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
    if module_id not in _HTTP_API_MODULES:
        return

    singular = _singular(module_id)
    py_id = module_id.replace("-", "_")
    if module_id == ModuleId.AUTHENTICATION.value:
        if architecture is ArchitectureStyle.SIMPLE:
            import_module = f"{package_name}.auth"
            model_module = f"{package_name}.auth_models"
            symbol = "User"
        elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
            import_module = f"{package_name}.api.routes.auth"
            model_module = f"{package_name}.models.authentication"
            symbol = "User"
        else:
            import_module = f"{package_name}.presentation.auth"
            model_module = f"{package_name}.infrastructure.persistence.authentication"
            symbol = "UserModel"
        blueprints.append(BlueprintContribution(module_id=module_id, import_module=import_module, blueprint_attr="bp", name="auth"))
        model_imports.append(ModelImportContribution(module_id=module_id, import_module=model_module, symbol=symbol))
        endpoints.extend(_authentication_endpoints("/api/auth", registration=True, trailing_slash=False))
        return
    if architecture is ArchitectureStyle.SIMPLE:
        import_module = f"{package_name}.{py_id}"
        model_module = f"{package_name}.{py_id}_models"
        symbol = singular.capitalize()
    elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
        import_module = f"{package_name}.api.routes.{py_id}"
        model_module = f"{package_name}.models.{singular}"
        symbol = singular.capitalize()
    else:
        import_module = f"{package_name}.presentation.{py_id}"
        model_module = (
            f"{package_name}.infrastructure.persistence.{singular}"
        )
        symbol = f"{singular.capitalize()}Model"

    blueprints.append(
        BlueprintContribution(
            module_id=module_id,
            import_module=import_module,
            blueprint_attr="bp",
            name=py_id,
        )
    )
    if module_id in _MODEL_MODULES:
        model_imports.append(
            ModelImportContribution(
                module_id=module_id,
                import_module=model_module,
                symbol=symbol,
            )
        )
    prefix = f"/api/{module_id}" if module_id != "files" else "/api/files"
    label = MODULE_LABELS.get(module_id, module_id.capitalize())
    if module_id == ModuleId.FILES.value:
        endpoints.extend(_files_endpoints(prefix, trailing_slash=False))
    else:
        endpoints.extend(_crud_endpoints(prefix, label, trailing_slash=False))


def _django_contributions(
    module_id: str,
    *,
    architecture: ArchitectureStyle,
    apps: list[DjangoAppContribution],
    model_imports: list[ModelImportContribution],
    endpoints: list[tuple[str, str, str]],
) -> None:
    if module_id == ModuleId.BACKGROUND_JOBS.value:
        # RQ helpers and run_worker live on the primary Django app
        # (core / apps.core / infrastructure.persistence) — no extra app package.
        return

    if module_id not in _HTTP_API_MODULES:
        return

    singular = _singular(module_id)
    py_id = module_id.replace("-", "_")
    url_prefix = f"{py_id}/"

    if module_id == ModuleId.AUTHENTICATION.value:
        if architecture is ArchitectureStyle.SIMPLE:
            app_config = "identity"
            urls_module = "identity.urls"
            model_module = "identity.models"
        elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
            app_config = "apps.identity"
            urls_module = "apps.identity.urls"
            model_module = "apps.identity.models"
        else:
            app_config = ""
            urls_module = "presentation.api.auth_urls"
            model_module = "infrastructure.persistence.authentication"
        apps.append(DjangoAppContribution(module_id=module_id, app_config=app_config, urls_module=urls_module, url_prefix="auth/"))
        model_imports.append(ModelImportContribution(module_id=module_id, import_module=model_module, symbol="User"))
        endpoints.extend(_authentication_endpoints("/api/auth", registration=True, trailing_slash=True))
        return

    if architecture is ArchitectureStyle.SIMPLE:
        app_config = py_id
        urls_module = f"{py_id}.urls"
        model_module = f"{py_id}.models"
    elif architecture is ArchitectureStyle.MODULAR_MONOLITH:
        app_config = f"apps.{py_id}"
        urls_module = f"apps.{py_id}.urls"
        model_module = f"apps.{py_id}.models"
    else:
        app_config = ""
        urls_module = f"presentation.api.{py_id}_urls"
        model_module = f"infrastructure.persistence.{singular}"

    apps.append(
        DjangoAppContribution(
            module_id=module_id,
            app_config=app_config,
            urls_module=urls_module,
            url_prefix=url_prefix,
        )
    )
    if module_id in _MODEL_MODULES:
        model_imports.append(
            ModelImportContribution(
                module_id=module_id,
                import_module=model_module,
                symbol=singular.capitalize(),
            )
        )
    label = MODULE_LABELS.get(module_id, module_id.capitalize())
    prefix = f"/api/{py_id}"
    if module_id == ModuleId.FILES.value:
        endpoints.extend(_files_endpoints(prefix, trailing_slash=True))
    else:
        endpoints.extend(
            _crud_endpoints(prefix, label, trailing_slash=True)
        )


def _files_endpoints(
    prefix: str,
    *,
    trailing_slash: bool,
) -> list[tuple[str, str, str]]:
    slash = "/" if trailing_slash else ""
    collection = f"{prefix}{slash}"
    detail = f"{prefix}/{{id}}{slash}"
    download = f"{prefix}/{{id}}/content{slash}"
    return [
        ("POST", collection, "Upload file"),
        ("GET", collection, "List files"),
        ("GET", detail, "Retrieve file metadata"),
        ("GET", download, "Download file content"),
        ("DELETE", detail, "Delete file"),
    ]


def _authentication_endpoints(
    prefix: str, *, registration: bool, trailing_slash: bool
) -> list[tuple[str, str, str]]:
    slash = "/" if trailing_slash else ""
    rows: list[tuple[str, str, str]] = []
    if registration:
        rows.append(("POST", f"{prefix}/register{slash}", "Register identity"))
    rows.extend(
        [
            ("POST", f"{prefix}/login{slash}", "Authenticate"),
            ("POST", f"{prefix}/refresh{slash}", "Rotate refresh session"),
            ("POST", f"{prefix}/logout{slash}", "Revoke refresh session"),
            ("POST", f"{prefix}/logout-all{slash}", "Revoke all sessions"),
            ("GET", f"{prefix}/me{slash}", "Current identity"),
            ("POST", f"{prefix}/password/change{slash}", "Change password"),
        ]
    )
    return rows


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
            {
                "id": m.id,
                "label": m.label,
                "implied": m.implied,
            }
            for m in contributions.modules
        ],
        "has_modules": contributions.enabled,
        "has_products": contributions.has_products,
        "has_categories": contributions.has_categories,
        "has_files": contributions.has_files,
        "has_background_jobs": contributions.has_background_jobs,
        "has_email": contributions.has_email,
        "has_webhooks": contributions.has_webhooks,
        "has_authentication": contributions.has_authentication,
        "authentication_registration": contributions.authentication_registration,
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
