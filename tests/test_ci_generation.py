"""Tests for GitHub Actions workflow generation (Forge 0.3 Phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import generate_project, resolve_plan


def _definition(
    *,
    framework: str = "fastapi",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    sql: str | None = None,
    nosql: str | None = None,
    migrations: bool = False,
    docker: bool = False,
    testing: bool = True,
    linting: bool = True,
    ci: str | None = "github-actions",
    name: str = "ci-app",
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


def _workflow(root: Path) -> Path:
    return root / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_emitted_when_selected(tmp_path: Path) -> None:
    result = generate_project(_definition(), base_dir=tmp_path)
    path = _workflow(result.destination)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "name: CI" in text
    assert "astral-sh/setup-uv@v5" in text
    assert "uv sync" in text
    assert "python-version: \"3.12\"" in text
    assert "uv run ruff check ." in text
    assert "uv run pytest -q" in text
    assert ".github/workflows/ci.yml" in result.files_written


def test_ci_workflow_absent_when_not_selected(tmp_path: Path) -> None:
    result = generate_project(_definition(ci=None), base_dir=tmp_path)
    assert not _workflow(result.destination).exists()
    assert not any(
        p.startswith(".github/") for p in result.files_written
    )


def test_ci_workflow_pytest_only(tmp_path: Path) -> None:
    result = generate_project(
        _definition(testing=True, linting=False, ci="github-actions"),
        base_dir=tmp_path,
    )
    text = _workflow(result.destination).read_text(encoding="utf-8")
    assert "uv run pytest -q" in text
    assert "ruff" not in text


def test_ci_workflow_ruff_only(tmp_path: Path) -> None:
    result = generate_project(
        _definition(testing=False, linting=True, ci="github-actions"),
        base_dir=tmp_path,
    )
    text = _workflow(result.destination).read_text(encoding="utf-8")
    assert "uv run ruff check ." in text
    assert "pytest" not in text


def test_ci_workflow_both_tools(tmp_path: Path) -> None:
    result = generate_project(
        _definition(testing=True, linting=True, ci="github-actions"),
        base_dir=tmp_path,
    )
    text = _workflow(result.destination).read_text(encoding="utf-8")
    assert "uv run ruff check ." in text
    assert "uv run pytest -q" in text
    # Ruff before tests (fail-fast lint).
    assert text.index("ruff check") < text.index("pytest")


@pytest.mark.parametrize(
    ("framework", "architecture"),
    [
        ("fastapi", ArchitectureStyle.SIMPLE),
        ("fastapi", ArchitectureStyle.CLEAN),
        ("django", ArchitectureStyle.MODULAR_MONOLITH),
        ("flask", ArchitectureStyle.SIMPLE),
    ],
)
def test_ci_workflow_cross_framework(
    tmp_path: Path,
    framework: str,
    architecture: ArchitectureStyle,
) -> None:
    sql = "sqlite" if framework == "django" else None
    result = generate_project(
        _definition(
            framework=framework,
            architecture=architecture,
            sql=sql,
            name=f"{framework}-ci",
        ),
        base_dir=tmp_path,
    )
    path = _workflow(result.destination)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "uv sync" in text
    assert "uv run pytest -q" in text
    assert "uv run ruff check ." in text


def test_ci_workflow_no_database_services_with_persistence(
    tmp_path: Path,
) -> None:
    result = generate_project(
        _definition(
            sql="postgresql",
            nosql="redis",
            migrations=True,
            docker=True,
            ci="github-actions",
        ),
        base_dir=tmp_path,
    )
    text = _workflow(result.destination).read_text(encoding="utf-8")
    lowered = text.lower()
    assert "postgres" not in lowered
    assert "mongodb" not in lowered
    assert "redis" not in lowered
    assert "image:" not in lowered
    assert "services:" not in lowered
    # App still generated with persistence — CI stays simple.
    assert (result.destination / "docker-compose.yml").is_file()


def test_shared_ci_template_exists_on_disk() -> None:
    from forge.generator.render import templates_root

    shared = (
        templates_root()
        / "python"
        / "_shared"
        / ".github"
        / "workflows"
        / "ci.yml.j2"
    )
    assert shared.is_file()


def test_resolve_plan_ci_still_required_for_emission() -> None:
    plan = resolve_plan(_definition(ci="github-actions"))
    assert plan.features.ci is True
    assert plan.features.ci_provider == "github-actions"
