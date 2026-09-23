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
    # None = no SQL (FastAPI/Flask). Django always requires an SQL engine.
    sql_database: str | None = None
    nosql_database: str | None = None
    migrations: bool = False
    docker: bool = False
    testing: bool = True
    linting: bool = True
    language: Language = Language.PYTHON
    project_type: ProjectType = ProjectType.REST_API

    @property
    def database(self) -> bool:
        return self.sql_database is not None

    @property
    def database_engine(self) -> str | None:
        """Backward-compatible alias for the SQL engine."""
        return self.sql_database

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
                sql_database=self.sql_database,
                nosql_database=self.nosql_database,
                migrations=self.migrations and self.sql_database is not None,
                docker=self.docker,
                testing=self.testing,
                linting=self.linting,
            ),
        )


# Representative matrix — not the Cartesian product of every capability.
# Coverage goals: 3 frameworks × 3 architectures, SQL / NoSQL / combined /
# no-persistence, migrations, Docker, and framework-implied infrastructure.
SUPPORTED_GENERATION_CASES: tuple[GenerationCase, ...] = (
    # FastAPI
    GenerationCase(
        id="fastapi-simple-sqlite",
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
        migrations=True,
    ),
    GenerationCase(
        id="fastapi-modular-postgres",
        framework="fastapi",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=True,
    ),
    GenerationCase(
        id="fastapi-clean-sqlite-migrations",
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="sqlite",
        migrations=True,
    ),
    GenerationCase(
        id="fastapi-clean-postgres-docker",
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="postgresql",
        migrations=True,
        docker=True,
    ),
    GenerationCase(
        id="fastapi-modular-mongodb",
        framework="fastapi",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        nosql_database="mongodb",
        docker=True,
    ),
    GenerationCase(
        id="fastapi-simple-postgres-redis",
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="postgresql",
        nosql_database="redis",
        migrations=True,
        docker=True,
    ),
    # Django (SQL required; ORM / migrations / DRF implied by resolver)
    GenerationCase(
        id="django-simple-sqlite",
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
    ),
    GenerationCase(
        id="django-modular-postgres",
        framework="django",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
    ),
    GenerationCase(
        id="django-clean-sqlite",
        framework="django",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="sqlite",
    ),
    GenerationCase(
        id="django-clean-postgres-docker",
        framework="django",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="postgresql",
        docker=True,
    ),
    GenerationCase(
        id="django-modular-postgres-redis",
        framework="django",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        nosql_database="redis",
        docker=True,
    ),
    # Flask
    GenerationCase(
        id="flask-simple-nodb",
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
    ),
    GenerationCase(
        id="flask-modular-postgres",
        framework="flask",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=True,
    ),
    GenerationCase(
        id="flask-clean-sqlite",
        framework="flask",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="sqlite",
        migrations=True,
    ),
    GenerationCase(
        id="flask-clean-postgres-docker",
        framework="flask",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="postgresql",
        migrations=True,
        docker=True,
    ),
    GenerationCase(
        id="flask-simple-sqlite-mongodb",
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
        nosql_database="mongodb",
        migrations=True,
    ),
    GenerationCase(
        id="fastapi-clean-mongodb",
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        nosql_database="mongodb",
    ),
)


def supported_generation_cases() -> tuple[GenerationCase, ...]:
    """Return the official representative generation matrix."""
    return SUPPORTED_GENERATION_CASES


def executable_smoke_cases() -> tuple[GenerationCase, ...]:
    """Cases safe to install/test without live external database servers.

    PostgreSQL / MongoDB / Redis / Docker-enabled cases remain in the matrix
    for structural generation coverage; executable smoke uses SQLite or
    no-persistence stacks only.
    """
    return tuple(
        case
        for case in SUPPORTED_GENERATION_CASES
        if case.sql_database != "postgresql"
        and case.nosql_database is None
        and not case.docker
    )
