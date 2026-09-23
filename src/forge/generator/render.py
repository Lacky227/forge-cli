"""Locate and render Jinja2 project templates from a GenerationPlan."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from forge.generator.errors import GenerationError
from forge.generator.plan import GenerationPlan

_PACKAGE_DIR_TOKEN = "__package__"
_TEMPLATE_SUFFIX = ".j2"
_SHARED_DIR_NAME = "_shared"

_DOCKER_FILES = frozenset({"Dockerfile.j2", "docker-compose.yml.j2"})
_SQL_ONLY_FILES = frozenset(
    {"database.py.j2", "models.py.j2", "base.py.j2", "ports.py.j2"}
)
_SQL_ONLY_DIR_NAMES = frozenset({"persistence"})
_MONGODB_FILES = frozenset({"mongodb.py.j2"})
_REDIS_FILES = frozenset({"redis_client.py.j2"})


def templates_root() -> Path:
    """Resolve the templates directory for installed or development layouts.

    Resolution order:

    1. ``FORGE_TEMPLATES_ROOT`` (explicit override)
    2. Packaged data at ``forge/templates`` (wheel force-include / adjacent to
       the installed package)
    3. Development checkout: ``<repo>/templates`` next to ``pyproject.toml``

    Parent directories are not scanned generically — that would risk picking up
    unrelated ``templates/`` trees and false positives during packaging tests.
    """
    override = os.environ.get("FORGE_TEMPLATES_ROOT")
    if override:
        path = Path(override).expanduser()
        if not path.is_dir():
            raise GenerationError(
                f"FORGE_TEMPLATES_ROOT is not a directory: {override}"
            )
        return path.resolve()

    # Installed wheel / sdist: hatch force-includes repo templates → forge/templates
    packaged = Path(__file__).resolve().parent.parent / "templates"
    if (packaged / "python").is_dir():
        return packaged

    # Editable / source checkout: src/forge/generator/render.py → repo root
    for parent in Path(__file__).resolve().parents:
        pyproject = parent / "pyproject.toml"
        candidate = parent / "templates"
        if (
            pyproject.is_file()
            and (candidate / "python").is_dir()
            and _looks_like_forge_pyproject(pyproject)
        ):
            return candidate.resolve()

    raise GenerationError(
        "Cannot locate Forge templates. Expected forge/templates/python/… "
        "in the installed package, or templates/python/… at the repository root."
    )


def _looks_like_forge_pyproject(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return 'name = "forge-scaffolder"' in text


def shared_template_dir(plan: GenerationPlan) -> Path | None:
    """Language-level shared overlay (e.g. ``templates/python/_shared``)."""
    shared = (
        templates_root()
        / plan.definition.language.value
        / _SHARED_DIR_NAME
    )
    return shared if shared.is_dir() else None


def create_env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def iter_template_files(template_dir: Path) -> Iterator[Path]:
    for path in sorted(template_dir.rglob("*")):
        if path.is_file() and not path.name.startswith(".gitkeep"):
            yield path
        elif path.is_file() and path.name == ".gitkeep":
            yield path


def should_emit(relative: Path, plan: GenerationPlan) -> bool:
    """Skip capability-specific template paths using resolved features."""
    features = plan.features
    parts = relative.parts
    name = relative.name

    # Shared GitHub Actions workflow — only when CI is resolved on.
    if parts and parts[0] == ".github":
        return features.ci

    if name in _DOCKER_FILES and not features.docker:
        return False
    # Project-level Alembic tree only (not Django app migrations packages).
    if parts and parts[0] == "migrations" and not features.migrations:
        return False
    if name.startswith("alembic") and not features.migrations:
        return False
    if "tests" in parts and not features.testing:
        return False
    if name == ".env.example.j2" and not features.env_example:
        return False
    if name in _SQL_ONLY_FILES and not features.database:
        return False
    if "models" in parts and name != "models.py.j2" and not features.database:
        return False
    if any(part in _SQL_ONLY_DIR_NAMES for part in parts) and not features.database:
        return False
    if name in _MONGODB_FILES and not features.mongodb:
        return False
    if name in _REDIS_FILES and not features.redis:
        return False
    return True


def output_relative_path(relative: Path, plan: GenerationPlan) -> Path:
    """Map a template-relative path to the destination-relative path."""
    parts: list[str] = []
    for part in relative.parts:
        if part == _PACKAGE_DIR_TOKEN:
            parts.append(plan.package_name)
        else:
            parts.append(part)
    out = Path(*parts) if parts else Path()
    if out.name.endswith(_TEMPLATE_SUFFIX):
        out = out.with_name(out.name[: -len(_TEMPLATE_SUFFIX)])
    return out


def render_tree(
    template_dir: Path,
    destination: Path,
    plan: GenerationPlan,
) -> list[Path]:
    """Render framework templates, then any language-level ``_shared`` overlay."""
    if not template_dir.is_dir():
        raise GenerationError(f"Template directory not found: {template_dir}")

    written: list[Path] = []
    written.extend(_render_template_dir(template_dir, destination, plan))

    shared = shared_template_dir(plan)
    if (
        shared is not None
        and shared.resolve() != template_dir.resolve()
    ):
        written.extend(_render_template_dir(shared, destination, plan))

    if not written:
        raise GenerationError(f"No template files emitted from {template_dir}")

    return written


def _render_template_dir(
    template_dir: Path,
    destination: Path,
    plan: GenerationPlan,
) -> list[Path]:
    """Render one template root into ``destination`` using resolved features."""
    env = create_env(template_dir)
    written: list[Path] = []
    jinja_ctx = plan.as_jinja_dict()

    for source in iter_template_files(template_dir):
        relative = source.relative_to(template_dir)
        if not should_emit(relative, plan):
            continue

        target_rel = output_relative_path(relative, plan)
        target = destination / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)

        if source.name.endswith(_TEMPLATE_SUFFIX):
            template_name = relative.as_posix()
            content = env.get_template(template_name).render(**jinja_ctx)
            target.write_text(content, encoding="utf-8")
        else:
            target.write_bytes(source.read_bytes())

        written.append(target_rel)

    return written
