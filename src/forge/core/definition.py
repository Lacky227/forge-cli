"""Normalized project definition — CLI-independent domain model."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from forge.core import catalog
from forge.core.types import ArchitectureStyle, Language, ProjectType

_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")


class Capabilities(BaseModel):
    """Optional features selected for the project.

    Fields are omitted or left default when irrelevant — generation (later)
    should treat absence as “not selected,” not as a missing requirement.
    """

    model_config = ConfigDict(extra="forbid")

    database: bool = False
    database_engine: str | None = None
    orm: str | None = None
    docker: bool = False
    testing: bool = True


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
            expected_orm = catalog.default_orm_for(self.framework)
            if expected_orm and caps.orm != expected_orm:
                raise ValueError(
                    f"orm must be {expected_orm!r} when using {self.framework!r} "
                    "with a database"
                )
        else:
            if caps.database_engine is not None or caps.orm is not None:
                raise ValueError(
                    "database_engine and orm require capabilities.database=True"
                )

        return self

    def to_display_dict(self) -> dict[str, Any]:
        """Human-oriented summary values for CLI display."""
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
            "ORM": caps.orm or "—",
            "Docker": "Yes" if caps.docker else "No",
            "Testing": "Yes" if caps.testing else "No",
        }
        if not caps.database:
            rows.pop("ORM")
        return rows
