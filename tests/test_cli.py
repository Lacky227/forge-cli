"""Public CLI contract tests for ``forge`` / ``forge new``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from forge import __version__
from forge.cli.app import app
from forge.cli.flow import FlowCancelled
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType

runner = CliRunner()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _minimal_config(
    tmp_path: Path,
    *,
    name: str = "demo-api",
    framework: str = "flask",
    extra: str = "database: false\ndocker: false\n",
) -> Path:
    return _write(
        tmp_path,
        "forge.yaml",
        f"""
name: {name}
type: rest-api
framework: {framework}
architecture: simple
{extra}
""",
    )


def test_forge_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Design and generate" in result.output
    assert "new" in result.output
    assert "--version" in result.output


def test_forge_new_help() -> None:
    result = runner.invoke(app, ["new", "--help"])
    assert result.exit_code == 0
    assert "--config" in result.output
    assert "-c" in result.output
    assert "YAML" in result.output or "config" in result.output.lower()


def test_forge_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"forge {__version__}" in result.output
    assert result.output.strip() == f"forge {__version__}"


def test_forge_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "new" in result.output


def test_config_generation_no_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _minimal_config(tmp_path, name="cfg-cli")
    monkeypatch.chdir(tmp_path)
    with patch("forge.cli.app.run_new_flow") as interactive:
        result = runner.invoke(app, ["new", "--config", str(config)])
    assert result.exit_code == 0, result.output
    interactive.assert_not_called()
    assert (tmp_path / "cfg-cli").is_dir()
    assert "Created" in result.output
    assert "cfg-cli" in result.output
    assert "Location:" in result.output
    assert "Stack:" in result.output
    assert "Next steps:" in result.output


def test_cli_name_overrides_config_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _minimal_config(tmp_path, name="from-config")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "from-cli", "--config", str(config)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "from-cli").is_dir()
    assert not (tmp_path / "from-config").exists()
    assert "from-cli" in result.output


def test_missing_config_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "--config", "missing.yaml"])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "configuration file not found" in result.output
    assert "Traceback" not in result.output


def test_invalid_config_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(
        tmp_path,
        "bad.yaml",
        """
name: x
type: rest-api
framework: fastapi
architecture: spaceship
""",
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "--config", str(config)])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "architecture" in result.output
    assert "Traceback" not in result.output


def test_unsupported_combination_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(
        tmp_path,
        "bad.yaml",
        """
name: bad-combo
type: rest-api
framework: django
architecture: simple
database: postgresql
orm: sqlalchemy
""",
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "--config", str(config)])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output
    # Fails at config→definition validation (django + sqlalchemy)
    assert "django-orm" in result.output or "SQLAlchemy" in result.output


def test_destination_conflict_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _minimal_config(tmp_path, name="taken")
    existing = tmp_path / "taken"
    existing.mkdir()
    (existing / "marker.txt").write_text("keep", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "--config", str(config)])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "already exists" in result.output
    assert "Traceback" not in result.output
    assert (existing / "marker.txt").read_text(encoding="utf-8") == "keep"


def test_empty_destination_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _minimal_config(tmp_path, name="empty-ok")
    (tmp_path / "empty-ok").mkdir()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "--config", str(config)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "empty-ok" / "pyproject.toml").is_file()


def test_cancellation_exits_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with patch("forge.cli.app.run_new_flow", side_effect=FlowCancelled):
        result = runner.invoke(app, ["new", "cancelled-app"])
    assert result.exit_code == 1
    assert "Cancelled." in result.output
    assert "Traceback" not in result.output
    assert not (tmp_path / "cancelled-app").exists()


def test_keyboard_interrupt_exits_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with patch("forge.cli.app.run_new_flow", side_effect=KeyboardInterrupt):
        result = runner.invoke(app, ["new", "interrupted"])
    assert result.exit_code == 1
    assert "Cancelled." in result.output
    assert "Traceback" not in result.output


def test_interactive_path_still_generates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interactive entry still reaches generation when the flow returns a definition."""
    definition = ProjectDefinition(
        name="interactive-demo",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities(
            database=False,
            docker=False,
            testing=True,
            linting=False,
        ),
    )
    monkeypatch.chdir(tmp_path)
    with patch("forge.cli.app.run_new_flow", return_value=definition):
        result = runner.invoke(app, ["new", "interactive-demo"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "interactive-demo").is_dir()
    assert (
        tmp_path / "interactive-demo" / "src" / "interactive_demo" / "main.py"
    ).is_file()
