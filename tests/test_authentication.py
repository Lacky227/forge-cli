from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from forge.core.config import ForgeConfig
from forge.core.definition import (
    AuthenticationOptions,
    Capabilities,
    ProjectDefinition,
    StorageOptions,
)
from forge.core.modules import ModuleId, modules_require_sql
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator.engine import generate_project, preview_project
from forge.generator.render import planned_output_paths
from forge.generator.resolve import resolve_plan

ARCHITECTURES = (
    ArchitectureStyle.SIMPLE,
    ArchitectureStyle.MODULAR_MONOLITH,
    ArchitectureStyle.CLEAN,
)


def definition(framework: str = "fastapi", architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE, *, registration: bool = True) -> ProjectDefinition:
    return ProjectDefinition(
        name=f"{framework}-auth-app",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework=framework,
        architecture=architecture,
        capabilities=Capabilities(sql_database="sqlite", migrations=framework != "django", docker=False),
        modules=("authentication",),
        authentication=AuthenticationOptions(registration=registration),
    )


def test_authentication_catalog_and_validation() -> None:
    assert modules_require_sql((ModuleId.AUTHENTICATION.value,))
    with pytest.raises(ValidationError, match="SQL database"):
        ProjectDefinition(
            name="missing-sql",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
            modules=("authentication",),
        )
    with pytest.raises(ValidationError, match="authentication options require"):
        ProjectDefinition(
            name="invalid-auth-options",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
            authentication=AuthenticationOptions(),
        )
    with pytest.raises(ValidationError, match="Alembic"):
        ProjectDefinition(
            name="missing-migrations",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
            capabilities=Capabilities(sql_database="sqlite", migrations=False),
            modules=("authentication",),
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        AuthenticationOptions.model_validate({"registration": True, "mfa": True})


def test_yaml_default_and_disabled_registration() -> None:
    base = {
        "type": "rest-api",
        "framework": "fastapi",
        "architecture": "simple",
        "persistence": {"sql": "sqlite"},
        "migrations": True,
        "modules": ["authentication"],
    }
    assert ForgeConfig.model_validate(base).to_definition(cli_name="yaml-auth").authentication_options.registration is True
    base["authentication"] = {"registration": False}
    assert ForgeConfig.model_validate(base).to_definition(cli_name="yaml-auth").authentication_options.registration is False


def test_resolved_auth_contract_and_secret_non_disclosure(tmp_path: Path) -> None:
    plan = resolve_plan(definition())
    assert plan.features.authentication and plan.features.registration
    assert plan.generated_secrets[0].environment_variable == "AUTH_JWT_SECRET"
    env = {item.name: item.example for item in plan.environment_variables}
    assert env["AUTH_JWT_SECRET"] == ""
    assert {"PyJWT>=2.10", "pwdlib[argon2]>=0.3", "email-validator>=2.2"} <= set(plan.runtime_dependencies)
    summary = str(plan.summary_sections())
    assert "Argon2id" in summary and "generated locally" in summary
    assert "AUTH_JWT_SECRET" not in summary or plan.generated_secrets[0].environment_variable in summary

    preview = preview_project(definition(), destination=tmp_path / "dry")
    assert ".env" in preview.files and ".env.example" in preview.files
    assert not (tmp_path / "dry").exists()

    result = generate_project(definition(), destination=tmp_path / "real")
    local_env = (result.destination / ".env").read_text()
    example = (result.destination / ".env.example").read_text()
    secret_line = next(line for line in local_env.splitlines() if line.startswith("AUTH_JWT_SECRET="))
    assert len(secret_line.partition("=")[2]) >= 43
    assert "AUTH_JWT_SECRET=" in example
    assert secret_line not in example


@pytest.mark.parametrize("framework", ["fastapi", "flask", "django"])
@pytest.mark.parametrize("architecture", ARCHITECTURES)
def test_all_nine_families_render_authentication(framework: str, architecture: ArchitectureStyle, tmp_path: Path) -> None:
    plan = resolve_plan(definition(framework, architecture))
    paths = planned_output_paths(plan)
    assert any("authentication" in path or "/auth" in path or "identity" in path for path in paths)
    assert any("migration" in path for path in paths)
    assert "tests/test_authentication.py" in paths
    output = tmp_path / f"{framework}-{architecture.value}"
    result = generate_project(definition(framework, architecture), destination=output)
    assert result.files_written
    for path in result.files_written:
        if path.endswith(".py"):
            compile((output / path).read_text(), path, "exec")


def test_registration_disabled_omits_route(tmp_path: Path) -> None:
    result = generate_project(definition(registration=False), destination=tmp_path / "disabled")
    auth_source = (result.destination / "src" / result.package_name / "auth.py").read_text()
    assert '@router.post("/register"' not in auth_source


@pytest.mark.parametrize(
    ("modules", "nosql", "storage"),
    [
        (("authentication", "products", "categories"), None, None),
        (("authentication", "files"), None, StorageOptions()),
        (("authentication", "background-jobs"), None, None),
        (("authentication", "email"), None, None),
        (("authentication", "webhooks"), None, None),
        (("authentication",), "redis", None),
        (("authentication",), "mongodb", None),
        (
            ("authentication", "files"),
            None,
            StorageOptions(backend="s3", minio=True),
        ),
    ],
)
def test_pairwise_existing_module_compatibility(
    modules: tuple[str, ...],
    nosql: str | None,
    storage: StorageOptions | None,
) -> None:
    plan = resolve_plan(
        ProjectDefinition(
            name="pairwise-auth",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.MODULAR_MONOLITH,
            capabilities=Capabilities(
                sql_database="sqlite",
                nosql_database=nosql,
                migrations=True,
                docker=bool(storage and storage.minio),
            ),
            modules=modules,
            storage=storage,
        )
    )
    assert plan.features.authentication
    assert planned_output_paths(plan)
    assert "redis>=5.0" in plan.runtime_dependencies if plan.features.redis else True
    assert "rq>=2.0" not in plan.runtime_dependencies if "background-jobs" not in plan.contributions.selected_modules and "webhooks" not in plan.contributions.selected_modules else True


@pytest.mark.parametrize("framework", ["fastapi", "flask", "django"])
def test_postgresql_docker_structure(framework: str) -> None:
    plan = resolve_plan(
        ProjectDefinition(
            name=f"{framework}-auth-postgres",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework=framework,
            architecture=ArchitectureStyle.MODULAR_MONOLITH,
            capabilities=Capabilities(
                sql_database="postgresql",
                migrations=framework != "django",
                docker=True,
            ),
            modules=("authentication",),
        )
    )
    paths = planned_output_paths(plan)
    assert "docker-compose.yml" in paths
    assert "db" in plan.docker_services
