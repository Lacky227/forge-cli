"""Resolved generation information derived from a ProjectDefinition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge.core import catalog
from forge.core.definition import ProjectDefinition


@dataclass(frozen=True)
class GenerationFeatures:
    """Resolved implementation implications of a ProjectDefinition.

    Includes both explicit user choices (docker, testing, …) and
    framework-implied facts (orm, migration_system, rest_framework).
    """

    database: bool
    postgresql: bool
    sqlite: bool
    migrations: bool
    docker: bool
    testing: bool
    linting: bool
    # Framework-implied / resolved implementation details
    orm: str | None = None
    migration_system: str | None = None  # "alembic" | "django" | None
    # REST API stacks may enable a framework-native API layer (e.g. DRF).
    rest_framework: bool = False

    @property
    def env_example(self) -> bool:
        return self.database or self.docker


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
    app_module: str
    entry_file: str
    run_command: str
    architecture_label: str
    framework_label: str
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

        persistence_rows: list[tuple[str, str]] = []
        if features.database:
            engine = caps.database_engine or "yes"
            persistence_rows.append(
                (
                    "Database",
                    catalog.DATABASE_ENGINE_LABELS.get(engine, engine),
                )
            )
            if features.orm:
                persistence_rows.append(("ORM", _orm_label(features.orm)))
            if features.migration_system:
                persistence_rows.append(
                    ("Migrations", _migration_label(features.migration_system))
                )
            else:
                persistence_rows.append(("Migrations", "none"))
        else:
            persistence_rows.append(("Database", "none"))

        tooling_rows: list[tuple[str, str]] = [
            ("Testing", "pytest" if features.testing else "no"),
            ("Linting", "Ruff" if features.linting else "no"),
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

        sections = [
            PlanSummarySection("Project", tuple(project_rows)),
            PlanSummarySection("Persistence", tuple(persistence_rows)),
            PlanSummarySection("Tooling", tuple(tooling_rows)),
            PlanSummarySection(
                "Template",
                (("Path", self.template_subdir.as_posix()),),
            ),
            PlanSummarySection("Commands", tuple(command_rows)),
        ]
        if dep_rows:
            sections.append(PlanSummarySection("Dependencies", tuple(dep_rows)))
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
            "database_engine": definition.capabilities.database_engine,
            "orm": features.orm,
            "migrations": features.migrations,
            "migration_system": features.migration_system,
            "docker": features.docker,
            "testing": features.testing,
            "linting": features.linting,
            "rest_framework": features.rest_framework,
            "is_postgresql": features.postgresql,
            "is_sqlite": features.sqlite,
            "is_simple": definition.architecture.value == "simple",
            "is_modular": definition.architecture.value == "modular-monolith",
            "database_url_example": self.database_url_example,
            "app_module": self.app_module,
            "entry_file": self.entry_file,
            "run_command": self.run_command,
            "migrate_command": self.migrate_command,
            "check_command": self.check_command,
            "primary_app": self.primary_app,
            "runtime_dependencies": self.runtime_dependencies,
            "dev_dependencies": self.dev_dependencies,
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
