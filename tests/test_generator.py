"""Tests for the FastAPI generation engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import GenerationError, generate_project


def _fastapi_definition(
    *,
    name: str = "demo-api",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    database: bool = True,
    engine: str = "postgresql",
    migrations: bool = True,
    docker: bool = True,
    testing: bool = True,
    linting: bool = True,
) -> ProjectDefinition:
    caps = Capabilities(
        sql_database=engine if database else None,
        migrations=migrations and database,
        docker=docker,
        testing=testing,
        linting=linting,
    )
    return ProjectDefinition(
        name=name,
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=architecture,
        capabilities=caps,
    )


def test_generate_simple_fastapi(tmp_path: Path) -> None:
    result = generate_project(
        _fastapi_definition(architecture=ArchitectureStyle.SIMPLE),
        base_dir=tmp_path,
    )
    root = result.destination
    assert (root / "src" / "demo_api" / "main.py").is_file()
    assert (root / "src" / "demo_api" / "config.py").is_file()
    assert (root / "src" / "demo_api" / "database.py").is_file()
    assert not (root / "src" / "demo_api" / "api").exists()
    assert (root / "pyproject.toml").is_file()
    assert (root / "Dockerfile").is_file()
    assert (root / "docker-compose.yml").is_file()
    assert (root / "alembic.ini").is_file()
    assert (root / "migrations" / "env.py").is_file()
    assert (root / "tests" / "test_health.py").is_file()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "fastapi[standard]" in pyproject
    assert "sqlalchemy" in pyproject
    assert "psycopg" in pyproject
    assert "alembic" in pyproject
    assert "ruff" in pyproject


def test_generate_modular_differs_from_simple(tmp_path: Path) -> None:
    simple = generate_project(
        _fastapi_definition(name="simple-api", architecture=ArchitectureStyle.SIMPLE),
        base_dir=tmp_path,
    )
    modular = generate_project(
        _fastapi_definition(
            name="modular-api",
            architecture=ArchitectureStyle.MODULAR_MONOLITH,
        ),
        base_dir=tmp_path,
    )
    assert (modular.destination / "src" / "modular_api" / "api" / "routes").is_dir()
    assert (modular.destination / "src" / "modular_api" / "core" / "config.py").is_file()
    assert (modular.destination / "src" / "modular_api" / "services").is_dir()
    assert not (simple.destination / "src" / "simple_api" / "api").exists()
    assert (simple.destination / "src" / "simple_api" / "config.py").is_file()


def test_without_database_skips_db_artifacts(tmp_path: Path) -> None:
    result = generate_project(
        _fastapi_definition(database=False, migrations=False, docker=False),
        base_dir=tmp_path,
    )
    root = result.destination
    assert not (root / "src" / "demo_api" / "database.py").exists()
    assert not (root / "alembic.ini").exists()
    assert not (root / "migrations").exists()
    assert not (root / "Dockerfile").exists()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "sqlalchemy" not in pyproject


def test_refuses_nonempty_destination(tmp_path: Path) -> None:
    existing = tmp_path / "demo-api"
    existing.mkdir()
    (existing / "already.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(GenerationError, match="already exists"):
        generate_project(_fastapi_definition(), base_dir=tmp_path)


def test_unsupported_framework(tmp_path: Path) -> None:
    definition = ProjectDefinition.model_construct(
        name="future-app",
        language=Language.PYTHON,
        project_type=ProjectType.WORKER,
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities(testing=True, linting=False),
    )
    with pytest.raises(GenerationError, match="Cannot generate this project"):
        generate_project(definition, base_dir=tmp_path)


def test_invalid_plan_fails_before_filesystem(tmp_path: Path) -> None:
    definition = ProjectDefinition.model_construct(
        name="future-app",
        language=Language.PYTHON,
        project_type=ProjectType.WORKER,
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities(testing=True, linting=False),
    )
    with pytest.raises(GenerationError):
        generate_project(definition, base_dir=tmp_path)
    assert not (tmp_path / "future-app").exists()


def test_next_steps_include_fastapi_dev(tmp_path: Path) -> None:
    result = generate_project(_fastapi_definition(), base_dir=tmp_path)
    steps = result.next_steps()
    assert any(s.startswith("uv run fastapi dev") for s in steps)
    assert "uv sync" in steps
