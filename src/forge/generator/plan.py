"""Resolved generation information derived from a ProjectDefinition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge.core import catalog
from forge.core.definition import ProjectDefinition
from forge.core.modules import STORAGE_BACKEND_LABELS
from forge.generator.modules import ModuleContributions, contribution_jinja_dict


@dataclass(frozen=True)
class EnvVarSpec:
    """One environment variable the generated project expects.

    Built by ``resolve_plan`` from the selected stack. Future template /
    README emission should consume this list rather than re-deriving names.
    """

    name: str
    example: str
    purpose: str


@dataclass(frozen=True, slots=True)
class GeneratedSecretSpec:
    """A sensitive value created only during real project generation."""

    environment_variable: str
    entropy_bytes: int = 32
    target_file: str = ".env"


@dataclass(frozen=True, slots=True)
class ProcessSpec:
    """One runtime process the generated project is expected to run."""

    id: str
    label: str
    command: str


@dataclass(frozen=True)
class GenerationFeatures:
    """Resolved implementation implications of a ProjectDefinition.

    Includes both explicit user choices (docker, testing, …) and
    framework-implied facts (orm, migration_system, rest_framework, nosql client).
    """

    # SQL persistence (independent of NoSQL)
    database: bool  # True when SQL is selected (template-friendly name)
    postgresql: bool
    sqlite: bool
    # NoSQL / infrastructure clients (independent of SQL)
    mongodb: bool
    redis: bool  # True when Redis is needed (NoSQL selection and/or jobs)
    redis_nosql: bool  # True when the user selected Redis as NoSQL persistence
    nosql: bool
    migrations: bool
    docker: bool
    testing: bool
    linting: bool
    # Optional CI provider id (e.g. "github-actions"); None = no CI.
    ci_provider: str | None = None
    # Framework-implied / resolved implementation details
    orm: str | None = None
    migration_system: str | None = None  # "alembic" | "django" | None
    nosql_client: str | None = None  # "pymongo" | "redis" | None
    # REST API stacks may enable a framework-native API layer (e.g. DRF).
    rest_framework: bool = False
    # Stage 2 infrastructure (resolved from modules + options)
    storage_backend: str | None = None  # "local" | "s3" | None
    minio: bool = False
    background_jobs: bool = False
    email: bool = False
    webhooks: bool = False
    rq: bool = False
    authentication: bool = False
    authorization: bool = False
    registration: bool = False
    email_verification: bool = False
    password_reset: bool = False

    @property
    def ci(self) -> bool:
        """True when a CI provider was selected."""
        return self.ci_provider is not None

    @property
    def env_example(self) -> bool:
        """True when SQL, NoSQL, or Docker is selected.

        Prefer ``bool(GenerationPlan.environment_variables)`` for whether an
        ``.env.example`` file should be emitted — Docker alone may have no vars.
        """
        return self.database or self.nosql or self.docker or self.redis


@dataclass(frozen=True)
class PlanSummarySection:
    """Structured, presentation-ready slice of a GenerationPlan.

    CLI/UI layers format these rows; this type stays free of Rich/Typer.
    """

    title: str
    rows: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GenerationPlan:
    """What Forge must generate to satisfy a ProjectDefinition.

    Produced by ``resolve_plan`` before any filesystem writes. The generator
    consumes this plan; it should not re-interpret raw capability choices.
    """

    definition: ProjectDefinition
    package_name: str
    template_subdir: Path
    features: GenerationFeatures
    runtime_dependencies: tuple[str, ...]
    dev_dependencies: tuple[str, ...]
    database_url_example: str
    mongodb_url_example: str
    mongodb_database_example: str
    redis_url_example: str
    app_module: str
    entry_file: str
    run_command: str
    architecture_label: str
    framework_label: str
    # Canonical env vars for the selected stack (plan, .env.example, README).
    environment_variables: tuple[EnvVarSpec, ...] = ()
    generated_secrets: tuple[GeneratedSecretSpec, ...] = ()
    # Compose dependency service names when Docker is enabled (not the app).
    docker_services: tuple[str, ...] = ()
    # Runtime processes (API always; worker when background jobs).
    processes: tuple[ProcessSpec, ...] = ()
    # Current generated liveness endpoint path for this stack.
    health_path: str = "/health"
    # Framework-specific migrate / check helpers (None when not applicable)
    migrate_command: str | None = None
    check_command: str | None = None
    # Django: dotted path of the primary app package (e.g. "core" or "apps.core")
    primary_app: str | None = None
    # Resolved project modules and structured template contributions.
    contributions: ModuleContributions | None = None

    @property
    def emits_env_example(self) -> bool:
        """Emit ``.env.example`` only when there are concrete variables."""
        return bool(self.environment_variables)

    @property
    def emits_local_env(self) -> bool:
        return bool(self.generated_secrets)

    @property
    def worker_command(self) -> str | None:
        for process in self.processes:
            if process.id == "worker":
                return process.command
        return None

    def summary_sections(self) -> tuple[PlanSummarySection, ...]:
        """Human-oriented sections derived from resolved plan data only."""
        definition = self.definition
        features = self.features
        caps = definition.capabilities

        project_rows: list[tuple[str, str]] = [
            ("Name", definition.name),
            ("Language", catalog.LANGUAGE_LABELS[definition.language]),
            ("Type", catalog.PROJECT_TYPE_LABELS[definition.project_type]),
            ("Framework", self.framework_label),
            ("Architecture", self.architecture_label),
            ("Package", self.package_name),
        ]
        if features.rest_framework:
            project_rows.append(("API", "Django REST Framework"))

        sections: list[PlanSummarySection] = [
            PlanSummarySection("Project", tuple(project_rows)),
        ]

        contrib = self.contributions
        if contrib is not None and contrib.enabled:
            module_rows = tuple(
                (
                    m.label + (" (implied)" if m.implied else ""),
                    m.id,
                )
                for m in contrib.modules
            )
            sections.append(PlanSummarySection("Modules", module_rows))
            if contrib.products_link_categories:
                sections.append(
                    PlanSummarySection(
                        "Relationship",
                        (("Products", "Category (many-to-one)"),),
                    )
                )

        if features.authentication:
            sections.extend(
                [
                    PlanSummarySection(
                        "Identity",
                        (("Identifier", "email"), ("User ID", "UUID"), ("Persistence", "SQL")),
                    ),
                    PlanSummarySection(
                        "Authentication",
                        (
                            ("Registration", "enabled" if features.registration else "disabled"),
                            ("Access tokens", "JWT, 15 minutes"),
                            ("Refresh sessions", "opaque, persistent, rotating"),
                            ("Refresh lifetime", "30 days"),
                            ("Logout", "refresh-session revocation"),
                            (
                                "Email verification",
                                "enabled" if features.email_verification else "disabled",
                            ),
                            (
                                "Password reset",
                                "enabled" if features.password_reset else "disabled",
                            ),
                        ),
                    ),
                    PlanSummarySection(
                        "Security",
                        (
                            ("Password hashing", "Argon2id"),
                            ("Transport", "Authorization Bearer"),
                            ("JWT secret", "generated locally / required in production"),
                            *(
                                (("Verification tokens", "opaque, single-use, 24 hours"),)
                                if features.email_verification
                                else ()
                            ),
                            *(
                                (("Reset tokens", "opaque, single-use, 30 minutes"),)
                                if features.password_reset
                                else ()
                            ),
                        ),
                    ),
                ]
            )

        if features.authorization:
            sections.append(
                PlanSummarySection(
                    "Authorization",
                    (
                        ("Model", "roles + permissions"),
                        ("Policy helpers", "authenticated, verified, permission, any-permission"),
                        ("Ownership helpers", "owner-or-permission + scoped-query guidance"),
                    ),
                )
            )

        if features.storage_backend:
            storage_rows: list[tuple[str, str]] = [
                (
                    "Backend",
                    STORAGE_BACKEND_LABELS.get(
                        features.storage_backend, features.storage_backend
                    ),
                )
            ]
            if features.minio:
                storage_rows.append(("Local development", "MinIO"))
            sections.append(PlanSummarySection("Storage", tuple(storage_rows)))

        if features.background_jobs:
            job_rows: list[tuple[str, str]] = [
                ("Queue", "RQ"),
                (
                    "Redis",
                    (
                        "reuse NoSQL selection"
                        if features.redis_nosql
                        else "required infrastructure"
                    ),
                ),
            ]
            sections.append(PlanSummarySection("Background Jobs", tuple(job_rows)))

        if features.email:
            delivery = (
                "background worker"
                if features.background_jobs
                and (features.email_verification or features.password_reset)
                else "direct SMTP"
            )
            sections.append(
                PlanSummarySection(
                    "Email",
                    (("Transport", "SMTP"), ("Security email delivery", delivery)),
                )
            )

        if features.webhooks:
            sections.append(
                PlanSummarySection(
                    "Webhooks",
                    (
                        ("Direction", "Outgoing"),
                        ("Delivery", "Background Jobs (RQ)"),
                    ),
                )
            )

        if features.database or features.nosql:
            if features.database:
                engine = caps.sql_database or "yes"
                sql_rows: list[tuple[str, str]] = [
                    (
                        "Database",
                        catalog.SQL_DATABASE_LABELS.get(engine, engine),
                    )
                ]
                if features.orm:
                    sql_rows.append(("ORM", _orm_label(features.orm)))
                if features.migration_system:
                    sql_rows.append(
                        ("Migrations", _migration_label(features.migration_system))
                    )
                else:
                    sql_rows.append(("Migrations", "none"))
                sections.append(PlanSummarySection("SQL", tuple(sql_rows)))

            if features.nosql:
                nosql_engine = caps.nosql_database or "yes"
                nosql_rows: list[tuple[str, str]] = [
                    (
                        "Database",
                        catalog.NOSQL_DATABASE_LABELS.get(nosql_engine, nosql_engine),
                    )
                ]
                if features.nosql_client:
                    nosql_rows.append(
                        ("Client", _nosql_client_label(features.nosql_client))
                    )
                sections.append(PlanSummarySection("NoSQL", tuple(nosql_rows)))
            elif features.redis and not features.redis_nosql:
                sections.append(
                    PlanSummarySection(
                        "Infrastructure",
                        (("Redis", "required by Background Jobs"),),
                    )
                )
        else:
            if features.redis and not features.redis_nosql:
                sections.append(
                    PlanSummarySection(
                        "Infrastructure",
                        (("Redis", "required by Background Jobs"),),
                    )
                )
            else:
                sections.append(
                    PlanSummarySection("Persistence", (("Database", "none"),))
                )

        if self.processes:
            sections.append(
                PlanSummarySection(
                    "Processes",
                    tuple((p.label, p.command) for p in self.processes),
                )
            )

        tooling_rows: list[tuple[str, str]] = [
            ("Testing", "pytest" if features.testing else "no"),
            ("Linting", "Ruff" if features.linting else "no"),
            (
                "CI",
                (
                    catalog.CI_PROVIDER_LABELS.get(
                        features.ci_provider or "", features.ci_provider or ""
                    )
                    if features.ci_provider
                    else "no"
                ),
            ),
            ("Docker", "yes" if features.docker else "no"),
        ]

        command_rows: list[tuple[str, str]] = [
            ("Run", self.run_command),
        ]
        if self.migrate_command:
            command_rows.append(("Migrate", self.migrate_command))
        if self.check_command:
            command_rows.append(("Check", self.check_command))
        if self.worker_command:
            command_rows.append(("Worker", self.worker_command))

        dep_rows: list[tuple[str, str]] = []
        if self.runtime_dependencies:
            dep_rows.append(("Runtime", ", ".join(self.runtime_dependencies)))
        if self.dev_dependencies:
            dep_rows.append(("Development", ", ".join(self.dev_dependencies)))

        sections.extend(
            [
                PlanSummarySection("Tooling", tuple(tooling_rows)),
                PlanSummarySection(
                    "Template",
                    (("Path", self.template_subdir.as_posix()),),
                ),
                PlanSummarySection("Commands", tuple(command_rows)),
            ]
        )
        if dep_rows:
            sections.append(PlanSummarySection("Dependencies", tuple(dep_rows)))

        if self.environment_variables:
            sections.append(
                PlanSummarySection(
                    "Environment",
                    tuple(
                        (spec.name, spec.purpose)
                        for spec in self.environment_variables
                    ),
                )
            )

        if features.docker:
            services_label = (
                ", ".join(self.docker_services)
                if self.docker_services
                else "none (app image only)"
            )
            sections.append(
                PlanSummarySection("Docker", (("Services", services_label),))
            )

        sections.append(
            PlanSummarySection(
                "HTTP",
                (("Health", f"GET {self.health_path}"),),
            )
        )

        return tuple(sections)

    def as_jinja_dict(self) -> dict[str, object]:
        """Presentation context for Jinja templates (no resolution logic)."""
        features = self.features
        definition = self.definition
        storage = definition.storage
        return {
            "project_name": definition.name,
            "package_name": self.package_name,
            "language": definition.language.value,
            "project_type": definition.project_type.value,
            "framework": definition.framework,
            "architecture": definition.architecture.value,
            "architecture_label": self.architecture_label,
            "framework_label": self.framework_label,
            "database": features.database,
            "database_engine": definition.capabilities.sql_database,
            "sql_database": definition.capabilities.sql_database,
            "nosql_database": definition.capabilities.nosql_database,
            "orm": features.orm,
            "migrations": features.migrations,
            "migration_system": features.migration_system,
            "nosql": features.nosql,
            "nosql_client": features.nosql_client,
            "docker": features.docker,
            "testing": features.testing,
            "linting": features.linting,
            "ci": features.ci,
            "ci_provider": features.ci_provider,
            "rest_framework": features.rest_framework,
            "is_postgresql": features.postgresql,
            "is_sqlite": features.sqlite,
            "is_mongodb": features.mongodb,
            "is_redis": features.redis,
            "is_redis_nosql": features.redis_nosql,
            "storage_backend": features.storage_backend,
            "is_storage_local": features.storage_backend == "local",
            "is_storage_s3": features.storage_backend == "s3",
            "has_minio": features.minio,
            "has_background_jobs": features.background_jobs,
            "has_email": features.email,
            "has_webhooks": features.webhooks,
            "has_rq": features.rq,
            "has_authentication": features.authentication,
            "has_authorization": features.authorization,
            "authentication_registration": features.registration,
            "authentication_email_verification": features.email_verification,
            "authentication_password_reset": features.password_reset,
            "has_worker": any(p.id == "worker" for p in self.processes),
            "is_simple": definition.architecture.value == "simple",
            "is_modular": definition.architecture.value == "modular-monolith",
            "database_url_example": self.database_url_example,
            "mongodb_url_example": self.mongodb_url_example,
            "mongodb_database_example": self.mongodb_database_example,
            "redis_url_example": self.redis_url_example,
            "app_module": self.app_module,
            "entry_file": self.entry_file,
            "run_command": self.run_command,
            "migrate_command": self.migrate_command,
            "check_command": self.check_command,
            "worker_command": self.worker_command,
            "primary_app": self.primary_app,
            "runtime_dependencies": self.runtime_dependencies,
            "dev_dependencies": self.dev_dependencies,
            "environment_variables": [
                {
                    "name": spec.name,
                    "example": spec.example,
                    "purpose": spec.purpose,
                }
                for spec in self.environment_variables
            ],
            "emits_env_example": self.emits_env_example,
            "emits_local_env": self.emits_local_env,
            "docker_services": self.docker_services,
            "processes": [
                {"id": p.id, "label": p.label, "command": p.command}
                for p in self.processes
            ],
            "health_path": self.health_path,
            "storage_minio": bool(storage.minio) if storage else False,
            **(
                contribution_jinja_dict(self.contributions)
                if self.contributions is not None
                else contribution_jinja_dict(ModuleContributions())
            ),
        }


def _orm_label(orm: str) -> str:
    if orm == "django-orm":
        return "Django ORM"
    if orm == "sqlalchemy":
        return "SQLAlchemy"
    return orm


def _migration_label(system: str) -> str:
    if system == "django":
        return "Django migrations"
    if system == "alembic":
        return "Alembic"
    return system


def _nosql_client_label(client: str) -> str:
    if client == "pymongo":
        return "pymongo"
    if client == "redis":
        return "redis"
    return client
