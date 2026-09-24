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

from forge.core.definition import (
    AuthenticationOptions,
    Capabilities,
    ProjectDefinition,
    StorageOptions,
)
from forge.core.modules import normalize_modules
from forge.core.types import ArchitectureStyle, Language, ProjectType

_FALSEY_DATABASE = frozenset({"", "false", "none", "null", "no", "off"})


class ConfigError(Exception):
    """User-facing configuration error (file, YAML, or mapping)."""


class _ProjectSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None


class PersistenceConfig(BaseModel):
    """Structured persistence selection (SQL and NoSQL are independent)."""

    model_config = ConfigDict(extra="forbid")

    sql: str | None = None
    nosql: str | None = None

    @field_validator("sql", "nosql", mode="before")
    @classmethod
    def normalize_engine(cls, value: Any) -> str | None:
        if value is None or value is False:
            return None
        if value is True:
            raise ValueError("must be an engine name or null — not true")
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in _FALSEY_DATABASE:
                return None
            return cleaned
        raise ValueError("must be a string engine name, false, or null")


class ForgeConfig(BaseModel):
    """YAML-facing input model — maps to ``ProjectDefinition``.

    Field names favour a short human schema. Persistence may be expressed as:

    * modern: ``persistence: {sql: postgresql, nosql: redis}``
    * legacy SQL shorthand: ``database: postgresql``

    Specifying incompatible values in both forms is rejected.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    project: _ProjectSection | None = None
    name: str | None = None
    language: Language = Language.PYTHON
    project_type: ProjectType = Field(alias="type")
    framework: str
    architecture: ArchitectureStyle
    # Legacy SQL shorthand — engine string enables SQL; false/null/omitted = none.
    database: str | bool | None = None
    # Modern structured persistence (SQL and/or NoSQL).
    persistence: PersistenceConfig | None = None
    orm: str | None = None
    migrations: bool = False
    testing: bool = True
    linting: bool = True
    docker: bool = False
    # Optional CI provider — ``github-actions`` or omit/null for none.
    ci: str | None = None
    # Project modules (products, categories, files, …). Omit or [] for none.
    modules: list[str] = Field(default_factory=list)
    # Files storage options (only valid with the files module).
    storage: StorageOptions | None = None
    authentication: AuthenticationOptions | None = None

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

    @field_validator("persistence", mode="before")
    @classmethod
    def normalize_persistence(cls, value: Any) -> Any:
        if value is None or value is False:
            return None
        if value is True:
            raise ValueError(
                "persistence must be a mapping with sql/nosql keys, or null"
            )
        return value

    @field_validator("ci", mode="before")
    @classmethod
    def normalize_ci(cls, value: Any) -> str | None:
        if value is None or value is False:
            return None
        if value is True:
            raise ValueError(
                "ci must be a provider name (github-actions) or null — not true"
            )
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in _FALSEY_DATABASE:
                return None
            return cleaned
        raise ValueError("ci must be a string provider name, false, or null")

    @field_validator("modules", mode="before")
    @classmethod
    def normalize_modules_field(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raise TypeError("modules must be a list of module ids, not a string")
        if not isinstance(value, list):
            raise TypeError("modules must be a list of module ids")
        try:
            return list(normalize_modules(tuple(str(item) for item in value)))
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

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

    @model_validator(mode="after")
    def persistence_sources_must_agree(self) -> ForgeConfig:
        """Reject ambiguous legacy ``database`` + ``persistence`` combinations."""
        provided = self.model_fields_set
        if "database" not in provided or "persistence" not in provided:
            return self

        legacy = self.database if isinstance(self.database, str) else None
        pers = self.persistence

        if pers is None:
            if legacy is not None:
                raise ValueError(
                    "conflicting persistence: `database` selects SQL "
                    f"{legacy!r} but `persistence` is null"
                )
            return self

        if legacy is not None and pers.sql is not None and legacy != pers.sql:
            raise ValueError(
                "conflicting persistence: "
                f"`database`={legacy!r} and `persistence.sql`={pers.sql!r}"
            )
        if legacy is None and pers.sql is not None:
            raise ValueError(
                "conflicting persistence: `database` disables SQL but "
                f"`persistence.sql`={pers.sql!r}"
            )
        return self

    def resolved_config_name(self) -> str | None:
        if self.name and self.name.strip():
            return self.name.strip()
        if self.project and self.project.name and self.project.name.strip():
            return self.project.name.strip()
        return None

    def _resolved_sql(self) -> str | None:
        if self.persistence is not None and self.persistence.sql is not None:
            return self.persistence.sql
        if isinstance(self.database, str):
            return self.database
        return None

    def _resolved_nosql(self) -> str | None:
        if self.persistence is not None:
            return self.persistence.nosql
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

        sql = self._resolved_sql()
        nosql = self._resolved_nosql()

        try:
            return ProjectDefinition(
                name=name,
                language=self.language,
                project_type=self.project_type,
                framework=self.framework,
                architecture=self.architecture,
                capabilities=Capabilities(
                    sql_database=sql,
                    nosql_database=nosql,
                    orm=self.orm,
                    migrations=self.migrations,
                    docker=self.docker,
                    testing=self.testing,
                    linting=self.linting,
                    ci=self.ci,
                ),
                modules=tuple(self.modules),
                storage=self.storage,
                authentication=self.authentication,
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
        msg = msg.removeprefix("Value error, ")
        lines.append(f"  {loc}: {msg}" if loc else f"  {msg}")
    return "\n".join(lines)
