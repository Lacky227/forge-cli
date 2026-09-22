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
from forge.core.config import ConfigError, definition_from_config
from forge.core.presets import Preset, PresetError, definition_from_preset, get_preset
from forge.generator import GenerationError, generate_project

app = typer.Typer(
    name="forge",
    help=(
        "Design and generate application architectures.\n\n"
        "Run [bold]forge new[/bold] to create a project interactively, "
        "or pass [bold]--preset[/bold] / [bold]--config[/bold] "
        "for non-interactive generation."
    ),
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
    """Forge — build your architecture.

    Running [bold]forge[/bold] with no command shows this help.
    """


@app.command("new")
def new_command(
    name: str | None = typer.Argument(
        None,
        help=(
            "Project directory name under the current working directory "
            "(creates [bold]./<name>[/bold]). "
            "Prompted if omitted unless [bold]--config[/bold] provides a name; "
            "required with [bold]--preset[/bold]."
        ),
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help=(
            "YAML config file. Skips interactive prompts "
            "(required fields must be present). "
            "Cannot be combined with [bold]--preset[/bold]."
        ),
        show_default=False,
    ),
    preset: str | None = typer.Option(
        None,
        "--preset",
        "-p",
        help=(
            "Named stack preset (non-interactive). "
            "Cannot be combined with [bold]--config[/bold]."
        ),
        show_default=False,
    ),
) -> None:
    """Generate a project interactively, from a preset, or from YAML config.

    Interactive mode asks only questions that affect the generated project.
    With [bold]--preset[/bold] or [bold]--config[/bold], generation is
    fully non-interactive.
    """
    try:
        _run_new(name=name, config=config, preset=preset)
    except FlowCancelled:
        print_cancelled()
        raise typer.Exit(code=1) from None
    except KeyboardInterrupt:
        print_cancelled()
        raise typer.Exit(code=1) from None


def _run_new(
    *,
    name: str | None,
    config: Path | None,
    preset: str | None,
) -> None:
    print_banner()
    used_preset: Preset | None = None
    try:
        if config is not None and preset is not None:
            raise PresetError("--preset and --config cannot be used together.")
        if preset is not None:
            definition = definition_from_preset(preset, name=name)
            used_preset = get_preset(preset)
        elif config is not None:
            definition = definition_from_config(config, cli_name=name)
        else:
            definition = run_new_flow(name=name)
    except (ConfigError, PresetError) as exc:
        print_error(str(exc))
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
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from None

    print_generation_result(
        result,
        preset_title=used_preset.title if used_preset else None,
    )


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
