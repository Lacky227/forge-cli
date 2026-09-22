"""Official generation compatibility matrix — representative supported cases.

The resolver (``resolve_plan``) remains the authority for validity. This module
documents the product's **officially supported** generation contract and lists
representative cases used for smoke coverage. It is not a second compatibility
engine and must not be used to bypass resolver checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType


@dataclass(frozen=True)
class GenerationCase:
    """One officially supported ProjectDefinition shape for smoke coverage."""

    id: str
    framework: str
    architecture: ArchitectureStyle
    # None = no database (FastAPI/Flask only). Django always requires an engine.
    database_engine: str | None
    migrations: bool = False
    docker: bool = False
    testing: bool = True
    linting: bool = True
    language: Language = Language.PYTHON
    project_type: ProjectType = ProjectType.REST_API

    @property
    def database(self) -> bool:
        return self.database_engine is not None

    def to_definition(self, *, name: str | None = None) -> ProjectDefinition:
        """Build a validated ProjectDefinition for this case."""
        project_name = name or f"case-{self.id}"
        return ProjectDefinition(
            name=project_name,
            language=self.language,
            project_type=self.project_type,
            framework=self.framework,
            architecture=self.architecture,
            capabilities=Capabilities(
                database=self.database,
                database_engine=self.database_engine,
                migrations=self.migrations and self.database,
                docker=self.docker,
                testing=self.testing,
                linting=self.linting,
            ),
        )


# Representative matrix — not the Cartesian product of every capability.
# Coverage goals: 3 frameworks × 3 architectures, SQLite / PostgreSQL /
# no-database, migrations, Docker, and framework-implied infrastructure.
SUPPORTED_GENERATION_CASES: tuple[GenerationCase, ...] = (
    # FastAPI
    GenerationCase(
        id="fastapi-simple-sqlite",
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        database_engine="sqlite",
        migrations=True,
    ),
    GenerationCase(
        id="fastapi-modular-postgres",
        framework="fastapi",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        database_engine="postgresql",
        migrations=True,
    ),
    GenerationCase(
        id="fastapi-clean-sqlite-migrations",
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        database_engine="sqlite",
        migrations=True,
    ),
    GenerationCase(
        id="fastapi-clean-postgres-docker",
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        database_engine="postgresql",
        migrations=True,
        docker=True,
    ),
    # Django (database required; ORM / migrations / DRF implied by resolver)
    GenerationCase(
        id="django-simple-sqlite",
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        database_engine="sqlite",
    ),
    GenerationCase(
        id="django-modular-postgres",
        framework="django",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        database_engine="postgresql",
    ),
    GenerationCase(
        id="django-clean-sqlite",
        framework="django",
        architecture=ArchitectureStyle.CLEAN,
        database_engine="sqlite",
    ),
    GenerationCase(
        id="django-clean-postgres-docker",
        framework="django",
        architecture=ArchitectureStyle.CLEAN,
        database_engine="postgresql",
        docker=True,
    ),
    # Flask
    GenerationCase(
        id="flask-simple-nodb",
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
        database_engine=None,
    ),
    GenerationCase(
        id="flask-modular-postgres",
        framework="flask",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        database_engine="postgresql",
        migrations=True,
    ),
    GenerationCase(
        id="flask-clean-sqlite",
        framework="flask",
        architecture=ArchitectureStyle.CLEAN,
        database_engine="sqlite",
        migrations=True,
    ),
    GenerationCase(
        id="flask-clean-postgres-docker",
        framework="flask",
        architecture=ArchitectureStyle.CLEAN,
        database_engine="postgresql",
        migrations=True,
        docker=True,
    ),
)


def supported_generation_cases() -> tuple[GenerationCase, ...]:
    """Return the official representative generation matrix."""
    return SUPPORTED_GENERATION_CASES


def executable_smoke_cases() -> tuple[GenerationCase, ...]:
    """Cases safe to install/test without a live PostgreSQL server.

    PostgreSQL / Docker-enabled cases remain in the matrix for structural
    generation coverage; executable smoke uses SQLite or no-database stacks.
    """
    return tuple(
        case
        for case in SUPPORTED_GENERATION_CASES
        if case.database_engine != "postgresql"
    )
