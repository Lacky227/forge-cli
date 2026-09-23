"""Phase 3: generated-project developer experience consistency."""

from __future__ import annotations

from pathlib import Path

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import generate_project, resolve_plan
from forge.generator.engine import GenerationResult


def _def(
    *,
    name: str = "dx-app",
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


def _generate(tmp_path: Path, definition: ProjectDefinition) -> GenerationResult:
    return generate_project(definition, base_dir=tmp_path)


def test_env_example_matches_plan_postgres(tmp_path: Path) -> None:
    result = _generate(
        tmp_path,
        _def(sql="postgresql", migrations=True, docker=True),
    )
    plan = result.plan
    env_path = result.destination / ".env.example"
    assert env_path.is_file()
    text = env_path.read_text(encoding="utf-8")
    for spec in plan.environment_variables:
        assert f"{spec.name}={spec.example}" in text
    assert set(text.strip().splitlines()) == {
        f"{s.name}={s.example}" for s in plan.environment_variables
    }


def test_env_example_absent_for_no_persistence(tmp_path: Path) -> None:
    result = _generate(tmp_path, _def())
    assert not (result.destination / ".env.example").exists()
    assert result.plan.environment_variables == ()
    assert result.plan.emits_env_example is False


def test_env_example_absent_for_docker_only(tmp_path: Path) -> None:
    result = _generate(tmp_path, _def(docker=True))
    assert result.plan.environment_variables == ()
    assert not (result.destination / ".env.example").exists()
    compose = (result.destination / "docker-compose.yml").read_text(encoding="utf-8")
    assert "env_file" not in compose


def test_env_example_mongo_only(tmp_path: Path) -> None:
    result = _generate(tmp_path, _def(nosql="mongodb"))
    text = (result.destination / ".env.example").read_text(encoding="utf-8")
    assert "MONGODB_URL=" in text
    assert "MONGODB_DATABASE=" in text
    assert "DATABASE_URL" not in text


def test_env_example_sql_redis(tmp_path: Path) -> None:
    result = _generate(
        tmp_path,
        _def(sql="postgresql", nosql="redis", docker=True),
    )
    text = (result.destination / ".env.example").read_text(encoding="utf-8")
    assert "DATABASE_URL=" in text
    assert "REDIS_URL=" in text
    assert "POSTGRES_USER=" in text


def test_env_example_django_postgres(tmp_path: Path) -> None:
    result = _generate(
        tmp_path,
        _def(framework="django", sql="postgresql", docker=True),
    )
    text = (result.destination / ".env.example").read_text(encoding="utf-8")
    assert "DJANGO_SECRET_KEY=" in text
    assert "POSTGRES_HOST=" in text
    assert "DATABASE_URL" not in text


def test_env_example_sqlite_mongodb(tmp_path: Path) -> None:
    result = _generate(
        tmp_path,
        _def(framework="flask", sql="sqlite", nosql="mongodb", docker=True),
    )
    text = (result.destination / ".env.example").read_text(encoding="utf-8")
    assert "DATABASE_URL=" in text
    assert "MONGODB_URL=" in text
    assert "POSTGRES_" not in text


def test_readme_capability_gating(tmp_path: Path) -> None:
    result = _generate(
        tmp_path,
        _def(
            sql="postgresql",
            nosql="redis",
            migrations=True,
            docker=True,
            ci="github-actions",
            architecture=ArchitectureStyle.MODULAR_MONOLITH,
        ),
    )
    readme = (result.destination / "README.md").read_text(encoding="utf-8")
    assert "SQL: postgresql" in readme
    assert "NoSQL: Redis" in readme
    assert "CI: GitHub Actions" in readme
    assert "cp .env.example .env" in readme
    assert "`DATABASE_URL`" in readme
    assert "`REDIS_URL`" in readme
    assert "docker compose up -d db redis" in readme
    assert "GET /health" in readme
    assert ".github/workflows/ci.yml" in readme
    assert "uv run ruff check ." in readme
    assert "uv run pytest" in readme


def test_readme_no_persistence_omits_env_and_ci(tmp_path: Path) -> None:
    result = _generate(tmp_path, _def(testing=False, linting=True))
    readme = (result.destination / "README.md").read_text(encoding="utf-8")
    assert "cp .env.example" not in readme
    assert "## CI" not in readme
    assert "## Tests" not in readme
    assert "## Lint" in readme
    assert "NoSQL" not in readme


def test_fastapi_all_architectures_health_path(tmp_path: Path) -> None:
    for architecture in ArchitectureStyle:
        result = _generate(
            tmp_path / architecture.value,
            _def(architecture=architecture, name=f"fa-{architecture.value}"),
        )
        assert result.plan.health_path == "/health"
        readme = (result.destination / "README.md").read_text(encoding="utf-8")
        assert "GET /health" in readme
        if result.plan.features.testing:
            test = (
                result.destination / "tests" / "test_health.py"
            ).read_text(encoding="utf-8")
            assert '"/health"' in test or "'/health'" in test
            assert "/api/health" not in test


def test_flask_and_django_health_paths(tmp_path: Path) -> None:
    flask = _generate(tmp_path / "flask", _def(framework="flask", name="flask-dx"))
    assert flask.plan.health_path == "/api/health"
    assert "GET /api/health" in (flask.destination / "README.md").read_text(
        encoding="utf-8"
    )

    django = _generate(
        tmp_path / "django",
        _def(framework="django", sql="sqlite", name="django-dx"),
    )
    assert django.plan.health_path == "/api/health/"
    assert "GET /api/health/" in (django.destination / "README.md").read_text(
        encoding="utf-8"
    )


def test_compose_services_and_env_file(tmp_path: Path) -> None:
    result = _generate(
        tmp_path,
        _def(sql="postgresql", nosql="mongodb", docker=True),
    )
    compose = (result.destination / "docker-compose.yml").read_text(encoding="utf-8")
    assert "env_file:" in compose
    assert "  db:" in compose
    assert "  mongodb:" in compose
    assert result.plan.docker_services == ("db", "mongodb")


def test_dockerfile_healthcheck_uses_health_path(tmp_path: Path) -> None:
    result = _generate(tmp_path, _def(docker=True, framework="django", sql="sqlite"))
    dockerfile = (result.destination / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in dockerfile
    assert result.plan.health_path in dockerfile
    assert "urllib.request" in dockerfile


def test_next_steps_include_env_copy_when_needed(tmp_path: Path) -> None:
    with_env = _generate(
        tmp_path / "with",
        _def(sql="sqlite", name="with-env"),
    )
    steps = with_env.next_steps()
    assert "cp .env.example .env" in steps
    assert steps.index("uv sync") < steps.index("cp .env.example .env")

    bare = _generate(tmp_path / "bare", _def(name="bare"))
    assert "cp .env.example .env" not in bare.next_steps()


def test_next_steps_docker_services_order(tmp_path: Path) -> None:
    result = _generate(
        tmp_path,
        _def(sql="postgresql", nosql="redis", docker=True, migrations=True),
    )
    steps = result.next_steps()
    assert "cp .env.example .env" in steps
    assert "docker compose up -d db redis" in steps
    assert steps.index("cp .env.example .env") < steps.index(
        "docker compose up -d db redis"
    )
    # App container is not started by next_steps; local run follows migrate.
    assert not any(s.startswith("docker compose up -d") and "api" in s for s in steps)
    assert result.plan.run_command in steps
    assert steps.index("docker compose up -d db redis") < steps.index(
        result.plan.migrate_command or result.plan.run_command
    )


def test_next_steps_docker_only_omits_bare_compose_up(tmp_path: Path) -> None:
    """Docker packaging without persistence: no invalid bare compose up -d."""
    result = _generate(tmp_path, _def(docker=True, name="docker-only"))
    assert result.plan.docker_services == ()
    steps = result.next_steps()
    assert not any(s.startswith("docker compose") for s in steps)
    readme = (result.destination / "README.md").read_text(encoding="utf-8")
    assert "docker compose up --build" in readme
    assert "docker compose up -d" not in readme


def test_resolve_health_paths_normalized() -> None:
    assert (
        resolve_plan(
            _def(architecture=ArchitectureStyle.CLEAN)
        ).health_path
        == "/health"
    )
    assert resolve_plan(_def()).health_path == "/health"
