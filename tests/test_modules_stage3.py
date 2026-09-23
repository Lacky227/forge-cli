"""Stage 3 integration hardening: composition, dense plans, Django jobs."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge.core.config import ConfigError, definition_from_config
from forge.core.definition import Capabilities, ProjectDefinition, StorageOptions
from forge.core.presets import definition_from_preset, list_presets
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator.engine import generate_project, next_steps_for
from forge.generator.render import planned_output_paths
from forge.generator.resolve import resolve_plan


def _definition(
    *,
    name: str = "stage3-api",
    framework: str = "fastapi",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    modules: tuple[str, ...] = (),
    sql: str | None = "sqlite",
    nosql: str | None = None,
    migrations: bool = True,
    docker: bool = False,
    ci: str | None = None,
    storage: StorageOptions | None = None,
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
            migrations=migrations,
            testing=True,
            linting=True,
            docker=docker,
            ci=ci,
        ),
        modules=modules,
        storage=storage,
    )


# Pairwise interactions distributed across the 9 framework×architecture families.
_PAIRWISE: list[tuple[str, ArchitectureStyle, tuple[str, ...], dict]] = [
    ("fastapi", ArchitectureStyle.SIMPLE, ("products", "categories"), {}),
    ("fastapi", ArchitectureStyle.MODULAR_MONOLITH, ("products", "files"), {"storage": StorageOptions(backend="local")}),
    ("fastapi", ArchitectureStyle.CLEAN, ("products", "background-jobs"), {}),
    ("flask", ArchitectureStyle.SIMPLE, ("products", "email"), {}),
    ("flask", ArchitectureStyle.MODULAR_MONOLITH, ("products", "webhooks"), {}),
    ("flask", ArchitectureStyle.CLEAN, ("categories", "files"), {"storage": StorageOptions(backend="local")}),
    ("django", ArchitectureStyle.SIMPLE, ("categories", "background-jobs"), {"migrations": False}),
    ("django", ArchitectureStyle.MODULAR_MONOLITH, ("files", "background-jobs"), {"storage": StorageOptions(backend="local"), "migrations": False}),
    ("django", ArchitectureStyle.CLEAN, ("files", "email"), {"storage": StorageOptions(backend="local"), "migrations": False}),
    ("fastapi", ArchitectureStyle.SIMPLE, ("files", "webhooks"), {"storage": StorageOptions(backend="local")}),
    ("flask", ArchitectureStyle.SIMPLE, ("background-jobs", "email"), {"sql": None, "migrations": False}),
    ("fastapi", ArchitectureStyle.MODULAR_MONOLITH, ("email", "webhooks"), {"sql": None, "migrations": False}),
]


@pytest.mark.parametrize(
    ("framework", "architecture", "modules", "extra"),
    _PAIRWISE,
    ids=[
        f"{fw}-{arch.value}-{'+'.join(mods)}"
        for fw, arch, mods, _ in _PAIRWISE
    ],
)
def test_pairwise_composition_resolves_and_generates(
    tmp_path: Path,
    framework: str,
    architecture: ArchitectureStyle,
    modules: tuple[str, ...],
    extra: dict,
) -> None:
    kwargs = {
        "framework": framework,
        "architecture": architecture,
        "modules": modules,
        **extra,
    }
    definition = _definition(**kwargs)
    plan = resolve_plan(definition)
    assert plan.template_subdir
    planned = planned_output_paths(plan)
    result = generate_project(definition, base_dir=tmp_path)
    assert planned == result.files_written
    assert result.files_written


def test_django_jobs_no_phantom_apps(tmp_path: Path) -> None:
    for architecture in ArchitectureStyle:
        definition = _definition(
            name=f"dj-jobs-{architecture.value}",
            framework="django",
            architecture=architecture,
            modules=("background-jobs",),
            migrations=False,
        )
        plan = resolve_plan(definition)
        assert not any(
            a.module_id == "background-jobs" and a.app_config
            for a in (plan.contributions.django_apps if plan.contributions else ())
        )
        result = generate_project(definition, base_dir=tmp_path / architecture.value)
        settings = (result.destination / "src/config/settings.py").read_text(
            encoding="utf-8"
        )
        installed = settings.split("INSTALLED_APPS")[1].split("]")[0]
        assert "jobsq" not in installed
        assert "apps.jobs" not in installed
        assert "infrastructure.jobs" not in installed
        assert '"jobsq"' not in settings
        assert '"apps.jobs"' not in settings
        assert '"infrastructure.jobs"' not in settings


def test_all_modules_acceptance_plan() -> None:
    plan = resolve_plan(
        _definition(
            framework="fastapi",
            architecture=ArchitectureStyle.CLEAN,
            modules=(
                "products",
                "categories",
                "files",
                "background-jobs",
                "email",
                "webhooks",
            ),
            sql="postgresql",
            docker=True,
            ci="github-actions",
            storage=StorageOptions(backend="s3", minio=True),
        )
    )
    assert plan.docker_services == ("db", "redis", "minio")
    assert {p.id for p in plan.processes} == {"api", "worker"}
    env_names = {v.name for v in plan.environment_variables}
    assert "S3_CREATE_BUCKET" in env_names
    assert "REDIS_URL" in env_names
    assert "WEBHOOK_URL" in env_names
    assert "SMTP_HOST" in env_names
    deps = " ".join(plan.runtime_dependencies)
    assert deps.count("redis") == 1
    assert "boto3" in deps and "rq" in deps and "httpx" in deps
    titles = {s.title for s in plan.summary_sections()}
    assert {"Modules", "Storage", "Background Jobs", "Email", "Webhooks", "Processes"} <= titles
    steps = next_steps_for(plan, destination_name="maximal")
    assert any("worker" in s for s in steps)
    assert any("docker compose up -d" in s for s in steps)


def test_s3_without_minio_empty_endpoint_example() -> None:
    plan = resolve_plan(
        _definition(
            modules=("files",),
            storage=StorageOptions(backend="s3", minio=False),
            docker=False,
        )
    )
    by_name = {v.name: v for v in plan.environment_variables}
    assert by_name["S3_ENDPOINT_URL"].example == ""
    assert by_name["S3_CREATE_BUCKET"].example == "false"


def test_redis_reuse_single_docker_service() -> None:
    plan = resolve_plan(
        _definition(
            modules=("background-jobs",),
            sql=None,
            migrations=False,
            nosql="redis",
            docker=True,
        )
    )
    assert plan.docker_services == ("redis",)
    assert plan.features.redis_nosql is True
    assert sum(1 for d in plan.runtime_dependencies if d.startswith("redis")) == 1


def test_dry_run_parity_all_modules(tmp_path: Path) -> None:
    definition = _definition(
        framework="fastapi",
        architecture=ArchitectureStyle.CLEAN,
        modules=(
            "products",
            "categories",
            "files",
            "background-jobs",
            "email",
            "webhooks",
        ),
        sql="sqlite",
        docker=True,
        storage=StorageOptions(backend="s3", minio=True),
    )
    planned = planned_output_paths(resolve_plan(definition))
    result = generate_project(definition, base_dir=tmp_path)
    assert planned == result.files_written
    assert any(".github/workflows" not in p for p in planned)  # ci off
    assert any("docker-compose" in p for p in planned)
    assert any("worker" in p.lower() or "jobs" in p.lower() for p in planned)


def test_ci_with_all_modules(tmp_path: Path) -> None:
    definition = _definition(
        modules=("products", "files", "webhooks"),
        storage=StorageOptions(backend="local"),
        ci="github-actions",
        docker=False,
    )
    result = generate_project(definition, base_dir=tmp_path)
    workflow = (result.destination / ".github/workflows/ci.yml").read_text(
        encoding="utf-8"
    )
    assert "uv sync" in workflow
    assert "pytest" in workflow
    assert "postgres" not in workflow.lower()
    assert "redis" not in workflow.lower()
    assert "minio" not in workflow.lower()


def test_module_presets() -> None:
    ids = {p.id for p in list_presets()}
    assert {"fastapi-catalog", "fastapi-files"} <= ids
    catalog = definition_from_preset("fastapi-catalog", name="catalog")
    assert catalog.modules == ("products", "categories")
    assert catalog.storage is None
    files = definition_from_preset("fastapi-files", name="files-api")
    assert files.modules == ("files",)
    assert files.storage is not None
    assert files.storage.backend == "local"
    # Existing presets unchanged — no modules.
    for legacy in (
        "fastapi-postgres",
        "fastapi-postgres-clean",
        "fastapi-mongo",
        "flask-postgres",
        "django-postgres",
    ):
        assert definition_from_preset(legacy, name="legacy").modules == ()


def test_legacy_yaml_no_modules(tmp_path: Path) -> None:
    path = tmp_path / "legacy.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "name": "legacy",
                "type": "rest-api",
                "framework": "fastapi",
                "architecture": "simple",
                "database": "sqlite",
                "migrations": True,
            }
        ),
        encoding="utf-8",
    )
    definition = definition_from_config(path)
    assert definition.modules == ()
    plan = resolve_plan(definition)
    assert plan.contributions is None or not plan.contributions.enabled


def test_yaml_invalid_module_message(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "name": "bad",
                "type": "rest-api",
                "framework": "fastapi",
                "architecture": "simple",
                "modules": ["users"],
                "persistence": {"sql": "sqlite"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="unknown module"):
        definition_from_config(path)


def test_nine_family_module_rich_matrix(tmp_path: Path) -> None:
    """Each framework×architecture family gets at least one module-rich case."""
    cases = [
        ("fastapi", ArchitectureStyle.SIMPLE, ("files", "email"), StorageOptions(backend="local"), "sqlite"),
        ("fastapi", ArchitectureStyle.MODULAR_MONOLITH, ("products", "categories", "background-jobs"), None, "postgresql"),
        ("fastapi", ArchitectureStyle.CLEAN, ("products", "files", "webhooks"), StorageOptions(backend="s3", minio=False), "sqlite"),
        ("flask", ArchitectureStyle.SIMPLE, ("products", "background-jobs"), None, "sqlite"),
        ("flask", ArchitectureStyle.MODULAR_MONOLITH, ("categories", "files", "email"), StorageOptions(backend="local"), "postgresql"),
        ("flask", ArchitectureStyle.CLEAN, ("products", "categories", "webhooks"), None, "sqlite"),
        ("django", ArchitectureStyle.SIMPLE, ("products", "files", "background-jobs"), StorageOptions(backend="local"), "sqlite"),
        ("django", ArchitectureStyle.MODULAR_MONOLITH, ("products", "categories", "email", "webhooks"), None, "postgresql"),
        ("django", ArchitectureStyle.CLEAN, ("files", "background-jobs", "webhooks"), StorageOptions(backend="s3", minio=False), "sqlite"),
    ]
    for framework, architecture, modules, storage, sql in cases:
        definition = _definition(
            name=f"{framework}-{architecture.value}",
            framework=framework,
            architecture=architecture,
            modules=modules,
            sql=sql,
            migrations=framework != "django",
            docker=False,
            storage=storage,
        )
        plan = resolve_plan(definition)
        result = generate_project(definition, base_dir=tmp_path / definition.name)
        assert planned_output_paths(plan) == result.files_written
        pyproject = (result.destination / "pyproject.toml").read_text(encoding="utf-8")
        if "files" in modules and storage and storage.backend == "s3":
            assert "boto3" in pyproject
        if "background-jobs" in modules or "webhooks" in modules:
            assert "rq" in pyproject
            assert "redis" in pyproject
