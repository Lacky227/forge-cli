"""Tests for Stage 2 infrastructure-backed modules."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge.core.config import ConfigError, definition_from_config
from forge.core.definition import Capabilities, ProjectDefinition, StorageOptions
from forge.core.modules import (
    expand_module_dependencies,
    implied_modules,
    modules_require_redis,
    modules_require_sql,
    normalize_modules,
)
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator.engine import generate_project, next_steps_for
from forge.generator.render import planned_output_paths
from forge.generator.resolve import resolve_plan


def _definition(
    *,
    framework: str = "fastapi",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    modules: tuple[str, ...] = (),
    sql: str | None = "sqlite",
    nosql: str | None = None,
    migrations: bool = True,
    docker: bool = False,
    storage: StorageOptions | None = None,
) -> ProjectDefinition:
    return ProjectDefinition(
        name="stage2-api",
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
        ),
        modules=modules,
        storage=storage,
    )


class TestModuleCatalogStage2:
    def test_catalog_order(self) -> None:
        ids = normalize_modules(
            [
                "webhooks",
                "email",
                "files",
                "background-jobs",
                "categories",
                "products",
            ]
        )
        assert ids == (
            "products",
            "categories",
            "files",
            "background-jobs",
            "email",
            "webhooks",
        )

    def test_webhooks_expand_to_jobs(self) -> None:
        expanded = expand_module_dependencies(("webhooks",))
        assert expanded == ("background-jobs", "webhooks")
        assert implied_modules(("webhooks",), expanded) == ("background-jobs",)

    def test_files_require_sql(self) -> None:
        assert modules_require_sql(("files",)) is True
        with pytest.raises(ValueError, match="require an SQL database"):
            _definition(modules=("files",), sql=None, migrations=False)

    def test_jobs_require_redis(self) -> None:
        assert modules_require_redis(("background-jobs",)) is True
        assert modules_require_redis(("webhooks",)) is True
        assert modules_require_redis(("email",)) is False


class TestStorageOptions:
    def test_default_local_when_files(self) -> None:
        d = _definition(modules=("files",))
        assert d.storage is not None
        assert d.storage.backend == "local"
        assert d.storage.minio is False

    def test_storage_without_files_rejected(self) -> None:
        with pytest.raises(ValueError, match="storage options require"):
            _definition(
                modules=("email",),
                sql=None,
                migrations=False,
                storage=StorageOptions(backend="local"),
            )

    def test_minio_requires_docker(self) -> None:
        with pytest.raises(ValueError, match="minio requires"):
            _definition(
                modules=("files",),
                docker=False,
                storage=StorageOptions(backend="s3", minio=True),
            )

    def test_minio_requires_s3(self) -> None:
        with pytest.raises(ValueError, match="storage.minio requires"):
            StorageOptions(backend="local", minio=True)


class TestYamlStage2:
    def test_files_s3_minio(self, tmp_path: Path) -> None:
        path = tmp_path / "forge.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "cfg-api",
                    "type": "rest-api",
                    "framework": "fastapi",
                    "architecture": "simple",
                    "modules": ["files"],
                    "storage": {"backend": "s3", "minio": True},
                    "persistence": {"sql": "sqlite"},
                    "migrations": True,
                    "docker": True,
                }
            ),
            encoding="utf-8",
        )
        definition = definition_from_config(path)
        assert definition.modules == ("files",)
        assert definition.storage is not None
        assert definition.storage.backend == "s3"
        assert definition.storage.minio is True

    def test_webhooks_only(self, tmp_path: Path) -> None:
        path = tmp_path / "forge.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "cfg-api",
                    "type": "rest-api",
                    "framework": "fastapi",
                    "architecture": "simple",
                    "modules": ["webhooks"],
                }
            ),
            encoding="utf-8",
        )
        definition = definition_from_config(path)
        assert definition.modules == ("webhooks",)
        plan = resolve_plan(definition)
        assert plan.features.background_jobs is True
        assert plan.features.redis is True
        assert plan.features.redis_nosql is False
        assert any(m.id == "background-jobs" and m.implied for m in plan.contributions.modules)

    def test_unknown_storage_backend(self, tmp_path: Path) -> None:
        path = tmp_path / "forge.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "cfg-api",
                    "type": "rest-api",
                    "framework": "fastapi",
                    "architecture": "simple",
                    "modules": ["files"],
                    "storage": {"backend": "gcs"},
                    "persistence": {"sql": "sqlite"},
                    "migrations": True,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="unknown storage backend"):
            definition_from_config(path)

    def test_stage1_yaml_still_valid(self, tmp_path: Path) -> None:
        path = tmp_path / "forge.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "cfg-api",
                    "type": "rest-api",
                    "framework": "fastapi",
                    "architecture": "simple",
                    "modules": ["products", "categories"],
                    "persistence": {"sql": "sqlite"},
                    "migrations": True,
                }
            ),
            encoding="utf-8",
        )
        definition = definition_from_config(path)
        plan = resolve_plan(definition)
        assert plan.features.redis is False
        assert "rq" not in " ".join(plan.runtime_dependencies)
        assert "boto3" not in " ".join(plan.runtime_dependencies)


class TestResolveStage2:
    def test_files_local_plan(self) -> None:
        plan = resolve_plan(_definition(modules=("files",)))
        assert plan.features.storage_backend == "local"
        assert plan.features.minio is False
        assert any(v.name == "STORAGE_LOCAL_ROOT" for v in plan.environment_variables)
        assert any(v.name == "UPLOAD_MAX_BYTES" for v in plan.environment_variables)
        assert "boto3" not in " ".join(plan.runtime_dependencies)

    def test_files_s3_minio_docker(self) -> None:
        plan = resolve_plan(
            _definition(
                modules=("files",),
                docker=True,
                storage=StorageOptions(backend="s3", minio=True),
            )
        )
        assert plan.features.storage_backend == "s3"
        assert plan.features.minio is True
        assert "minio" in plan.docker_services
        assert any(v.name == "S3_ENDPOINT_URL" for v in plan.environment_variables)
        assert any("boto3" in d for d in plan.runtime_dependencies)

    def test_jobs_adds_redis_infra(self) -> None:
        plan = resolve_plan(
            _definition(modules=("background-jobs",), sql=None, migrations=False)
        )
        assert plan.features.redis is True
        assert plan.features.redis_nosql is False
        assert plan.features.rq is True
        assert any(p.id == "worker" for p in plan.processes)
        assert any(v.name == "REDIS_URL" for v in plan.environment_variables)
        assert any("rq" in d for d in plan.runtime_dependencies)

    def test_jobs_reuse_nosql_redis(self) -> None:
        plan = resolve_plan(
            _definition(
                modules=("background-jobs",),
                sql=None,
                migrations=False,
                nosql="redis",
            )
        )
        assert plan.features.redis is True
        assert plan.features.redis_nosql is True
        assert plan.features.nosql is True
        redis_deps = [d for d in plan.runtime_dependencies if d.startswith("redis")]
        assert len(redis_deps) == 1

    def test_email_smtp_env(self) -> None:
        plan = resolve_plan(
            _definition(modules=("email",), sql=None, migrations=False)
        )
        names = {v.name for v in plan.environment_variables}
        assert {"SMTP_HOST", "SMTP_PORT", "EMAIL_FROM"} <= names
        assert plan.features.redis is False

    def test_all_modules_dense(self) -> None:
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
                storage=StorageOptions(backend="s3", minio=True),
            )
        )
        assert plan.features.background_jobs
        assert plan.features.email
        assert plan.features.webhooks
        assert plan.features.minio
        assert plan.docker_services == ("db", "redis", "minio")
        deps = " ".join(plan.runtime_dependencies)
        assert "boto3" in deps
        assert "rq" in deps
        assert "httpx" in deps
        assert deps.count("redis") == 1
        sections = {s.title for s in plan.summary_sections()}
        assert "Storage" in sections
        assert "Background Jobs" in sections
        assert "Processes" in sections

    def test_no_module_regression(self) -> None:
        plan = resolve_plan(_definition(modules=(), sql=None, migrations=False))
        assert plan.features.redis is False
        assert plan.processes[0].id == "api"
        assert len(plan.processes) == 1
        assert not any(
            x in " ".join(plan.runtime_dependencies)
            for x in ("boto3", "rq", "httpx>=")
        )

    def test_next_steps_include_worker_hint(self) -> None:
        plan = resolve_plan(
            _definition(modules=("background-jobs",), sql=None, migrations=False)
        )
        steps = next_steps_for(plan, destination_name="stage2-api")
        assert any("worker" in s for s in steps)


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
def test_stage2_dry_run_parity_files_local(
    tmp_path: Path,
    framework: str,
    architecture: ArchitectureStyle,
) -> None:
    definition = _definition(
        framework=framework,
        architecture=architecture,
        modules=("files",),
        migrations=framework != "django",
    )
    planned = planned_output_paths(resolve_plan(definition))
    result = generate_project(definition, base_dir=tmp_path)
    assert planned == result.files_written
    assert any("file" in p.lower() for p in planned)


def test_products_unchanged_no_stage2_deps() -> None:
    plan = resolve_plan(_definition(modules=("products", "categories")))
    blob = " ".join(plan.runtime_dependencies)
    assert "boto3" not in blob
    assert "rq" not in blob
    assert plan.features.email is False
    assert plan.features.minio is False
