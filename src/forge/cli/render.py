"""Rich-based presentation helpers."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from forge.core import catalog
from forge.core.definition import ProjectDefinition
from forge.generator.engine import GenerationResult

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


def print_generation_result(result: GenerationResult) -> None:
    definition = result.definition
    caps = definition.capabilities
    lines = Text()
    lines.append("✓ ", style="bold green")
    lines.append(definition.name, style="bold")
    lines.append("\n\n")
    lines.append(
        catalog.FRAMEWORK_LABELS.get(definition.framework, definition.framework)
    )
    lines.append("\n")
    lines.append(catalog.ARCHITECTURE_LABELS[definition.architecture])
    lines.append("\n")

    extras: list[str] = []
    if caps.database and caps.database_engine:
        extras.append(
            catalog.DATABASE_ENGINE_LABELS.get(
                caps.database_engine, caps.database_engine
            )
        )
        if caps.orm:
            extras.append(caps.orm)
        if caps.migrations:
            extras.append("Alembic")
    if caps.docker:
        extras.append("Docker")
    if caps.testing:
        extras.append("pytest")
    if caps.linting:
        extras.append("Ruff")
    if extras:
        lines.append(" · ".join(extras), style="dim")

    console.print(
        Panel(
            lines,
            title="[bold]Project created[/bold]",
            border_style="green",
            padding=(1, 2),
            expand=False,
        )
    )
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print()
    for step in result.next_steps():
        console.print(f"  [cyan]{step}[/cyan]")
    console.print()


def print_cancelled() -> None:
    console.print(
        "\n[yellow]Cancelled.[/yellow] No project was created.\n"
    )


def print_error(message: str) -> None:
    console.print(f"\n[red]Error:[/red] {message}\n")
