"""Resolved generation information derived from a ProjectDefinition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge.core import catalog
from forge.core.definition import ProjectDefinition


@dataclass(frozen=True)
class EnvVarSpec:
    """One environment variable the generated project expects.

    Built by ``resolve_plan`` from the selected stack. Future template /
    README emission should consume this list rather than re-deriving names.
    """

    name: str
    example: str
    purpose: str


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
    redis: bool
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

    @property
    def ci(self) -> bool:
        """True when a CI provider was selected."""
        return self.ci_provider is not None

    @property
    def env_example(self) -> bool:
        return self.database or self.nosql or self.docker


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
    # Canonical env vars for the selected stack (plan / future .env / README).
    environment_variables: tuple[EnvVarSpec, ...] = ()
    # Compose dependency service names when Docker is enabled (not the app).
    docker_services: tuple[str, ...] = ()
    # Current generated liveness endpoint path for this stack.
    health_path: str = "/health"
    # Framework-specific migrate / check helpers (None when not applicable)
    migrate_command: str | None = None
    check_command: str | None = None
    # Django: dotted path of the primary app package (e.g. "core" or "apps.core")
    primary_app: str | None = None

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
        else:
            sections.append(
                PlanSummarySection("Persistence", (("Database", "none"),))
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
            "docker_services": self.docker_services,
            "health_path": self.health_path,
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
