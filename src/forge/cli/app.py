"""Typer application entrypoint."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError

from forge import __version__
from forge.cli.flow import FlowCancelled, run_new_flow
from forge.cli.render import (
    print_banner,
    print_cancelled,
    print_definition,
    print_error,
    print_generation_result,
)
from forge.generator import GenerationError, generate_project

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
        help="Project name. Creates ./<name>. Prompted if omitted.",
    ),
) -> None:
    """Interview for a project definition and generate the project."""
    print_banner()
    try:
        definition = run_new_flow(name=name)
    except FlowCancelled:
        print_cancelled()
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        print_error(_format_validation_error(exc))
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from None

    print_definition(definition)

    try:
        result = generate_project(definition, base_dir=Path.cwd())
    except GenerationError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from None

    print_generation_result(result)


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        msg = err.get("msg", "invalid value")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts) if parts else str(exc)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
