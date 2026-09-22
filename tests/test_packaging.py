"""Packaging-focused tests: artifact contents and clean-install generation.

Heavy clean-install coverage also lives in ``scripts/packaging_smoke.sh`` (CI).
These pytest cases keep the contract checked in the normal suite without
always rebuilding wheels.
"""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from forge.generator.render import templates_root

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_templates_root_resolves_python_tree() -> None:
    root = templates_root()
    assert (root / "python" / "fastapi").is_dir()
    assert (root / "python" / "django").is_dir()
    assert (root / "python" / "flask").is_dir()


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
    wheels = list(dist.glob("forge_cli-*.whl"))
    assert len(wheels) == 1, wheels
    with zipfile.ZipFile(wheels[0]) as zf:
        names = zf.namelist()
    templates = [n for n in names if n.startswith("forge/templates/python/")]
    assert len(templates) >= 50
    assert any("fastapi" in n for n in templates)
    assert any("django" in n for n in templates)
    assert any("flask" in n for n in templates)
    assert not any(n.startswith("tests/") for n in names)
    assert not any(".cursor" in n for n in names)


@pytest.mark.packaging
def test_clean_wheel_install_generates_outside_repo(tmp_path: Path) -> None:
    """Install the wheel into a venv outside the checkout and generate a project.

    This is the anti-false-positive check: generation must work with only the
    packaged ``forge/templates`` tree available.
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
    wheel = next(dist.glob("forge_cli-*.whl"))

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

    gen_dir = tmp_path / "gen"
    gen_dir.mkdir()
    env = {**os.environ, "PATH": str(forge_bin.parent) + os.pathsep + os.environ.get("PATH", "")}
    # Ensure we do not inherit a FORGE_TEMPLATES_ROOT pointing at the repo.
    env.pop("FORGE_TEMPLATES_ROOT", None)

    version = subprocess.check_output(
        [str(forge_bin), "--version"], cwd=gen_dir, env=env, text=True
    ).strip()
    assert version.startswith("forge ")

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
