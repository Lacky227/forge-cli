from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from forge.cli import flow
from forge.core.config import ForgeConfig
from forge.core.definition import AuthenticationOptions, Capabilities, ProjectDefinition
from forge.core.modules import ModuleId, expand_module_dependencies
from forge.core.presets import definition_from_preset
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator.engine import generate_project, preview_project
from forge.generator.render import planned_output_paths
from forge.generator.resolve import resolve_plan

ARCHITECTURES = tuple(ArchitectureStyle)


def definition(
    framework: str = "fastapi",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    *,
    authorization: bool = True,
    verification: bool = False,
    reset: bool = False,
    jobs: bool = False,
    extra_modules: tuple[str, ...] = (),
    sql: str = "sqlite",
    docker: bool = False,
) -> ProjectDefinition:
    modules = [ModuleId.AUTHORIZATION.value if authorization else ModuleId.AUTHENTICATION.value]
    if jobs:
        modules.append(ModuleId.BACKGROUND_JOBS.value)
    modules.extend(extra_modules)
    return ProjectDefinition(
        name=f"{framework}-security",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework=framework,
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=sql,
            migrations=framework != "django",
            docker=docker,
        ),
        modules=tuple(modules),
        authentication=AuthenticationOptions(
            email_verification=verification,
            password_reset=reset,
        ),
    )


def test_authorization_implies_authentication_and_sql() -> None:
    expanded = expand_module_dependencies((ModuleId.AUTHORIZATION.value,))
    assert expanded[-2:] == (ModuleId.AUTHENTICATION.value, ModuleId.AUTHORIZATION.value)
    with pytest.raises(ValidationError, match="SQL database"):
        ProjectDefinition(
            name="authz-no-sql",
            language=Language.PYTHON,
            project_type=ProjectType.REST_API,
            framework="fastapi",
            architecture=ArchitectureStyle.SIMPLE,
            modules=(ModuleId.AUTHORIZATION.value,),
        )


def test_yaml_authorization_and_account_security_implications() -> None:
    config = ForgeConfig.model_validate(
        {
            "type": "rest-api",
            "framework": "fastapi",
            "architecture": "clean",
            "persistence": {"sql": "sqlite"},
            "migrations": True,
            "modules": ["authorization"],
            "authentication": {
                "registration": True,
                "email_verification": True,
                "password_reset": True,
            },
        }
    )
    plan = resolve_plan(config.to_definition(cli_name="secure-api"))
    assert plan.features.authentication and plan.features.authorization
    assert plan.features.email_verification and plan.features.password_reset
    assert plan.features.email
    assert not plan.features.background_jobs
    assert not plan.features.redis
    assert plan.contributions is not None
    assert plan.contributions.implied_module_ids == ("email", "authentication")
    env = {item.name for item in plan.environment_variables}
    assert {
        "AUTH_PUBLIC_BASE_URL",
        "AUTH_VERIFICATION_TOKEN_TTL_SECONDS",
        "AUTH_RESET_TOKEN_TTL_SECONDS",
    } <= env


def test_authentication_options_remain_strict() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        AuthenticationOptions.model_validate({"mfa": True})


def test_interactive_authorization_collects_account_security_options(monkeypatch) -> None:
    monkeypatch.setattr(flow, "_select", lambda *_args, **_kwargs: "enabled")
    monkeypatch.setattr(
        flow,
        "_checkbox",
        lambda *_args, **_kwargs: ["email-verification", "password-reset"],
    )
    options = flow._collect_authentication_options([ModuleId.AUTHORIZATION.value])
    assert options == AuthenticationOptions(
        registration=True,
        email_verification=True,
        password_reset=True,
    )


def test_stage1_authentication_only_remains_email_free() -> None:
    plan = resolve_plan(definition(authorization=False))
    assert plan.features.authentication
    assert not plan.features.authorization
    assert not plan.features.email
    assert not plan.features.email_verification
    assert not plan.features.password_reset
    assert "AUTH_PUBLIC_BASE_URL" not in {item.name for item in plan.environment_variables}


def test_authorization_does_not_rewrite_existing_resource_endpoints(
    tmp_path: Path,
) -> None:
    common = {
        "name": "public-api",
        "language": Language.PYTHON,
        "project_type": ProjectType.REST_API,
        "framework": "fastapi",
        "architecture": ArchitectureStyle.SIMPLE,
        "capabilities": Capabilities(sql_database="sqlite", migrations=True),
    }
    legacy = generate_project(
        ProjectDefinition(**common, modules=("products",)),
        destination=tmp_path / "legacy",
    )
    secured = generate_project(
        ProjectDefinition(**common, modules=("products", "authorization")),
        destination=tmp_path / "secured",
    )
    product_path = Path("src/public_api/products.py")
    assert (legacy.destination / product_path).read_text(encoding="utf-8") == (
        secured.destination / product_path
    ).read_text(encoding="utf-8")


def test_plan_and_dry_run_describe_security_without_writes(tmp_path: Path) -> None:
    project = definition(verification=True, reset=True, jobs=True)
    plan = resolve_plan(project)
    sections = {section.title: dict(section.rows) for section in plan.summary_sections()}
    assert sections["Authorization"]["Model"] == "roles + permissions"
    assert sections["Authentication"]["Email verification"] == "enabled"
    assert sections["Email"]["Security email delivery"] == "background worker"
    preview = preview_project(project, destination=tmp_path / "preview")
    assert not (tmp_path / "preview").exists()
    assert any(path.endswith("authorization.py") for path in preview.files)
    assert any(path.endswith("security_email.py") for path in preview.files)
    assert any(path.endswith("test_account_security.py") for path in preview.files)
    assert plan.contributions is not None
    assert not any(
        path.startswith(("/roles", "/permissions", "/users/"))
        for _method, path, _description in plan.contributions.api_endpoints
    )


def test_action_tokens_are_digest_only_and_jobs_reuse_existing_worker(tmp_path: Path) -> None:
    output = tmp_path / "security-jobs"
    generate_project(
        definition(verification=True, reset=True, jobs=True, docker=True),
        destination=output,
    )
    package = output / "src" / "fastapi_security"
    models = (package / "auth_models.py").read_text(encoding="utf-8")
    security_email = (package / "security_email.py").read_text(encoding="utf-8")
    compose = (output / "docker-compose.yml").read_text(encoding="utf-8")
    assert "token_digest" in models
    assert "raw_token" not in models
    assert "secrets.token_urlsafe(32)" in (
        package / "auth_security.py"
    ).read_text(encoding="utf-8")
    assert "get_queue().enqueue" in security_email
    assert "Retry(max=3" in security_email
    assert "result_ttl=0" in security_email
    assert "failure_ttl=0" in security_email
    assert "redis:" in compose and "worker:" in compose


@pytest.mark.parametrize("framework", ["fastapi", "flask", "django"])
@pytest.mark.parametrize("architecture", ARCHITECTURES)
def test_all_nine_families_render_dense_stage2(
    framework: str,
    architecture: ArchitectureStyle,
    tmp_path: Path,
) -> None:
    project = definition(framework, architecture, verification=True, reset=True)
    output = tmp_path / f"{framework}-{architecture.value}"
    result = generate_project(project, destination=output)
    paths = set(result.files_written)
    assert any("authorization" in path for path in paths)
    assert any(path.endswith("test_account_security.py") for path in paths)
    assert any("migration" in path for path in paths)
    if architecture is ArchitectureStyle.CLEAN:
        assert any(path.endswith("application/authorization.py") for path in paths)
        auth_ports = next(path for path in paths if path.endswith("application/auth_ports.py"))
        assert "SecurityEmailDelivery" in (output / auth_ports).read_text(
            encoding="utf-8"
        )
    for path in paths:
        if path.endswith(".py"):
            compile((output / path).read_text(), path, "exec")


@pytest.mark.parametrize(
    "extra_modules",
    [
        ("products",),
        ("categories",),
        ("files",),
        ("webhooks",),
        ("products", "categories", "files", "email", "webhooks"),
    ],
)
def test_stage2_pairwise_and_dense_composition(extra_modules: tuple[str, ...]) -> None:
    kwargs = {}
    if "files" in extra_modules:
        from forge.core.definition import StorageOptions

        kwargs["storage"] = StorageOptions()
    base = definition(
        verification=True,
        reset=True,
        extra_modules=extra_modules,
        jobs="webhooks" in extra_modules,
    ).model_dump()
    base.update(kwargs)
    project = ProjectDefinition.model_validate(base)
    plan = resolve_plan(project)
    assert planned_output_paths(plan)
    assert len({item.name for item in plan.environment_variables}) == len(plan.environment_variables)


@pytest.mark.parametrize("framework", ["fastapi", "flask", "django"])
def test_postgresql_docker_stage2_structure(framework: str) -> None:
    plan = resolve_plan(
        definition(
            framework,
            ArchitectureStyle.MODULAR_MONOLITH,
            verification=True,
            reset=True,
            sql="postgresql",
            docker=True,
        )
    )
    paths = planned_output_paths(plan)
    assert "docker-compose.yml" in paths
    assert "db" in plan.docker_services
    assert "redis" not in plan.docker_services


def test_django_auth_preset() -> None:
    project = definition_from_preset("django-auth", name="django-secure")
    plan = resolve_plan(project)
    assert plan.features.authentication and plan.features.authorization
    assert not plan.features.email
