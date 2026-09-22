"""Tests for ProjectDefinition validation and catalog compatibility."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from forge.core.catalog import frameworks_for, supports_database
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType


def test_valid_fastapi_definition() -> None:
    definition = ProjectDefinition(
        name="my-api",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="fastapi",
        architecture=ArchitectureStyle.MODULAR_MONOLITH,
        capabilities=Capabilities(
            database=True,
            database_engine="postgresql",
            migrations=True,
            docker=True,
            testing=True,
        ),
    )
    assert definition.name == "my-api"
    assert definition.framework == "fastapi"
    assert definition.capabilities.database_engine == "postgresql"
    assert definition.capabilities.orm is None


def test_valid_django_definition_without_orm_field() -> None:
    """Django REST intent does not require ORM/migrations on the definition."""
    definition = ProjectDefinition(
        name="web",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities(
            database=True,
            database_engine="postgresql",
            docker=True,
        ),
    )
    assert definition.capabilities.orm is None
    assert definition.capabilities.migrations is False


def test_cli_project_skips_complex_architecture() -> None:
    definition = ProjectDefinition(
        name="my-cli",
        language=Language.PYTHON,
        project_type=ProjectType.CLI,
        framework="typer",
        architecture=ArchitectureStyle.SIMPLE,
    )
    assert definition.project_type is ProjectType.CLI
    assert definition.capabilities.database is False


def test_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        ProjectDefinition(
            name="  ",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
        )


def test_rejects_invalid_name_characters() -> None:
    with pytest.raises(ValidationError):
        ProjectDefinition(
            name="my api!",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
        )


def test_rejects_framework_incompatible_with_project_type() -> None:
    with pytest.raises(ValidationError, match="not valid"):
        ProjectDefinition(
            name="oops",
            language=Language.PYTHON,
            project_type=ProjectType.CLI,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
        )


def test_rejects_clean_architecture_for_cli() -> None:
    with pytest.raises(ValidationError, match="architecture"):
        ProjectDefinition(
            name="oops",
            language=Language.PYTHON,
            project_type=ProjectType.CLI,
            framework="typer",
            architecture=ArchitectureStyle.CLEAN,
        )


def test_rejects_database_without_engine() -> None:
    with pytest.raises(ValidationError):
        ProjectDefinition(
            name="api",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
            capabilities=Capabilities(database=True),
        )


def test_rejects_orm_when_database_disabled() -> None:
    with pytest.raises(ValidationError, match="database_engine and orm"):
        ProjectDefinition(
            name="api",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
            capabilities=Capabilities(
                database=False,
                orm="sqlalchemy",
            ),
        )


def test_rejects_database_for_non_capable_framework() -> None:
    with pytest.raises(ValidationError, match="does not support a database"):
        ProjectDefinition(
            name="tool",
            language=Language.PYTHON,
            project_type=ProjectType.CLI,
            framework="typer",
            architecture=ArchitectureStyle.SIMPLE,
            capabilities=Capabilities(
                database=True,
                database_engine="sqlite",
                orm="sqlalchemy",
            ),
        )


def test_django_requires_django_orm() -> None:
    with pytest.raises(ValidationError, match="django-orm"):
        ProjectDefinition(
            name="web",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="django",
            architecture=ArchitectureStyle.SIMPLE,
            capabilities=Capabilities(
                database=True,
                database_engine="postgresql",
                orm="sqlalchemy",
            ),
        )


def test_frameworks_for_rest_api_are_python_web() -> None:
    frameworks = frameworks_for(Language.PYTHON, ProjectType.REST_API)
    assert frameworks == ("fastapi", "django", "flask")


def test_typer_does_not_support_database_capability() -> None:
    assert supports_database("typer") is False
    assert supports_database("fastapi") is True


def test_definition_constructible_without_cli() -> None:
    """Architectural proof: core model has no CLI dependency."""
    import forge.core.definition as definition_module

    assert "questionary" not in definition_module.__dict__
    assert "typer" not in definition_module.__dict__
    assert "rich" not in definition_module.__dict__
