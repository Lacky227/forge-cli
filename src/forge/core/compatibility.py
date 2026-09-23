"""Official generation compatibility matrix — representative supported cases.

The resolver (``resolve_plan``) remains the authority for validity. This module
documents the product's **officially supported** generation contract and lists
representative cases used for smoke coverage. It is not a second compatibility
engine and must not be used to bypass resolver checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.core.definition import Capabilities, ProjectDefinition, StorageOptions
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
    ci: str | None = None
    language: Language = Language.PYTHON
    project_type: ProjectType = ProjectType.REST_API
    modules: tuple[str, ...] = ()
    storage_backend: str | None = None
    storage_minio: bool = False

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
        storage = None
        if "files" in self.modules or self.storage_backend is not None:
            storage = StorageOptions(
                backend=self.storage_backend or "local",
                minio=self.storage_minio,
            )
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
                ci=self.ci,
            ),
            modules=self.modules,
            storage=storage,
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
    # Project modules (Products / Categories) — Stage 1 representative cases
    GenerationCase(
        id="fastapi-simple-products-sqlite",
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
        migrations=True,
        modules=("products",),
    ),
    GenerationCase(
        id="fastapi-modular-catalog-postgres",
        framework="fastapi",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=True,
        modules=("products", "categories"),
    ),
    GenerationCase(
        id="fastapi-clean-catalog-sqlite",
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="sqlite",
        migrations=True,
        modules=("products", "categories"),
    ),
    GenerationCase(
        id="django-simple-products",
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
        modules=("products",),
    ),
    GenerationCase(
        id="django-modular-categories",
        framework="django",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="sqlite",
        modules=("categories",),
    ),
    GenerationCase(
        id="django-clean-catalog",
        framework="django",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="sqlite",
        modules=("products", "categories"),
    ),
    GenerationCase(
        id="flask-simple-categories-sqlite",
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
        migrations=True,
        modules=("categories",),
    ),
    GenerationCase(
        id="flask-modular-products-postgres",
        framework="flask",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=True,
        modules=("products",),
    ),
    GenerationCase(
        id="flask-clean-catalog-sqlite",
        framework="flask",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="sqlite",
        migrations=True,
        modules=("products", "categories"),
    ),
    # Stage 2 infrastructure-backed modules (representative, not Cartesian)
    GenerationCase(
        id="fastapi-simple-files-local",
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
        migrations=True,
        modules=("files",),
        storage_backend="local",
    ),
    GenerationCase(
        id="fastapi-modular-files-jobs-s3-minio",
        framework="fastapi",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=True,
        docker=True,
        modules=("products", "files", "background-jobs"),
        storage_backend="s3",
        storage_minio=True,
    ),
    GenerationCase(
        id="fastapi-clean-all-modules",
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="postgresql",
        migrations=True,
        docker=True,
        modules=(
            "products",
            "categories",
            "files",
            "background-jobs",
            "email",
            "webhooks",
        ),
        storage_backend="s3",
        storage_minio=True,
    ),
    GenerationCase(
        id="django-simple-files-email",
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
        modules=("files", "email"),
        storage_backend="local",
    ),
    GenerationCase(
        id="django-modular-jobs-webhooks",
        framework="django",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        docker=True,
        modules=("products", "categories", "background-jobs", "webhooks"),
    ),
    GenerationCase(
        id="django-clean-files-jobs-email",
        framework="django",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="sqlite",
        modules=("files", "background-jobs", "email"),
        storage_backend="s3",
    ),
    GenerationCase(
        id="flask-simple-files-jobs",
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
        sql_database="sqlite",
        migrations=True,
        modules=("files", "background-jobs"),
        storage_backend="local",
    ),
    GenerationCase(
        id="flask-modular-files-email",
        framework="flask",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=True,
        modules=("products", "files", "email"),
        storage_backend="s3",
    ),
    GenerationCase(
        id="flask-clean-all-modules",
        framework="flask",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="sqlite",
        migrations=True,
        modules=(
            "products",
            "categories",
            "files",
            "background-jobs",
            "email",
            "webhooks",
        ),
        storage_backend="local",
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
