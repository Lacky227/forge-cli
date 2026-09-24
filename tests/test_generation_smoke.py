"""Executable generation smoke — install and validate generated projects.

Marked ``generation_smoke`` and excluded from the default suite (see
``pyproject.toml``). Only runs cases that do not require live PostgreSQL.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from forge.core.compatibility import GenerationCase, executable_smoke_cases
from forge.core.definition import AuthenticationOptions, Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator import generate_project


def _run(cmd: list[str], *, cwd: Path) -> None:
    env = {**os.environ}
    # Avoid inheriting the Forge repo venv into generated-project commands.
    env.pop("VIRTUAL_ENV", None)
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


@pytest.mark.generation_smoke
@pytest.mark.parametrize(
    "case",
    executable_smoke_cases(),
    ids=lambda c: c.id,
)
def test_executable_generation_smoke(case: GenerationCase, tmp_path: Path) -> None:
    result = generate_project(case.to_definition(), base_dir=tmp_path)
    root = result.destination
    plan = result.plan

    _run(["uv", "sync"], cwd=root)

    if case.framework == "django":
        _run(["uv", "run", "python", "manage.py", "check"], cwd=root)
        _run(["uv", "run", "python", "manage.py", "migrate"], cwd=root)
    elif case.framework == "fastapi":
        pkg = plan.package_name
        _run(
            ["uv", "run", "python", "-c", f"from {pkg}.main import app"],
            cwd=root,
        )
    elif case.framework == "flask":
        pkg = plan.package_name
        _run(
            [
                "uv",
                "run",
                "python",
                "-c",
                f"from {pkg} import create_app; create_app()",
            ],
            cwd=root,
        )

    if plan.features.migration_system == "alembic":
        assert (root / "alembic.ini").is_file()
        # Check revision environment imports without needing a live DB write.
        _run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "import alembic.config; alembic.config.Config('alembic.ini')",
            ],
            cwd=root,
        )

    if plan.features.testing:
        _run(["uv", "run", "pytest"], cwd=root)
    if plan.features.linting:
        _run(["uv", "run", "ruff", "check", "."], cwd=root)


@pytest.mark.generation_smoke
@pytest.mark.parametrize("framework", ["fastapi", "flask", "django"])
@pytest.mark.parametrize("architecture", tuple(ArchitectureStyle))
def test_stage3_security_matrix(
    framework: str,
    architecture: ArchitectureStyle,
    tmp_path: Path,
) -> None:
    """Execute every Stage 3 family with hardening + dense/recovery mix."""
    dense = architecture != ArchitectureStyle.MODULAR_MONOLITH
    project = ProjectDefinition(
        name=f"stage3-{framework}-{architecture.value}",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework=framework,
        architecture=architecture,
        capabilities=Capabilities(
            sql_database="sqlite",
            migrations=framework != "django",
            testing=True,
            linting=True,
        ),
        modules=(("authorization",) if dense else ("authentication",)),
        authentication=AuthenticationOptions(
            email_verification=True,
            password_reset=True,
        ),
    )
    root = generate_project(project, base_dir=tmp_path).destination
    _run(["uv", "sync"], cwd=root)
    if framework == "django":
        _run(["uv", "run", "python", "manage.py", "check"], cwd=root)
        _run(["uv", "run", "python", "manage.py", "migrate", "--noinput"], cwd=root)
        _run(
            [
                "uv",
                "run",
                "python",
                "manage.py",
                "makemigrations",
                "--check",
                "--dry-run",
            ],
            cwd=root,
        )
    else:
        _run(["uv", "run", "alembic", "upgrade", "head"], cwd=root)
    _run(["uv", "run", "pytest", "-q"], cwd=root)
    _run(["uv", "run", "ruff", "check", "."], cwd=root)
