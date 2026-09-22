"""Load Forge YAML configuration into a ProjectDefinition.

Configuration expresses **explicit user choices** only. Framework implications
(ORM, migration system, DRF, …) remain owned by ``resolve_plan``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType

_FALSEY_DATABASE = frozenset({"", "false", "none", "null", "no", "off"})


class ConfigError(Exception):
    """User-facing configuration error (file, YAML, or mapping)."""


class _ProjectSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None


class ForgeConfig(BaseModel):
    """YAML-facing input model — maps to ``ProjectDefinition``.

    Field names favour a short human schema (``type``, ``database: postgresql``)
    rather than mirroring internal capability nesting.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    project: _ProjectSection | None = None
    name: str | None = None
    language: Language = Language.PYTHON
    project_type: ProjectType = Field(alias="type")
    framework: str
    architecture: ArchitectureStyle
    # Engine string enables DB; false/null/omitted means no database.
    database: str | bool | None = None
    orm: str | None = None
    migrations: bool = False
    testing: bool = True
    linting: bool = True
    docker: bool = False

    @field_validator("framework")
    @classmethod
    def framework_normalized(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("framework is required")
        return cleaned

    @field_validator("database", mode="before")
    @classmethod
    def normalize_database(cls, value: Any) -> str | bool | None:
        if value is None or value is False:
            return None
        if value is True:
            raise ValueError(
                "database must be an engine name "
                "(postgresql, sqlite) or false/null — not true"
            )
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in _FALSEY_DATABASE:
                return None
            return cleaned
        raise ValueError("database must be a string engine name, false, or null")

    @model_validator(mode="after")
    def names_must_agree(self) -> ForgeConfig:
        top = self.name.strip() if self.name else None
        nested = (
            self.project.name.strip()
            if self.project and self.project.name
            else None
        )
        if top and nested and top != nested:
            raise ValueError(
                f"conflicting project names: name={top!r} and "
                f"project.name={nested!r}"
            )
        return self

    def resolved_config_name(self) -> str | None:
        if self.name and self.name.strip():
            return self.name.strip()
        if self.project and self.project.name and self.project.name.strip():
            return self.project.name.strip()
        return None

    def to_definition(self, *, cli_name: str | None = None) -> ProjectDefinition:
        """Build a validated ``ProjectDefinition``.

        Name rule: CLI ``name`` argument wins when provided; otherwise the
        config name is required.
        """
        name = (cli_name.strip() if cli_name and cli_name.strip() else None) or (
            self.resolved_config_name()
        )
        if not name:
            raise ConfigError(
                "invalid Forge configuration\n"
                "  name: project name is required "
                "(set `name` / `project.name` in the config, "
                "or pass it as `forge new <name>`)"
            )

        engine: str | None = None
        database = False
        if isinstance(self.database, str):
            database = True
            engine = self.database

        try:
            return ProjectDefinition(
                name=name,
                language=self.language,
                project_type=self.project_type,
                framework=self.framework,
                architecture=self.architecture,
                capabilities=Capabilities(
                    database=database,
                    database_engine=engine,
                    orm=self.orm,
                    migrations=self.migrations,
                    docker=self.docker,
                    testing=self.testing,
                    linting=self.linting,
                ),
            )
        except ValidationError as exc:
            raise ConfigError(_format_pydantic_error(exc)) from exc


def load_forge_config(path: Path) -> ForgeConfig:
    """Parse a YAML config file into ``ForgeConfig``."""
    config_path = path.expanduser()
    if not config_path.is_file():
        raise ConfigError(f"configuration file not found: {path}")

    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"invalid Forge configuration\n  cannot read {path}: {exc}"
        ) from exc

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigError(
            f"invalid Forge configuration\n  malformed YAML: {exc}"
        ) from exc

    if data is None:
        raise ConfigError("invalid Forge configuration\n  file is empty")
    if not isinstance(data, dict):
        raise ConfigError(
            "invalid Forge configuration\n  root value must be a mapping"
        )

    try:
        return ForgeConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(_format_pydantic_error(exc)) from exc


def definition_from_config(
    path: Path,
    *,
    cli_name: str | None = None,
) -> ProjectDefinition:
    """Load YAML config and map it to a ``ProjectDefinition``."""
    return load_forge_config(path).to_definition(cli_name=cli_name)


def _format_pydantic_error(exc: ValidationError) -> str:
    lines = ["invalid Forge configuration"]
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()) if x != "body")
        msg = err.get("msg", "invalid value")
        # Pydantic prefixes some messages with "Value error, "
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        lines.append(f"  {loc}: {msg}" if loc else f"  {msg}")
    return "\n".join(lines)
