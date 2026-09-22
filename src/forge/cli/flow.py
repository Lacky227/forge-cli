"""Adaptive interactive flow → ProjectDefinition.

Uses questionary for prompts. Domain validation lives in ProjectDefinition;
this module only asks relevant questions and maps answers to the model.
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
    database = False
    database_engine: str | None = None
    orm: str | None = None
    migrations = False

    if framework == "django":
        # Django REST API projects always use Django ORM + Django migrations.
        database = True
        database_engine = _select(
            "Database engine",
            [
                Choice(
                    title=catalog.DATABASE_ENGINE_LABELS[engine],
                    value=engine,
                )
                for engine in catalog.DATABASE_ENGINES
            ],
        )
        orm = catalog.default_orm_for(framework)
        migrations = True
        _console.print("[dim]ORM:[/dim] Django ORM")
        _console.print("[dim]Migrations:[/dim] Django migrations")
        if project_type is ProjectType.REST_API:
            _console.print(
                "[dim]API:[/dim] Django REST Framework "
                "[dim](required for REST API)[/dim]"
            )
    elif catalog.supports_database(framework):
        database = _confirm("Include a database?", default=True)
        if database:
            database_engine = _select(
                "Database engine",
                [
                    Choice(
                        title=catalog.DATABASE_ENGINE_LABELS[engine],
                        value=engine,
                    )
                    for engine in catalog.DATABASE_ENGINES
                ],
            )
            orm = catalog.default_orm_for(framework)
            if orm:
                _console.print(
                    f"[dim]ORM:[/dim] {orm} "
                    f"[dim](selected for "
                    f"{catalog.FRAMEWORK_LABELS.get(framework, framework)})[/dim]"
                )
            migrations = _confirm("Include Alembic migrations?", default=True)
    else:
        _console.print(
            "[dim]Database options skipped — not applicable for this framework.[/dim]"
        )

    docker = _confirm("Include Docker support?", default=True)
    testing = _confirm("Include testing setup (pytest)?", default=True)
    linting = _confirm("Include Ruff linting?", default=True)

    return Capabilities(
        database=database,
        database_engine=database_engine,
        orm=orm,
        migrations=migrations,
        docker=docker,
        testing=testing,
        linting=linting,
    )
