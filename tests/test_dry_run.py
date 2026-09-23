"""Phase 4: forge new --dry-run preview and planned-output parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.cli.app import app
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import (
    GenerationError,
    generate_project,
    planned_output_paths,
    preview_project,
    resolve_plan,
)
from forge.generator.engine import next_steps_for
from tests.cli_testing import invoke_cli, plain_output


def _def(
    *,
    name: str = "dry-app",
    framework: str = "fastapi",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    sql: str | None = None,
    nosql: str | None = None,
    migrations: bool = False,
    docker: bool = False,
    testing: bool = True,
    linting: bool = True,
    ci: str | None = None,
) -> ProjectDefinition:
    return ProjectDefinition(
        name=name,
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework=framework,
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=sql,
            nosql_database=nosql,
            migrations=migrations and sql is not None,
            docker=docker,
            testing=testing,
            linting=linting,
            ci=ci,
        ),
    )


def test_planned_outputs_match_real_generation(tmp_path: Path) -> None:
    definition = _def(
        name="parity-app",
        sql="postgresql",
        nosql="redis",
        migrations=True,
        docker=True,
        ci="github-actions",
    )
    planned = planned_output_paths(resolve_plan(definition))
    result = generate_project(definition, base_dir=tmp_path)
    assert planned == result.files_written
    assert ".github/workflows/ci.yml" in planned
    assert ".env.example" in planned
    assert "Dockerfile" in planned
    assert "docker-compose.yml" in planned
    assert not any("_includes" in p for p in planned)
    assert not any(p.endswith(".j2") for p in planned)


@pytest.mark.parametrize(
    ("framework", "architecture"),
    [
        ("fastapi", ArchitectureStyle.SIMPLE),
        ("fastapi", ArchitectureStyle.MODULAR_MONOLITH),
        ("fastapi", ArchitectureStyle.CLEAN),
        ("flask", ArchitectureStyle.SIMPLE),
        ("flask", ArchitectureStyle.MODULAR_MONOLITH),
        ("flask", ArchitectureStyle.CLEAN),
        ("django", ArchitectureStyle.SIMPLE),
        ("django", ArchitectureStyle.MODULAR_MONOLITH),
        ("django", ArchitectureStyle.CLEAN),
    ],
)
def test_planned_outputs_match_for_architecture_matrix(
    tmp_path: Path,
    framework: str,
    architecture: ArchitectureStyle,
) -> None:
    sql = "sqlite" if framework == "django" else None
    definition = _def(
        name=f"{framework}-{architecture.value}",
        framework=framework,
        architecture=architecture,
        sql=sql,
    )
    planned = planned_output_paths(resolve_plan(definition))
    result = generate_project(definition, base_dir=tmp_path)
    assert planned == result.files_written


def test_capability_gating_in_planned_outputs() -> None:
    with_ci = planned_output_paths(
        resolve_plan(_def(ci="github-actions", sql="sqlite"))
    )
    without_ci = planned_output_paths(resolve_plan(_def(sql="sqlite")))
    assert ".github/workflows/ci.yml" in with_ci
    assert ".github/workflows/ci.yml" not in without_ci
    assert ".env.example" in with_ci

    bare = planned_output_paths(resolve_plan(_def()))
    assert ".env.example" not in bare
    assert ".github/workflows/ci.yml" not in bare

    with_docker = planned_output_paths(resolve_plan(_def(docker=True)))
    without_docker = planned_output_paths(resolve_plan(_def()))
    assert "Dockerfile" in with_docker
    assert "docker-compose.yml" in with_docker
    assert "Dockerfile" not in without_docker
    assert "docker-compose.yml" not in without_docker

    no_tests = planned_output_paths(
        resolve_plan(_def(testing=False, linting=True))
    )
    assert not any(p.startswith("tests/") for p in no_tests)


def test_preview_missing_destination_leaves_absent(tmp_path: Path) -> None:
    destination = tmp_path / "missing-app"
    assert not destination.exists()
    preview = preview_project(_def(name="missing-app"), base_dir=tmp_path)
    assert preview.destination == destination
    assert not destination.exists()
    assert preview.files
    assert preview.next_steps() == next_steps_for(
        preview.plan, destination_name="missing-app"
    )


def test_preview_empty_destination_untouched(tmp_path: Path) -> None:
    destination = tmp_path / "empty-app"
    destination.mkdir()
    assert list(destination.iterdir()) == []
    preview = preview_project(_def(name="empty-app"), base_dir=tmp_path)
    assert preview.destination == destination
    assert destination.is_dir()
    assert list(destination.iterdir()) == []


def test_preview_nonempty_destination_rejected(tmp_path: Path) -> None:
    destination = tmp_path / "busy-app"
    destination.mkdir()
    marker = destination / "keep-me.txt"
    marker.write_text("sentinel", encoding="utf-8")
    before = marker.read_bytes()
    with pytest.raises(GenerationError, match="not empty"):
        preview_project(_def(name="busy-app"), base_dir=tmp_path)
    assert marker.read_bytes() == before
    assert list(destination.iterdir()) == [marker]


def test_preview_file_destination_rejected(tmp_path: Path) -> None:
    target = tmp_path / "file-app"
    target.write_text("not a directory", encoding="utf-8")
    before = target.read_bytes()
    with pytest.raises(GenerationError, match="exists as a file"):
        preview_project(_def(name="file-app"), base_dir=tmp_path)
    assert target.is_file()
    assert target.read_bytes() == before


def test_cli_dry_run_preset_zero_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    result = invoke_cli(
        app,
        ["new", "demo-api", "--preset", "fastapi-postgres", "--dry-run"],
    )
    assert result.exit_code == 0, plain_output(result)
    out = plain_output(result)
    assert "Dry run" in out
    assert "no files will be written" in out
    assert "demo-api" in out
    assert "pyproject.toml" in out
    assert "Created" not in out
    assert set(tmp_path.iterdir()) == before
    assert not (tmp_path / "demo-api").exists()


def test_cli_dry_run_config_combined_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "forge.yml"
    config.write_text(
        """
name: combo-api
type: rest-api
framework: fastapi
architecture: clean
persistence:
  sql: postgresql
  nosql: redis
migrations: true
docker: true
testing: true
linting: true
ci: github-actions
""",
        encoding="utf-8",
    )
    before = {p.name for p in tmp_path.iterdir()}
    result = invoke_cli(app, ["new", "--config", str(config), "--dry-run"])
    assert result.exit_code == 0, plain_output(result)
    out = plain_output(result)
    assert ".github/workflows/ci.yml" in out
    assert ".env.example" in out
    assert "Dockerfile" in out
    assert "docker compose up -d db redis" in out
    assert not (tmp_path / "combo-api").exists()
    assert {p.name for p in tmp_path.iterdir()} == before


def test_cli_dry_run_rejects_nonempty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    dest = tmp_path / "taken"
    dest.mkdir()
    (dest / "existing.txt").write_text("x", encoding="utf-8")
    result = invoke_cli(
        app,
        ["new", "taken", "--preset", "fastapi-postgres", "--dry-run"],
    )
    assert result.exit_code == 1
    assert "not empty" in plain_output(result)
    assert (dest / "existing.txt").read_text(encoding="utf-8") == "x"


def test_cli_new_help_mentions_dry_run() -> None:
    result = invoke_cli(app, ["new", "--help"])
    assert result.exit_code == 0
    assert "--dry-run" in plain_output(result)
