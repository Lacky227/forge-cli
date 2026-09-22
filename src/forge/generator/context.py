"""Template context derived from a ProjectDefinition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge.core import catalog
from forge.core.definition import ProjectDefinition
from forge.core.naming import to_package_name
from forge.core.types import ArchitectureStyle


@dataclass(frozen=True)
class TemplateContext:
    """Values available to Jinja templates and path rewriting."""

    project_name: str
    package_name: str
    language: str
    project_type: str
    framework: str
    architecture: str
    architecture_label: str
    framework_label: str
    database: bool
    database_engine: str | None
    orm: str | None
    migrations: bool
    docker: bool
    testing: bool
    linting: bool
    is_postgresql: bool
    is_sqlite: bool
    is_simple: bool
    is_modular: bool
    # Example DATABASE_URL for .env.example (never real secrets)
    database_url_example: str
    app_module: str  # e.g. my_api.main:app for uvicorn
    entry_file: str  # e.g. src/my_api/main.py

    @classmethod
    def from_definition(cls, definition: ProjectDefinition) -> TemplateContext:
        caps = definition.capabilities
        package = to_package_name(definition.name)
        engine = caps.database_engine
        if caps.database and engine == "postgresql":
            db_url = (
                "postgresql+psycopg://postgres:postgres@localhost:5432/"
                f"{package}"
            )
        elif caps.database and engine == "sqlite":
            db_url = f"sqlite:///./{package}.db"
        else:
            db_url = ""

        return cls(
            project_name=definition.name,
            package_name=package,
            language=definition.language.value,
            project_type=definition.project_type.value,
            framework=definition.framework,
            architecture=definition.architecture.value,
            architecture_label=catalog.ARCHITECTURE_LABELS[definition.architecture],
            framework_label=catalog.FRAMEWORK_LABELS.get(
                definition.framework, definition.framework
            ),
            database=caps.database,
            database_engine=engine,
            orm=caps.orm,
            migrations=caps.migrations,
            docker=caps.docker,
            testing=caps.testing,
            linting=caps.linting,
            is_postgresql=engine == "postgresql",
            is_sqlite=engine == "sqlite",
            is_simple=definition.architecture is ArchitectureStyle.SIMPLE,
            is_modular=(
                definition.architecture is ArchitectureStyle.MODULAR_MONOLITH
            ),
            database_url_example=db_url,
            app_module=f"{package}.main:app",
            entry_file=f"src/{package}/main.py",
        )

    def as_jinja_dict(self) -> dict[str, object]:
        return {
            "project_name": self.project_name,
            "package_name": self.package_name,
            "language": self.language,
            "project_type": self.project_type,
            "framework": self.framework,
            "architecture": self.architecture,
            "architecture_label": self.architecture_label,
            "framework_label": self.framework_label,
            "database": self.database,
            "database_engine": self.database_engine,
            "orm": self.orm,
            "migrations": self.migrations,
            "docker": self.docker,
            "testing": self.testing,
            "linting": self.linting,
            "is_postgresql": self.is_postgresql,
            "is_sqlite": self.is_sqlite,
            "is_simple": self.is_simple,
            "is_modular": self.is_modular,
            "database_url_example": self.database_url_example,
            "app_module": self.app_module,
            "entry_file": self.entry_file,
        }


def template_subdir(definition: ProjectDefinition) -> Path:
    """Relative path under the templates root for this definition."""
    return Path(
        definition.language.value,
        definition.framework,
        definition.architecture.value,
    )
