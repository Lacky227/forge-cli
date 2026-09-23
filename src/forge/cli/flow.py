"""Adaptive interactive flow → ProjectDefinition.

Uses questionary for prompts. Domain validation lives in ProjectDefinition;
framework implications live in ``resolve_plan``. This module only asks
questions that affect the generated project.
"""

from __future__ import annotations

from typing import TypeVar

import questionary
from questionary import Choice, Style
from rich.console import Console

from forge.core import catalog
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType

T = TypeVar("T")

_STYLE = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("answer", "fg:cyan bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("instruction", "fg:darkgray"),
    ]
)

_console = Console(stderr=True)


class FlowCancelled(Exception):
    """User cancelled an interactive prompt (e.g. Ctrl+C / Esc)."""


def _require(value: T | None) -> T:
    if value is None:
        raise FlowCancelled
    return value


def _select(message: str, choices: list[Choice]) -> str:
    result = questionary.select(
        message,
        choices=choices,
        style=_STYLE,
        instruction="(use arrow keys)",
    ).ask()
    return _require(result)


def _confirm(message: str, default: bool = True) -> bool:
    result = questionary.confirm(message, default=default, style=_STYLE).ask()
    return _require(result)


def _text(message: str, default: str = "") -> str:
    result = questionary.text(
        message,
        default=default,
        style=_STYLE,
        validate=lambda text: True
        if text.strip()
        else "Please enter a project name",
    ).ask()
    return _require(result).strip()


def run_new_flow(name: str | None = None) -> ProjectDefinition:
    """Run the adaptive interview and return a validated ProjectDefinition."""

    if name is None or not name.strip():
        name = _text("Project name:", default="my-project")
    else:
        name = name.strip()
        _console.print(f"[dim]Project name:[/dim] {name}")

    project_type = ProjectType(
        _select(
            "What are you building?",
            [
                Choice(title=label, value=value.value)
                for value, label in catalog.PROJECT_TYPE_LABELS.items()
            ],
        )
    )

    language = Language(
        _select(
            "Language",
            [
                Choice(title=label, value=value.value)
                for value, label in catalog.LANGUAGE_LABELS.items()
            ],
        )
    )

    framework_options = catalog.frameworks_for(language, project_type)
    if not framework_options:
        raise ValueError(
            f"No frameworks available for {language.value} / {project_type.value}"
        )

    framework = _select(
        "Framework",
        [
            Choice(
                title=catalog.FRAMEWORK_LABELS.get(fw, fw),
                value=fw,
            )
            for fw in framework_options
        ],
    )

    architecture_options = catalog.architectures_for(project_type)
    if len(architecture_options) == 1:
        architecture = architecture_options[0]
        _console.print(
            f"[dim]Architecture:[/dim] "
            f"{catalog.ARCHITECTURE_LABELS[architecture]} "
            f"[dim](only option for this project type)[/dim]"
        )
    else:
        architecture = ArchitectureStyle(
            _select(
                "Architecture",
                [
                    Choice(
                        title=catalog.ARCHITECTURE_LABELS[style],
                        value=style.value,
                    )
                    for style in architecture_options
                ],
            )
        )

    capabilities = _collect_capabilities(framework, project_type)
    return ProjectDefinition(
        name=name,
        language=language,
        project_type=project_type,
        framework=framework,
        architecture=architecture,
        capabilities=capabilities,
    )


def _collect_capabilities(
    framework: str,
    project_type: ProjectType,
) -> Capabilities:
    """Ask only user-selectable capability questions.

    Framework-implied details (Django ORM/migrations/DRF; SQLAlchemy for
    FastAPI/Flask when SQL is selected) are not stored here —
    ``resolve_plan`` fills them in.
    """
    sql_database: str | None = None
    nosql_database: str | None = None
    migrations = False

    if framework == "django":
        # SQL is required for Django REST API; NoSQL is optional.
        sql_database = _select_sql_database()
        _console.print("[dim]ORM:[/dim] Django ORM")
        _console.print("[dim]Migrations:[/dim] Django migrations")
        if project_type is ProjectType.REST_API:
            _console.print(
                "[dim]API:[/dim] Django REST Framework "
                "[dim](required for REST API)[/dim]"
            )
        if catalog.supports_nosql(framework) and _confirm(
            "Also add a NoSQL database?", default=False
        ):
            nosql_database = _select_nosql_database()
            _print_nosql_client_note(nosql_database)
    elif catalog.supports_sql(framework) or catalog.supports_nosql(framework):
        if _confirm("Add a database?", default=True):
            db_kind = _select(
                "Database type",
                [
                    Choice(title="SQL", value="sql"),
                    Choice(title="NoSQL", value="nosql"),
                    Choice(title="Both", value="both"),
                ],
            )
            if db_kind in {"sql", "both"}:
                sql_database = _select_sql_database()
                implied_orm = catalog.default_orm_for(framework)
                if implied_orm:
                    label = (
                        "SQLAlchemy"
                        if implied_orm == "sqlalchemy"
                        else implied_orm
                    )
                    _console.print(
                        f"[dim]ORM:[/dim] {label} "
                        f"[dim](selected for "
                        f"{catalog.FRAMEWORK_LABELS.get(framework, framework)})"
                        f"[/dim]"
                    )
                migrations = _confirm(
                    "Include Alembic migrations?", default=True
                )
            if db_kind in {"nosql", "both"}:
                nosql_database = _select_nosql_database()
                _print_nosql_client_note(nosql_database)
    else:
        _console.print(
            "[dim]Database options skipped — not applicable for this framework.[/dim]"
        )

    docker = _confirm("Include Docker support?", default=True)
    testing = _confirm("Include testing setup (pytest)?", default=True)
    linting = _confirm("Include Ruff linting?", default=True)

    return Capabilities(
        sql_database=sql_database,
        nosql_database=nosql_database,
        migrations=migrations,
        docker=docker,
        testing=testing,
        linting=linting,
    )


def _select_sql_database() -> str:
    return _select(
        "SQL database",
        [
            Choice(
                title=catalog.SQL_DATABASE_LABELS[engine],
                value=engine,
            )
            for engine in catalog.SQL_DATABASES
        ],
    )


def _select_nosql_database() -> str:
    return _select(
        "NoSQL database",
        [
            Choice(
                title=catalog.NOSQL_DATABASE_LABELS[engine],
                value=engine,
            )
            for engine in catalog.NOSQL_DATABASES
        ],
    )


def _print_nosql_client_note(nosql_database: str) -> None:
    client = catalog.nosql_client_for(nosql_database)
    if client == "pymongo":
        _console.print(
            "[dim]Client:[/dim] pymongo "
            "[dim](official MongoDB Python driver)[/dim]"
        )
    elif client == "redis":
        _console.print(
            "[dim]Client:[/dim] redis "
            "[dim](official Redis Python client)[/dim]"
        )
