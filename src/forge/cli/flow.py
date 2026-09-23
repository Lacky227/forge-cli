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
from forge.core.definition import Capabilities, ProjectDefinition, StorageOptions
from forge.core.modules import (
    MODULE_ORDER,
    MODULE_SPECS,
    STORAGE_BACKEND_LABELS,
    ModuleId,
    StorageBackend,
    expand_module_dependencies,
    implied_modules,
    modules_require_redis,
    modules_require_sql,
)
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


def _checkbox(message: str, choices: list[Choice]) -> list[str]:
    result = questionary.checkbox(
        message,
        choices=choices,
        style=_STYLE,
        instruction="(space to toggle, enter to confirm)",
    ).ask()
    return list(_require(result))


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

    modules = _collect_modules()
    # Announce implied modules / Redis *before* persistence prompts so the
    # user can choose NoSQL Redis knowingly when jobs need it.
    _announce_early_module_implications(modules)
    capabilities = _collect_capabilities(
        framework,
        project_type,
        modules=modules,
    )
    storage = _collect_storage_options(modules, docker=capabilities.docker)
    _announce_redis_resolution(modules, capabilities)
    return ProjectDefinition(
        name=name,
        language=language,
        project_type=project_type,
        framework=framework,
        architecture=architecture,
        capabilities=capabilities,
        modules=tuple(modules),
        storage=storage,
    )


def _collect_modules() -> list[str]:
    """Multi-select project modules (optional)."""
    selected = _checkbox(
        "Project modules (optional)",
        [
            Choice(
                title=f"{MODULE_SPECS[mid].label} — {MODULE_SPECS[mid].description}",
                value=mid.value,
            )
            for mid in MODULE_ORDER
        ],
    )
    if not selected:
        _console.print("[dim]Modules:[/dim] none")
    else:
        labels = ", ".join(
            MODULE_SPECS[m].label
            for m in MODULE_ORDER
            if m.value in selected
        )
        _console.print(f"[dim]Modules:[/dim] {labels}")
    return selected


def _collect_storage_options(
    modules: list[str],
    *,
    docker: bool,
) -> StorageOptions | None:
    """Ask Files-only storage questions (after Docker is known)."""
    if ModuleId.FILES.value not in modules:
        return None
    backend = _select(
        "Storage backend",
        [
            Choice(
                title=STORAGE_BACKEND_LABELS[StorageBackend.LOCAL.value],
                value=StorageBackend.LOCAL.value,
            ),
            Choice(
                title=STORAGE_BACKEND_LABELS[StorageBackend.S3.value],
                value=StorageBackend.S3.value,
            ),
        ],
    )
    minio = False
    if backend == StorageBackend.S3.value and docker:
        minio = _confirm("Add MinIO for local development?", default=True)
    return StorageOptions(backend=backend, minio=minio)


def _announce_early_module_implications(modules: list[str]) -> None:
    """Surface dependency implications before capability questions."""
    expanded = expand_module_dependencies(tuple(modules))
    implied = implied_modules(tuple(modules), expanded)
    if implied:
        labels = ", ".join(MODULE_SPECS[ModuleId(m)].label for m in implied)
        causes: list[str] = []
        if ModuleId.WEBHOOKS.value in modules:
            causes.append("Webhooks")
        note = f" [dim](required by {', '.join(causes)})[/dim]" if causes else ""
        _console.print(f"[dim]Implied modules:[/dim] {labels}{note}")
    if modules_require_redis(tuple(modules)):
        _console.print(
            "[dim]Redis:[/dim] required for Background Jobs / RQ "
            "[dim](select as NoSQL to reuse, or Forge adds infrastructure Redis)"
            "[/dim]"
        )


def _announce_redis_resolution(
    modules: list[str],
    capabilities: Capabilities,
) -> None:
    """Confirm Redis reuse vs infrastructure after NoSQL is known."""
    if not modules_require_redis(tuple(modules)):
        return
    if capabilities.nosql_database == "redis":
        _console.print(
            "[dim]Redis:[/dim] reusing selected NoSQL Redis "
            "[dim](Background Jobs)[/dim]"
        )
    else:
        _console.print(
            "[dim]Redis:[/dim] required infrastructure "
            "[dim](Background Jobs / RQ)[/dim]"
        )


def _collect_capabilities(
    framework: str,
    project_type: ProjectType,
    *,
    modules: list[str] | None = None,
) -> Capabilities:
    """Ask only user-selectable capability questions.

    Framework-implied details (Django ORM/migrations/DRF; SQLAlchemy for
    FastAPI/Flask when SQL is selected) are not stored here —
    ``resolve_plan`` fills them in.
    """
    sql_database: str | None = None
    nosql_database: str | None = None
    migrations = False
    selected_modules = tuple(modules or ())
    require_sql = modules_require_sql(selected_modules)

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
        if require_sql:
            _console.print(
                "[dim]SQL persistence required by selected modules.[/dim]"
            )
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
            if catalog.supports_nosql(framework) and _confirm(
                "Also add a NoSQL database?", default=False
            ):
                nosql_database = _select_nosql_database()
                _print_nosql_client_note(nosql_database)
        elif _confirm("Add a database?", default=True):
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

    ci: str | None = None
    if testing or linting:
        ci_choice = _select(
            "Add CI?",
            [
                Choice(title="GitHub Actions", value="github-actions"),
                Choice(title="No", value="none"),
            ],
        )
        if ci_choice != "none":
            ci = ci_choice

    return Capabilities(
        sql_database=sql_database,
        nosql_database=nosql_database,
        migrations=migrations,
        docker=docker,
        testing=testing,
        linting=linting,
        ci=ci,
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
