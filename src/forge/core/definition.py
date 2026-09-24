"""Normalized project definition — CLI-independent domain model.

``ProjectDefinition`` captures **explicit user intent** only. Framework-implied
implementation details (ORM, migration system, REST framework package) are
resolved later into a ``GenerationPlan``.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from forge.core import catalog
from forge.core.modules import (
    MODULE_LABELS,
    STORAGE_BACKEND_LABELS,
    ModuleId,
    StorageBackend,
    expand_module_dependencies,
    modules_require_sql,
    normalize_modules,
    normalize_storage_backend,
)
from forge.core.types import ArchitectureStyle, Language, ProjectType

_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
_FALSEY_CI = frozenset({"", "false", "none", "null", "no", "off"})


class StorageOptions(BaseModel):
    """Shallow Files-module storage options (not a selectable module).

    Only meaningful when ``files`` is selected. ``minio`` enables a local
    MinIO Compose service when Docker is on and the backend is S3-compatible.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: str = StorageBackend.LOCAL.value
    minio: bool = False

    @field_validator("backend", mode="before")
    @classmethod
    def backend_normalized(cls, value: object) -> str:
        if value is None:
            return StorageBackend.LOCAL.value
        if not isinstance(value, str):
            raise TypeError("storage.backend must be a string")
        return normalize_storage_backend(value) or StorageBackend.LOCAL.value

    @model_validator(mode="after")
    def minio_requires_s3(self) -> StorageOptions:
        if self.minio and self.backend != StorageBackend.S3.value:
            raise ValueError("storage.minio requires storage.backend: s3")
        return self


class AuthenticationOptions(BaseModel):
    """Stage 1 public authentication choices."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    registration: bool = True



class Capabilities(BaseModel):
    """Explicit user-facing capability choices.

    Persistence is modeled as independent SQL and NoSQL selections:

    * ``sql_database`` — optional ``postgresql`` / ``sqlite``
    * ``nosql_database`` — optional ``mongodb`` / ``redis``

    Absence means “not selected.” Framework-implied details such as which ORM
    or migration system a stack uses belong on ``GenerationPlan``, not here.

    ``orm`` is optional and reserved for programmatic/config paths that state
    an ORM explicitly. The interactive CLI leaves it unset so the resolver
    can imply it. If set, it must be compatible with the framework.
    """

    model_config = ConfigDict(extra="forbid")

    sql_database: str | None = None
    nosql_database: str | None = None
    orm: str | None = None
    # FastAPI/Flask: user chooses Alembic when SQL is selected.
    # Django: ignored; resolver enables Django migrations whenever SQL is present.
    migrations: bool = False
    docker: bool = False
    testing: bool = True
    linting: bool = True
    # Optional CI provider id (e.g. "github-actions"); None = no CI.
    ci: str | None = None

    @field_validator("ci", mode="before")
    @classmethod
    def normalize_ci(cls, value: object) -> str | None:
        if value is None or value is False:
            return None
        if value is True:
            raise ValueError(
                "ci must be a provider name (github-actions) or null — not true"
            )
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in _FALSEY_CI:
                return None
            return cleaned
        raise ValueError("ci must be a string provider name, false, or null")

    @model_validator(mode="after")
    def validate_ci(self) -> Capabilities:
        if self.ci is None:
            return self
        if self.ci not in catalog.CI_PROVIDERS:
            raise ValueError(
                "ci must be one of: " + ", ".join(catalog.CI_PROVIDERS)
            )
        if not self.testing and not self.linting:
            raise ValueError("ci requires testing or linting to be enabled")
        return self

    @property
    def database(self) -> bool:
        """True when an SQL database is selected (legacy-friendly name)."""
        return self.sql_database is not None

    @property
    def database_engine(self) -> str | None:
        """SQL engine id, or ``None`` when SQL is not selected."""
        return self.sql_database

    @property
    def has_persistence(self) -> bool:
        return self.sql_database is not None or self.nosql_database is not None


class ProjectDefinition(BaseModel):
    """Result of user (or config) choices — not prompt/UI state.

    Constructible without any CLI imports so interactive, config-file, and
    future preset paths can all produce the same object for generation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    language: Language
    project_type: ProjectType
    framework: str
    architecture: ArchitectureStyle
    capabilities: Capabilities = Field(default_factory=Capabilities)
    # Selectable domain/API modules (products, categories, files, …). Distinct
    # from Capabilities. Omitted / empty means a scaffold-only project.
    modules: tuple[str, ...] = ()
    # Files storage options — required shape when ``files`` is selected;
    # must be None when Files is not selected.
    storage: StorageOptions | None = None
    # Authentication options are meaningful only with the authentication module.
    authentication: AuthenticationOptions | None = None

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("project name is required")
        if not _NAME_PATTERN.fullmatch(cleaned):
            raise ValueError(
                "project name must start with a letter and contain only "
                "letters, digits, hyphens, and underscores (max 64 chars)"
            )
        return cleaned

    @field_validator("framework")
    @classmethod
    def framework_normalized(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("framework is required")
        return cleaned

    @field_validator("modules", mode="before")
    @classmethod
    def modules_normalized(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            raise TypeError("modules must be a list of module ids, not a string")
        if not isinstance(value, (list, tuple)):
            raise TypeError("modules must be a list of module ids")
        try:
            return normalize_modules(tuple(str(item) for item in value))
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="before")
    @classmethod
    def default_storage_for_files(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        modules_raw = data.get("modules") or ()
        try:
            modules = normalize_modules(
                tuple(str(item) for item in modules_raw)
                if not isinstance(modules_raw, str)
                else ()
            )
        except ValueError:
            return data
        has_files = ModuleId.FILES.value in expand_module_dependencies(modules)
        if has_files and data.get("storage") is None:
            data = {**data, "storage": {"backend": "local", "minio": False}}
        return data

    @model_validator(mode="after")
    def validate_compatibility(self) -> ProjectDefinition:
        if not catalog.is_framework_compatible(
            self.language, self.project_type, self.framework
        ):
            raise ValueError(
                f"framework {self.framework!r} is not valid for "
                f"{self.language.value} / {self.project_type.value}"
            )

        allowed_architectures = catalog.architectures_for(self.project_type)
        if self.architecture not in allowed_architectures:
            raise ValueError(
                f"architecture {self.architecture.value!r} is not valid for "
                f"project type {self.project_type.value}"
            )

        caps = self.capabilities
        if (
            self.framework == "django"
            and self.project_type is ProjectType.REST_API
            and caps.sql_database is None
        ):
            raise ValueError(
                "Django REST API projects require an SQL database "
                "(SQLite or PostgreSQL)"
            )

        if caps.sql_database is not None:
            if not catalog.supports_sql(self.framework):
                raise ValueError(
                    f"framework {self.framework!r} does not support SQL "
                    "persistence in the current catalog"
                )
            if caps.sql_database not in catalog.SQL_DATABASES:
                raise ValueError(
                    "sql_database must be one of: "
                    + ", ".join(catalog.SQL_DATABASES)
                )
            expected_orm = catalog.default_orm_for(self.framework)
            if caps.orm is not None and expected_orm and caps.orm != expected_orm:
                raise ValueError(
                    f"orm must be {expected_orm!r} when using {self.framework!r} "
                    "with an SQL database"
                )
        else:
            if caps.orm is not None:
                raise ValueError("orm requires capabilities.sql_database")
            if caps.migrations:
                raise ValueError("migrations require capabilities.sql_database")

        if caps.nosql_database is not None:
            if not catalog.supports_nosql(self.framework):
                raise ValueError(
                    f"framework {self.framework!r} does not support NoSQL "
                    "clients in the current catalog"
                )
            if caps.nosql_database not in catalog.NOSQL_DATABASES:
                raise ValueError(
                    "nosql_database must be one of: "
                    + ", ".join(catalog.NOSQL_DATABASES)
                )

        if (
            self.modules
            and modules_require_sql(self.modules)
            and caps.sql_database is None
        ):
            labels = ", ".join(MODULE_LABELS.get(m, m) for m in self.modules)
            raise ValueError(
                f"modules require an SQL database (selected: {labels})"
            )

        has_files = ModuleId.FILES.value in expand_module_dependencies(
            self.modules
        )
        has_authentication = ModuleId.AUTHENTICATION.value in expand_module_dependencies(
            self.modules
        )
        if not has_authentication and self.authentication is not None:
            raise ValueError(
                "authentication options require the authentication module to be selected"
            )
        if (
            has_authentication
            and self.framework in {"fastapi", "flask"}
            and not caps.migrations
        ):
            raise ValueError(
                "authentication requires Alembic migrations for FastAPI and Flask"
            )
        if not has_files and self.storage is not None:
            raise ValueError(
                "storage options require the files module to be selected"
            )
        if self.storage is not None and self.storage.minio and not caps.docker:
            raise ValueError("storage.minio requires capabilities.docker")
        if has_files and self.storage is None:
            raise ValueError(
                "the files module requires storage options "
                "(backend: local or s3)"
            )

        return self

    @property
    def authentication_options(self) -> AuthenticationOptions:
        """Resolved Stage 1 defaults when Authentication is selected."""
        return self.authentication or AuthenticationOptions()

    def to_display_dict(self) -> dict[str, Any]:
        """Human-oriented summary of explicit choices (plus implied labels).

        Implied ORM / migration / API labels are derived for readability only;
        they are not stored as independent user decisions on this model.
        """
        caps = self.capabilities
        rows: dict[str, Any] = {
            "Name": self.name,
            "Type": catalog.PROJECT_TYPE_LABELS[self.project_type],
            "Language": catalog.LANGUAGE_LABELS[self.language],
            "Framework": catalog.FRAMEWORK_LABELS.get(
                self.framework, self.framework
            ),
            "Architecture": catalog.ARCHITECTURE_LABELS[self.architecture],
            "SQL": (
                catalog.SQL_DATABASE_LABELS.get(
                    caps.sql_database or "", caps.sql_database
                )
                if caps.sql_database
                else "No"
            ),
            "NoSQL": (
                catalog.NOSQL_DATABASE_LABELS.get(
                    caps.nosql_database or "", caps.nosql_database
                )
                if caps.nosql_database
                else "No"
            ),
            "Docker": "Yes" if caps.docker else "No",
            "Testing": "Yes" if caps.testing else "No",
            "Linting": "Ruff" if caps.linting else "No",
            "CI": (
                catalog.CI_PROVIDER_LABELS.get(caps.ci, caps.ci)
                if caps.ci
                else "No"
            ),
        }
        if caps.sql_database:
            implied_orm = caps.orm or catalog.default_orm_for(self.framework)
            rows["ORM"] = _orm_display(implied_orm)
            rows["Migrations"] = _migrations_display(self.framework, caps)
        if self.framework == "django" and self.project_type is ProjectType.REST_API:
            rows["API"] = "Django REST Framework"
        if self.modules:
            rows["Modules"] = ", ".join(
                MODULE_LABELS.get(m, m) for m in self.modules
            )
        if self.storage is not None:
            rows["Storage"] = STORAGE_BACKEND_LABELS.get(
                self.storage.backend, self.storage.backend
            )
            if self.storage.minio:
                rows["MinIO"] = "Yes"
        return rows


def _orm_display(orm: str | None) -> str:
    if orm == "django-orm":
        return "Django ORM"
    if orm == "sqlalchemy":
        return "SQLAlchemy"
    return orm or "—"


def _migrations_display(framework: str, caps: Capabilities) -> str:
    if framework == "django":
        return "Django"
    if caps.migrations:
        return "Alembic"
    return "No"
