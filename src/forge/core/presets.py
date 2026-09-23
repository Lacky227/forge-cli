"""Named presets — compositions of valid explicit user choices.

A preset is **not** a generator. It expands into a ``ProjectDefinition`` that
then follows the normal ``resolve_plan()`` → generation path.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType


class PresetError(Exception):
    """User-facing preset error (unknown id, missing name, …)."""


@dataclass(frozen=True)
class Preset:
    """Catalog entry: stable id + human label + explicit definition fields.

    Does not include project name (CLI/config owns identity) or resolved
    GenerationPlan facts (ORM implications, migration system, DRF, …).
    """

    id: str
    title: str
    description: str
    framework: str
    architecture: ArchitectureStyle
    project_type: ProjectType = ProjectType.REST_API
    language: Language = Language.PYTHON
    sql_database: str | None = None
    nosql_database: str | None = None
    migrations: bool = False
    docker: bool = True
    testing: bool = True
    linting: bool = True
    ci: str | None = None

    def to_definition(self, *, name: str) -> ProjectDefinition:
        """Build a validated ``ProjectDefinition`` for ``name``."""
        try:
            return ProjectDefinition(
                name=name,
                language=self.language,
                project_type=self.project_type,
                framework=self.framework,
                architecture=self.architecture,
                capabilities=Capabilities(
                    sql_database=self.sql_database,
                    nosql_database=self.nosql_database,
                    # ORM left unset — resolve_plan implies framework defaults.
                    migrations=self.migrations,
                    docker=self.docker,
                    testing=self.testing,
                    linting=self.linting,
                    ci=self.ci,
                ),
            )
        except ValidationError as exc:
            raise PresetError(
                f"preset {self.id!r} is invalid:\n{_format_validation(exc)}"
            ) from exc


# Small curated set — meaningful compositions, not single-choice aliases.
PRESETS: tuple[Preset, ...] = (
    Preset(
        id="fastapi-postgres",
        title="FastAPI + PostgreSQL",
        description=(
            "FastAPI REST API with Modular Monolith layout, "
            "PostgreSQL, Alembic, Docker, pytest, and Ruff."
        ),
        framework="fastapi",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=True,
    ),
    Preset(
        id="fastapi-postgres-clean",
        title="FastAPI + PostgreSQL (Clean)",
        description=(
            "FastAPI REST API with Clean Architecture, "
            "PostgreSQL, Alembic, Docker, pytest, and Ruff."
        ),
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        sql_database="postgresql",
        migrations=True,
    ),
    Preset(
        id="flask-postgres",
        title="Flask + PostgreSQL",
        description=(
            "Flask REST API with Modular Monolith layout, "
            "PostgreSQL, Alembic, Docker, pytest, and Ruff."
        ),
        framework="flask",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=True,
    ),
    Preset(
        id="django-postgres",
        title="Django + PostgreSQL",
        description=(
            "Django REST API with Modular Monolith layout, "
            "PostgreSQL, Docker, pytest, and Ruff "
            "(ORM, migrations, and DRF implied by the resolver)."
        ),
        framework="django",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        sql_database="postgresql",
        migrations=False,
    ),
    Preset(
        id="fastapi-mongo",
        title="FastAPI + MongoDB",
        description=(
            "FastAPI REST API with Modular Monolith layout, "
            "MongoDB (PyMongo), Docker, pytest, and Ruff."
        ),
        framework="fastapi",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        nosql_database="mongodb",
        migrations=False,
    ),
)

_BY_ID: dict[str, Preset] = {preset.id: preset for preset in PRESETS}


def list_presets() -> tuple[Preset, ...]:
    """Return the catalog in declaration order."""
    return PRESETS


def get_preset(preset_id: str) -> Preset:
    """Look up a preset by stable identifier."""
    key = preset_id.strip().lower()
    preset = _BY_ID.get(key)
    if preset is None:
        listing = "\n".join(f"  {p.id}" for p in PRESETS) or "  (none)"
        raise PresetError(
            f"unknown preset {preset_id!r}.\nAvailable presets:\n{listing}"
        )
    return preset


def definition_from_preset(
    preset_id: str,
    *,
    name: str | None,
) -> ProjectDefinition:
    """Resolve a preset into a validated ``ProjectDefinition``.

    Presets do not own the project name — the CLI name argument is required.
    """
    preset = get_preset(preset_id)
    cleaned = name.strip() if name and name.strip() else None
    if not cleaned:
        raise PresetError(
            "project name is required when using --preset "
            "(example: forge new my-api --preset fastapi-postgres)"
        )
    return preset.to_definition(name=cleaned)


def _format_validation(exc: ValidationError) -> str:
    lines: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        msg = err.get("msg", "invalid value")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        lines.append(f"  {loc}: {msg}" if loc else f"  {msg}")
    return "\n".join(lines) if lines else str(exc)
