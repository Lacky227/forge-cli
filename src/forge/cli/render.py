"""Rich-based presentation helpers."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from forge.core.definition import ProjectDefinition

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
            border_style="green",
            padding=(1, 1),
            expand=False,
        )
    )
    console.print()
    console.print(
        "[dim]Forge has enough information to generate this project.[/dim]"
    )
    console.print(
        "[dim]Generation is not implemented in this prototype.[/dim]"
    )
    console.print()


def print_cancelled() -> None:
    console.print("\n[yellow]Cancelled.[/yellow] No project definition was created.\n")


def print_error(message: str) -> None:
    console.print(f"\n[red]Error:[/red] {message}\n")
