"""Generation compatibility matrix — resolve, generate, and boundary checks.

Default suite: every official case resolves and generates structurally.
Executable install/test smoke is marked ``generation_smoke`` (excluded by
default; see ``pyproject.toml`` / CI package job).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.core.compatibility import (
    SUPPORTED_GENERATION_CASES,
    GenerationCase,
    executable_smoke_cases,
    supported_generation_cases,
)
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import GenerationError, generate_project, resolve_plan


def test_matrix_ids_unique() -> None:
    ids = [case.id for case in SUPPORTED_GENERATION_CASES]
    assert len(ids) == len(set(ids))


def test_matrix_covers_frameworks_and_architectures() -> None:
    frameworks = {case.framework for case in SUPPORTED_GENERATION_CASES}
    architectures = {case.architecture for case in SUPPORTED_GENERATION_CASES}
    assert frameworks == {"fastapi", "django", "flask"}
    assert architectures == {
        ArchitectureStyle.SIMPLE,
        ArchitectureStyle.MODULAR_MONOLITH,
        ArchitectureStyle.CLEAN,
    }


@pytest.mark.parametrize("case", SUPPORTED_GENERATION_CASES, ids=lambda c: c.id)
def test_supported_case_resolves(case: GenerationCase) -> None:
    plan = resolve_plan(case.to_definition())
    assert plan.definition.framework == case.framework
    assert plan.definition.architecture is case.architecture
    assert plan.features.database is case.database
    if case.database_engine == "postgresql":
        assert plan.features.postgresql is True
    if case.database_engine == "sqlite":
        assert plan.features.sqlite is True
    if case.framework == "django":
        assert plan.features.orm == "django-orm"
        assert plan.features.migration_system == "django"
        assert plan.features.rest_framework is True
    if case.framework in {"fastapi", "flask"} and case.database:
        assert plan.features.orm == "sqlalchemy"
        if case.migrations:
            assert plan.features.migration_system == "alembic"
    if case.framework == "flask" and not case.database:
        assert plan.features.orm is None
        assert plan.features.migration_system is None


@pytest.mark.parametrize("case", SUPPORTED_GENERATION_CASES, ids=lambda c: c.id)
def test_supported_case_generates_structurally(
    case: GenerationCase, tmp_path: Path
) -> None:
    result = generate_project(case.to_definition(), base_dir=tmp_path)
    root = result.destination
    plan = result.plan
    assert root.is_dir()
    assert (root / "pyproject.toml").is_file()
    assert (root / "README.md").is_file()

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    for dep in plan.runtime_dependencies:
        # Dependencies may use extras: fastapi[standard]>=...
        token = dep.split(">=")[0].split("[")[0]
        assert token in pyproject, f"missing runtime dep {dep!r}"

    template = plan.template_subdir.as_posix()
    assert case.framework in template
    assert case.architecture.value in template

    if case.framework == "django":
        assert (root / "manage.py").is_file()
        assert "django" in pyproject.lower()
        assert "sqlalchemy" not in pyproject.lower()
    elif case.framework == "fastapi":
        assert "fastapi" in pyproject.lower()
        assert not (root / "manage.py").exists()
    elif case.framework == "flask":
        assert "flask" in pyproject.lower()
        assert not (root / "manage.py").exists()

    if case.architecture is ArchitectureStyle.CLEAN:
        pkg = root / "src" / plan.package_name
        if case.framework == "django":
            # Django Clean uses layered packages under src/
            assert (root / "src" / "domain").is_dir() or (pkg / "domain").is_dir()
        else:
            assert (pkg / "domain").is_dir()
            assert (pkg / "application").is_dir()
            assert (pkg / "infrastructure").is_dir()
            assert (pkg / "presentation").is_dir()

    if plan.features.docker:
        assert (root / "Dockerfile").is_file()
        assert (root / "docker-compose.yml").is_file()
    else:
        assert not (root / "Dockerfile").exists()

    if plan.features.migration_system == "alembic":
        assert (root / "alembic.ini").is_file()
    if plan.features.migration_system == "django":
        assert plan.migrate_command is not None
        assert "migrate" in plan.migrate_command

    if plan.features.testing:
        assert (root / "tests").is_dir()
    if plan.features.linting:
        assert "ruff" in pyproject.lower()


def test_unsupported_django_sqlalchemy_fails_before_write(tmp_path: Path) -> None:
    definition = ProjectDefinition.model_construct(
        name="bad-django",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities.model_construct(
            database=True,
            database_engine="postgresql",
            orm="sqlalchemy",
            migrations=False,
            docker=False,
            testing=True,
            linting=False,
        ),
    )
    with pytest.raises(GenerationError, match="SQLAlchemy"):
        generate_project(definition, base_dir=tmp_path)
    assert not (tmp_path / "bad-django").exists()


def test_unsupported_fastapi_django_orm_fails_before_write(tmp_path: Path) -> None:
    definition = ProjectDefinition.model_construct(
        name="bad-fastapi",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities.model_construct(
            database=True,
            database_engine="sqlite",
            orm="django-orm",
            migrations=False,
            docker=False,
            testing=True,
            linting=False,
        ),
    )
    with pytest.raises(GenerationError, match="Django ORM"):
        generate_project(definition, base_dir=tmp_path)
    assert not (tmp_path / "bad-fastapi").exists()


def test_unsupported_flask_django_orm_fails_before_write(tmp_path: Path) -> None:
    definition = ProjectDefinition.model_construct(
        name="bad-flask",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="flask",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities.model_construct(
            database=True,
            database_engine="sqlite",
            orm="django-orm",
            migrations=False,
            docker=False,
            testing=True,
            linting=False,
        ),
    )
    with pytest.raises(GenerationError, match="Django ORM"):
        generate_project(definition, base_dir=tmp_path)
    assert not (tmp_path / "bad-flask").exists()


def test_executable_smoke_subset_excludes_postgres() -> None:
    cases = executable_smoke_cases()
    assert cases
    assert all(c.database_engine != "postgresql" for c in cases)
    assert {c.framework for c in cases} == {"fastapi", "django", "flask"}


def test_supported_generation_cases_helper() -> None:
    assert list(supported_generation_cases()) == list(SUPPORTED_GENERATION_CASES)
