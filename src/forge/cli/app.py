"""Typer application entrypoint."""

from __future__ import annotations

import typer
from pydantic import ValidationError

from forge import __version__
from forge.cli.flow import FlowCancelled, run_new_flow
from forge.cli.render import (
    print_banner,
    print_cancelled,
    print_definition,
    print_error,
)

app = typer.Typer(
    name="forge",
    help="Interactively design and generate application architectures.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"forge {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Forge — build your architecture."""


@app.command("new")
def new_command(
    name: str | None = typer.Argument(
        None,
        help="Project name. Prompted interactively if omitted.",
    ),
) -> None:
    """Interview for a project definition (generation not implemented yet)."""
    print_banner()
    try:
        definition = run_new_flow(name=name)
    except FlowCancelled:
        print_cancelled()
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from None

    print_definition(definition)
    # Future: pass `definition` into the generation engine here.


def main() -> None:
    app()


if __name__ == "__main__":
    main()
