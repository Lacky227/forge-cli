"""Packaging-focused tests: artifact contents and clean-install generation.

Heavy clean-install coverage also lives in ``scripts/packaging_smoke.sh`` (CI).
These pytest cases keep the contract checked in the normal suite without
always rebuilding wheels.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from forge.generator.render import templates_root

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_NAME = "forge-scaffolder"
DIST_VERSION = "0.5.0"
WHEEL_GLOB = "forge_scaffolder-*.whl"
SDIST_GLOB = "forge_scaffolder-*.tar.gz"


def test_templates_root_resolves_python_tree() -> None:
    root = templates_root()
    assert (root / "python" / "fastapi").is_dir()
    assert (root / "python" / "django").is_dir()
    assert (root / "python" / "flask").is_dir()
    assert (
        root / "python" / "_shared" / ".github" / "workflows" / "ci.yml.j2"
    ).is_file()


def test_templates_root_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "custom-templates"
    (fake / "python").mkdir(parents=True)
    monkeypatch.setenv("FORGE_TEMPLATES_ROOT", str(fake))
    assert templates_root() == fake.resolve()


@pytest.mark.packaging
def test_wheel_contains_runtime_templates(tmp_path: Path) -> None:
    """Build a wheel in an isolated dist dir and assert templates are packaged."""
    dist = tmp_path / "dist"
    dist.mkdir()
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(dist.glob(WHEEL_GLOB))
    assert len(wheels) == 1, wheels
    sdists = list(dist.glob(SDIST_GLOB))
    assert len(sdists) == 1, sdists
    with zipfile.ZipFile(wheels[0]) as zf:
        names = zf.namelist()
        metadata = zf.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode()
    assert f"Name: {DIST_NAME}" in metadata
    assert f"Version: {DIST_VERSION}" in metadata
    assert (
        "License-Expression: GPL-3.0-only" in metadata
        or "License: GPL-3.0-only" in metadata
    )
    assert any(n.endswith(("licenses/LICENSE", "/LICENSE")) for n in names)
    templates = [n for n in names if n.startswith("forge/templates/python/")]
    assert len(templates) >= 50
    assert any("fastapi" in n for n in templates)
    assert any("django" in n for n in templates)
    assert any("flask" in n for n in templates)
    assert any(n.endswith("mongodb.py.j2") for n in templates)
    assert any(n.endswith("redis_client.py.j2") for n in templates)
    assert any(
        "/modules/products/" in n for n in templates
    ), "missing products module templates"
    assert any(
        "/modules/categories/" in n for n in templates
    ), "missing categories module templates"
    assert any(
        "/modules/files/" in n for n in templates
    ), "missing files module templates"
    assert any(
        "/modules/background-jobs/" in n for n in templates
    ), "missing background-jobs module templates"
    assert any(
        "/modules/email/" in n for n in templates
    ), "missing email module templates"
    assert any(
        "/modules/webhooks/" in n for n in templates
    ), "missing webhooks module templates"
    auth_templates = [n for n in templates if "/modules/authentication/" in n]
    assert auth_templates, "missing authentication module templates"
    for framework in ("fastapi", "django", "flask"):
        for architecture in ("simple", "modular-monolith", "clean"):
            assert any(
                f"/modules/authentication/{framework}/{architecture}/" in n
                for n in auth_templates
            ), f"missing {framework}/{architecture} authentication templates"
    authorization_templates = [
        n for n in templates if "/modules/authorization/" in n
    ]
    assert authorization_templates, "missing authorization module templates"
    for framework in ("fastapi", "django", "flask"):
        for architecture in ("simple", "modular-monolith", "clean"):
            assert any(
                f"/modules/authorization/{framework}/{architecture}/" in n
                for n in authorization_templates
            ), f"missing {framework}/{architecture} authorization templates"
    assert any(n.endswith("auth_account_security_tests.py.j2") for n in templates)
    assert any(n.endswith("auth_security_email.py.j2") for n in templates)
    assert any(
        "/modules/_foundation/" in n for n in templates
    ), "missing module foundation templates"
    assert any(
        "/_shared/" in n and n.endswith("ci.yml.j2") for n in templates
    ), "missing shared GitHub Actions CI template"
    assert any(
        "/_shared/" in n and n.endswith(".env.example.j2") for n in templates
    )
    assert any(
        "/_includes/" in n and n.endswith("readme_macros.j2") for n in templates
    )
    assert not any(n.startswith("tests/") for n in names)
    assert not any(".cursor" in n for n in names)
    assert not any(".smoke" in n for n in names)
    with tarfile.open(sdists[0], "r:gz") as archive:
        sdist_names = archive.getnames()
    assert any(
        "/templates/python/modules/authorization/" in name
        for name in sdist_names
    ), "sdist is missing authorization templates"
    assert any(
        name.endswith("auth_account_security_tests.py.j2")
        for name in sdist_names
    ), "sdist is missing account-security templates"


@pytest.mark.packaging
def test_clean_wheel_install_generates_outside_repo(tmp_path: Path) -> None:
    """Install the wheel into a venv outside the checkout and generate a project.

    This is the anti-false-positive check: generation must work with only the
    packaged ``forge/templates`` tree available. Console script stays ``forge``.
    """
    # Work entirely under tmp_path (pytest's temp root is outside the repo).
    assert REPO_ROOT.resolve() not in tmp_path.resolve().parents

    dist = tmp_path / "dist"
    dist.mkdir()
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(dist.glob(WHEEL_GLOB))

    venv = tmp_path / "venv"
    subprocess.run(["uv", "venv", str(venv)], check=True, capture_output=True)
    if sys.platform == "win32":
        forge_bin = venv / "Scripts" / "forge.exe"
        python = venv / "Scripts" / "python.exe"
    else:
        forge_bin = venv / "bin" / "forge"
        python = venv / "bin" / "python"

    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert forge_bin.is_file()

    # Prove import path is the venv, not the repo src/
    loc = subprocess.check_output(
        [str(python), "-c", "import forge, pathlib; print(pathlib.Path(forge.__file__).resolve())"],
        text=True,
    ).strip()
    assert "site-packages" in loc.replace("\\", "/")
    assert str(REPO_ROOT / "src") not in loc

    dist_meta = subprocess.check_output(
        [
            str(python),
            "-c",
            (
                "from importlib.metadata import version, metadata; "
                f"print(metadata({DIST_NAME!r})['Name'], version({DIST_NAME!r}))"
            ),
        ],
        text=True,
    ).strip()
    assert dist_meta == f"{DIST_NAME} {DIST_VERSION}"

    gen_dir = tmp_path / "gen"
    gen_dir.mkdir()
    env = {**os.environ, "PATH": str(forge_bin.parent) + os.pathsep + os.environ.get("PATH", "")}
    # Ensure we do not inherit a FORGE_TEMPLATES_ROOT pointing at the repo.
    env.pop("FORGE_TEMPLATES_ROOT", None)

    version = subprocess.check_output(
        [str(forge_bin), "--version"], cwd=gen_dir, env=env, text=True
    ).strip()
    assert version == f"forge {DIST_VERSION}"

    subprocess.run(
        [str(forge_bin), "new", "wheel-api", "--preset", "fastapi-postgres"],
        cwd=gen_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    project = gen_dir / "wheel-api"
    assert (project / "pyproject.toml").is_file()
    assert (project / "src" / "wheel_api").is_dir()
    assert (project / "alembic.ini").is_file()
    # Presets leave CI off — shared workflow must not appear by default.
    assert not (project / ".github" / "workflows" / "ci.yml").exists()

    dry = subprocess.run(
        [
            str(forge_bin),
            "new",
            "dry-wheel",
            "--preset",
            "fastapi-postgres",
            "--dry-run",
        ],
        cwd=gen_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Dry run" in dry.stdout
    assert "pyproject.toml" in dry.stdout
    assert not (gen_dir / "dry-wheel").exists()

    auth_plan = subprocess.run(
        [str(forge_bin), "plan", "--preset", "fastapi-auth", "wheel-auth"],
        cwd=gen_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Authentication" in auth_plan.stdout
    assert "generated locally" in auth_plan.stdout
    auth_dry = subprocess.run(
        [
            str(forge_bin),
            "new",
            "wheel-auth-dry",
            "--preset",
            "fastapi-auth",
            "--dry-run",
        ],
        cwd=gen_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert ".env" in auth_dry.stdout
    assert not (gen_dir / "wheel-auth-dry").exists()
    auth_generate = subprocess.run(
        [str(forge_bin), "new", "wheel-auth", "--preset", "fastapi-auth"],
        cwd=gen_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    auth_env = (gen_dir / "wheel-auth" / ".env").read_text(encoding="utf-8")
    secret = next(
        line.partition("=")[2]
        for line in auth_env.splitlines()
        if line.startswith("AUTH_JWT_SECRET=")
    )
    assert len(secret) >= 43
    assert secret not in auth_generate.stdout
    assert secret not in auth_plan.stdout
    assert secret not in auth_dry.stdout

    stage2_cases = {
        "wheel-authz": """
modules:
  - authorization
authentication:
  registration: true
""",
        "wheel-recovery": """
modules:
  - authentication
authentication:
  email_verification: true
  password_reset: true
""",
        "wheel-security-dense": """
modules:
  - authorization
authentication:
  email_verification: true
  password_reset: true
""",
    }
    for project_name, security_yaml in stage2_cases.items():
        stage2_config = gen_dir / f"{project_name}.yaml"
        stage2_config.write_text(
            f"""
name: {project_name}
type: rest-api
framework: fastapi
architecture: simple
{security_yaml}
persistence:
  sql: sqlite
migrations: true
testing: true
linting: true
""",
            encoding="utf-8",
        )
        stage2_plan = subprocess.check_output(
            [str(forge_bin), "plan", "--config", str(stage2_config)],
            cwd=gen_dir,
            env=env,
            text=True,
        )
        assert "Authentication" in stage2_plan
        if project_name != "wheel-recovery":
            assert "Authorization" in stage2_plan
        stage2_dry = subprocess.check_output(
            [str(forge_bin), "new", "--config", str(stage2_config), "--dry-run"],
            cwd=gen_dir,
            env=env,
            text=True,
        )
        assert "Dry run" in stage2_dry
        assert not (gen_dir / project_name).exists()
        subprocess.run(
            [str(forge_bin), "new", "--config", str(stage2_config)],
            cwd=gen_dir,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        generated = gen_dir / project_name
        package = generated / "src" / project_name.replace("-", "_")
        if project_name != "wheel-recovery":
            assert (package / "authorization.py").is_file()
        if project_name != "wheel-authz":
            assert (package / "security_email.py").is_file()
            assert (generated / "tests" / "test_account_security.py").is_file()

    # Generate with CI from the installed wheel (packaged ``_shared`` template).
    config = gen_dir / "with-ci.yaml"
    config.write_text(
        """
name: wheel-ci
type: rest-api
framework: flask
architecture: simple
database: false
testing: true
linting: true
ci: github-actions
""",
        encoding="utf-8",
    )
    subprocess.run(
        [str(forge_bin), "new", "--config", str(config)],
        cwd=gen_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    ci_project = gen_dir / "wheel-ci"
    workflow = ci_project / ".github" / "workflows" / "ci.yml"
    assert workflow.is_file()
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "uv sync" in workflow_text
    assert "uv run pytest -q" in workflow_text
    assert "uv run ruff check ." in workflow_text

    # Modules must resolve from the installed wheel template tree.
    modules_config = gen_dir / "modules.yaml"
    modules_config.write_text(
        """
name: wheel-mods
type: rest-api
framework: fastapi
architecture: simple
modules:
  - products
  - categories
persistence:
  sql: sqlite
migrations: true
testing: true
linting: true
""",
        encoding="utf-8",
    )
    plan_out = subprocess.check_output(
        [str(forge_bin), "plan", "--config", str(modules_config)],
        cwd=gen_dir,
        env=env,
        text=True,
    )
    assert "Products" in plan_out
    assert "Categories" in plan_out
    subprocess.run(
        [str(forge_bin), "new", "--config", str(modules_config)],
        cwd=gen_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    mods_project = gen_dir / "wheel-mods"
    assert (mods_project / "src" / "wheel_mods" / "products.py").is_file()
    assert (mods_project / "src" / "wheel_mods" / "categories.py").is_file()
    assert (mods_project / "tests" / "test_products.py").is_file()
