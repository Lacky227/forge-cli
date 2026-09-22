"""Resolved generation information derived from a ProjectDefinition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge.core.definition import ProjectDefinition


@dataclass(frozen=True)
class GenerationFeatures:
    """Explicit generation implications of selected capabilities."""

    database: bool
    postgresql: bool
    sqlite: bool
    migrations: bool
    docker: bool
    testing: bool
    linting: bool

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
            "orm": definition.capabilities.orm,
            "migrations": features.migrations,
            "docker": features.docker,
            "testing": features.testing,
            "linting": features.linting,
            "is_postgresql": features.postgresql,
            "is_sqlite": features.sqlite,
            "is_simple": definition.architecture.value == "simple",
            "is_modular": definition.architecture.value == "modular-monolith",
            "database_url_example": self.database_url_example,
            "app_module": self.app_module,
            "entry_file": self.entry_file,
            "run_command": self.run_command,
            "runtime_dependencies": self.runtime_dependencies,
            "dev_dependencies": self.dev_dependencies,
        }
