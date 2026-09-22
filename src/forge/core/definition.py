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
from forge.core.types import ArchitectureStyle, Language, ProjectType

_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")


class Capabilities(BaseModel):
    """Explicit user-facing capability choices.

    Absence means “not selected.” Framework-implied details such as which ORM
    or migration system a stack uses belong on ``GenerationPlan``, not here.

    ``orm`` is optional and reserved for programmatic/config paths that state
    an ORM explicitly. The interactive CLI leaves it unset so the resolver
    can imply it. If set, it must be compatible with the framework.
    """

    model_config = ConfigDict(extra="forbid")

    database: bool = False
    database_engine: str | None = None
    orm: str | None = None
    # FastAPI: user chooses Alembic. Django: ignored; resolver enables Django
    # migrations whenever a database is present.
    migrations: bool = False
    docker: bool = False
    testing: bool = True
    linting: bool = True


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
    def framework_must_be_nonempty(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("framework is required")
        return cleaned

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
            and not caps.database
        ):
            raise ValueError(
                "Django REST API projects require a database "
                "(SQLite or PostgreSQL)"
            )

        if caps.database:
            if not catalog.supports_database(self.framework):
                raise ValueError(
                    f"framework {self.framework!r} does not support a database "
                    "capability in the current catalog"
                )
            if caps.database_engine not in catalog.DATABASE_ENGINES:
                raise ValueError(
                    "database_engine must be one of: "
                    + ", ".join(catalog.DATABASE_ENGINES)
                )
            # Explicit ORM override must match the framework; omission is fine
            # and is resolved into GenerationPlan.
            expected_orm = catalog.default_orm_for(self.framework)
            if caps.orm is not None and expected_orm and caps.orm != expected_orm:
                raise ValueError(
                    f"orm must be {expected_orm!r} when using {self.framework!r} "
                    "with a database"
                )
        else:
            if caps.database_engine is not None or caps.orm is not None:
                raise ValueError(
                    "database_engine and orm require capabilities.database=True"
                )
            if caps.migrations:
                raise ValueError("migrations require capabilities.database=True")

        return self

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
            "Database": (
                catalog.DATABASE_ENGINE_LABELS.get(
                    caps.database_engine or "", caps.database_engine
                )
                if caps.database
                else "No"
            ),
            "Docker": "Yes" if caps.docker else "No",
            "Testing": "Yes" if caps.testing else "No",
            "Linting": "Ruff" if caps.linting else "No",
        }
        if caps.database:
            implied_orm = caps.orm or catalog.default_orm_for(self.framework)
            rows["ORM"] = _orm_display(implied_orm)
            rows["Migrations"] = _migrations_display(self.framework, caps)
        if self.framework == "django" and self.project_type is ProjectType.REST_API:
            rows["API"] = "Django REST Framework"
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
