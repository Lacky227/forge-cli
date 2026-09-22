"""Resolved generation information derived from a ProjectDefinition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
