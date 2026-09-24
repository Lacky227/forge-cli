from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from forge.core.definition import AuthenticationOptions, Capabilities, ProjectDefinition
from forge.core.modules import ModuleId
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
) -> ProjectDefinition:
    modules = [ModuleId.AUTHORIZATION.value if authorization else ModuleId.AUTHENTICATION.value]
    if jobs:
        modules.append(ModuleId.BACKGROUND_JOBS.value)
    modules.extend(extra_modules)
    return ProjectDefinition(
        name=f"{framework}-stage3",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework=framework,
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=sql,
            migrations=framework != "django",
        ),
        modules=tuple(modules),
        authentication=AuthenticationOptions(
            email_verification=verification,
            password_reset=reset,
        ),
    )


def test_plan_includes_hardening_facts_and_env() -> None:
    plan = resolve_plan(definition(verification=True, reset=True))
    sections = {section.title: dict(section.rows) for section in plan.summary_sections()}
    security = sections["Security"]
    assert "process-local" in security["Abuse protection"]
    assert security["Trusted hosts"] == "configurable allow-list"
    assert "configurable" in security["CORS"].lower()
    assert "maintenance command" in security["Cleanup"]
    env = {item.name for item in plan.environment_variables}
    assert {
        "TRUSTED_HOSTS",
        "CORS_ALLOWED_ORIGINS",
        "AUTH_ENABLE_HSTS",
        "AUTH_RATE_LIMIT_CREDENTIAL",
        "AUTH_RATE_LIMIT_REGISTRATION",
        "AUTH_RATE_LIMIT_REFRESH",
        "AUTH_RATE_LIMIT_RECOVERY",
    } <= env
    assert "REDIS_URL" not in env or plan.features.redis


def test_django_plan_uses_allowed_hosts_env() -> None:
    plan = resolve_plan(definition("django"))
    env = {item.name: item.example for item in plan.environment_variables}
    assert "DJANGO_ALLOWED_HOSTS" in env
    assert "TRUSTED_HOSTS" not in env
    assert "localhost" in env["DJANGO_ALLOWED_HOSTS"]


def test_dry_run_lists_hardening_files(tmp_path: Path) -> None:
    project = definition(verification=True, reset=True)
    preview = preview_project(project, destination=tmp_path / "preview")
    assert not (tmp_path / "preview").exists()
    paths = set(preview.files)
    assert any(path.endswith(("auth_rate_limit.py", "rate_limit.py")) for path in paths)
    assert any("auth_cleanup" in path or path.endswith("cleanup_auth_state.py") for path in paths)
    assert any(path.endswith("test_security_hardening.py") for path in paths)
    assert any(path.endswith(("auth_hardening.py", "hardening.py")) for path in paths)


def test_auth_only_does_not_imply_redis() -> None:
    plan = resolve_plan(definition(authorization=False))
    assert plan.features.authentication
    assert not plan.features.redis
    assert not plan.features.background_jobs
    assert "redis" not in " ".join(plan.runtime_dependencies).lower()


def test_stage1_auth_only_still_works(tmp_path: Path) -> None:
    output = tmp_path / "stage1"
    result = generate_project(definition(authorization=False), destination=output)
    assert any(path.endswith(("auth_rate_limit.py", "rate_limit.py")) for path in result.files_written)
    assert not any(path.endswith("test_account_security.py") for path in result.files_written)
    assert not any("authorization" in path for path in result.files_written)


def test_stage2_authz_still_works(tmp_path: Path) -> None:
    output = tmp_path / "stage2"
    result = generate_project(definition(verification=True, reset=True), destination=output)
    assert any("authorization" in path for path in result.files_written)
    assert any(path.endswith("test_account_security.py") for path in result.files_written)
    assert any(path.endswith("test_security_hardening.py") for path in result.files_written)


def test_no_auth_project_unchanged_hosts(tmp_path: Path) -> None:
    project = ProjectDefinition(
        name="plain-api",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework="django",
        architecture=ArchitectureStyle.SIMPLE,
        capabilities=Capabilities(sql_database="sqlite"),
    )
    plan = resolve_plan(project)
    assert not plan.features.authentication
    assert "DJANGO_ALLOWED_HOSTS" not in {item.name for item in plan.environment_variables}
    output = tmp_path / "plain"
    generate_project(project, destination=output)
    settings = (output / "src" / "config" / "settings.py").read_text(encoding="utf-8")
    assert 'os.environ.get("DJANGO_ALLOWED_HOSTS", "*")' in settings
    assert "SECURE_CONTENT_TYPE_NOSNIFF" not in settings


def test_presets_still_resolve() -> None:
    for preset in ("fastapi-auth", "django-auth"):
        project = definition_from_preset(preset, name=f"{preset}-proj")
        plan = resolve_plan(project)
        assert plan.features.authentication
        assert planned_output_paths(plan)


def test_rq_security_email_is_honest_about_tokens(tmp_path: Path) -> None:
    output = tmp_path / "jobs"
    generate_project(
        definition(verification=True, reset=True, jobs=True),
        destination=output,
    )
    security_email = (
        output / "src" / "fastapi_stage3" / "security_email.py"
    ).read_text(encoding="utf-8")
    assert "failure_ttl=0" in security_email
    assert "result_ttl=0" in security_email
    assert "description=" in security_email
    assert "Raw tokens necessarily appear in Redis" in security_email


@pytest.mark.parametrize("framework", ["fastapi", "flask", "django"])
@pytest.mark.parametrize("architecture", ARCHITECTURES)
def test_all_nine_families_render_stage3(
    framework: str,
    architecture: ArchitectureStyle,
    tmp_path: Path,
) -> None:
    project = definition(framework, architecture, verification=True, reset=True)
    output = tmp_path / f"{framework}-{architecture.value}"
    result = generate_project(project, destination=output)
    paths = set(result.files_written)
    assert any(path.endswith("test_security_hardening.py") for path in paths)
    assert any("rate_limit" in path for path in paths)
    assert any("cleanup" in path for path in paths)
    for path in paths:
        if path.endswith(".py"):
            compile((output / path).read_text(encoding="utf-8"), path, "exec")


def test_authentication_options_remain_strict() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        AuthenticationOptions.model_validate({"mfa": True})
