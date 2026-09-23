"""Rich-based presentation helpers."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from forge.core import catalog
from forge.core.definition import ProjectDefinition
from forge.generator.engine import GenerationPreview, GenerationResult
from forge.generator.plan import GenerationPlan

console = Console()


def print_banner() -> None:
    title = Text()
    title.append("⚒  FORGE", style="bold cyan")
    title.append("\n")
    title.append("Build your architecture.", style="dim")
    console.print(
        Panel(
            title,
            border_style="cyan",
            padding=(1, 4),
            expand=False,
        )
    )
    console.print()


def print_definition(definition: ProjectDefinition) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim", justify="right")
    table.add_column(style="bold")

    for label, value in definition.to_display_dict().items():
        table.add_row(f"{label}:", str(value))

    console.print()
    console.print(
        Panel(
            table,
            title="[bold]Project Definition[/bold]",
            border_style="cyan",
            padding=(1, 1),
            expand=False,
        )
    )
    console.print()


def print_generation_result(
    result: GenerationResult,
    *,
    preset_title: str | None = None,
) -> None:
    """Print a concise success summary from the resolved plan."""
    console.print()
    console.print(
        f"[bold green]✓[/bold green] Created [bold]{result.definition.name}[/bold]"
    )
    console.print()
    console.print("[bold]Location:[/bold]")
    console.print(f"  {_format_location(result.destination)}")
    if preset_title:
        console.print()
        console.print("[bold]Preset:[/bold]")
        console.print(f"  {preset_title}")
    console.print()
    console.print("[bold]Stack:[/bold]")
    for line in _stack_lines(result.plan):
        console.print(f"  {line}")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    for step in result.next_steps():
        console.print(f"  [cyan]{step}[/cyan]")
    console.print()


def print_generation_preview(
    preview: GenerationPreview,
    *,
    preset_title: str | None = None,
) -> None:
    """Print a dry-run preview: destination, files, and informational next steps."""
    plan = preview.plan
    features = plan.features

    console.print()
    console.print(
        Panel(
            Text("Dry run — no files will be written", style="bold"),
            border_style="yellow",
            padding=(0, 2),
            expand=False,
        )
    )

    console.print()
    console.print("[bold]Project[/bold]")
    console.print(f"  Name: {plan.definition.name}")
    console.print(f"  Destination: {preview.destination}")
    if preset_title:
        console.print(f"  Preset: {preset_title}")

    console.print()
    console.print("[bold]Stack[/bold]")
    for line in _stack_lines(plan):
        console.print(f"  {line}")
    if features.docker:
        console.print("  Docker")
    if features.ci_provider:
        label = catalog.CI_PROVIDER_LABELS.get(
            features.ci_provider, features.ci_provider
        )
        console.print(f"  CI: {label}")

    console.print()
    console.print("[bold]Files[/bold]")
    for path in preview.files:
        console.print(f"  {path}")

    deps = list(plan.runtime_dependencies) + list(plan.dev_dependencies)
    if deps:
        console.print()
        console.print("[bold]Dependencies[/bold]")
        for dep in deps:
            console.print(f"  {dep}")

    if plan.docker_services:
        console.print()
        console.print("[bold]Docker services[/bold]")
        console.print(f"  {', '.join(plan.docker_services)}")

    if plan.environment_variables:
        console.print()
        console.print("[bold]Environment[/bold]")
        for var in plan.environment_variables:
            console.print(f"  {var.name}")

    console.print()
    console.print(f"[bold]HTTP[/bold]  GET {plan.health_path}")

    console.print()
    console.print("[bold]Next steps[/bold] [dim](informational — not executed)[/dim]")
    for step in preview.next_steps():
        console.print(f"  [cyan]{step}[/cyan]")
    console.print()


def print_generation_plan(plan: GenerationPlan) -> None:
    """Print a resolved GenerationPlan without generating files."""
    console.print()
    console.print(
        Panel(
            Text("Resolved from ProjectDefinition → resolve_plan()", style="dim"),
            title="[bold]Forge Generation Plan[/bold]",
            border_style="cyan",
            padding=(0, 2),
            expand=False,
        )
    )
    for section in plan.summary_sections():
        console.print()
        console.print(f"[bold]{section.title}[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim", justify="right")
        table.add_column()
        for label, value in section.rows:
            table.add_row(f"{label}:", value)
        console.print(table)
    console.print()


def print_cancelled() -> None:
    console.print("\n[yellow]Cancelled.[/yellow]\n")


def print_error(message: str) -> None:
    console.print(f"\n[red]Error:[/red] {message}\n")


def _format_location(destination: Path) -> str:
    resolved = destination.resolve()
    try:
        relative = resolved.relative_to(Path.cwd().resolve())
    except ValueError:
        return str(resolved)
    text = relative.as_posix()
    return f"./{text}" if text != "." else "."


def _stack_lines(plan: GenerationPlan) -> list[str]:
    """Human-readable stack summary derived from the GenerationPlan."""
    features = plan.features
    caps = plan.definition.capabilities
    lines = [plan.framework_label, plan.architecture_label]

    if features.database and caps.sql_database:
        lines.append(
            catalog.SQL_DATABASE_LABELS.get(
                caps.sql_database, caps.sql_database
            )
        )
    if features.orm == "django-orm":
        lines.append("Django ORM")
    elif features.orm == "sqlalchemy":
        lines.append("SQLAlchemy")
    elif features.orm:
        lines.append(features.orm)

    if features.migration_system == "django":
        lines.append("Django migrations")
    elif features.migration_system == "alembic":
        lines.append("Alembic")

    if features.nosql and caps.nosql_database:
        lines.append(
            catalog.NOSQL_DATABASE_LABELS.get(
                caps.nosql_database, caps.nosql_database
            )
        )
        if features.nosql_client:
            lines.append(features.nosql_client)

    if features.rest_framework:
        lines.append("Django REST Framework")

    return lines
