"""Locate and render Jinja2 project templates from a GenerationPlan."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from forge.generator.errors import GenerationError
from forge.generator.plan import GenerationPlan

_PACKAGE_DIR_TOKEN = "__package__"
_TEMPLATE_SUFFIX = ".j2"
_SHARED_DIR_NAME = "_shared"
_INCLUDES_DIR_NAME = "_includes"


@dataclass(frozen=True)
class PlannedOutput:
    """One template file that generation would emit to a destination path."""

    template_path: Path
    relative_path: Path

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


def includes_dir(plan: GenerationPlan) -> Path | None:
    """Jinja include/macro root (not emitted to generated projects)."""
    path = (
        templates_root()
        / plan.definition.language.value
        / _INCLUDES_DIR_NAME
    )
    return path if path.is_dir() else None


def create_env(
    template_dir: Path,
    *,
    extra_dirs: list[Path] | None = None,
) -> Environment:
    searchpath = [str(template_dir)]
    if extra_dirs:
        searchpath.extend(str(path) for path in extra_dirs if path.is_dir())
    return Environment(
        loader=FileSystemLoader(searchpath),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def iter_template_files(template_dir: Path) -> Iterator[Path]:
    for path in sorted(template_dir.rglob("*")):
        if path.is_file():
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
    if name == ".env.example.j2" and not plan.emits_env_example:
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


def iter_planned_outputs_from_dir(
    template_dir: Path,
    plan: GenerationPlan,
) -> Iterator[PlannedOutput]:
    """Yield emit jobs from one template root (framework or ``_shared``)."""
    for source in iter_template_files(template_dir):
        relative = source.relative_to(template_dir)
        if not should_emit(relative, plan):
            continue
        yield PlannedOutput(
            template_path=source,
            relative_path=output_relative_path(relative, plan),
        )


def planned_outputs(plan: GenerationPlan) -> tuple[PlannedOutput, ...]:
    """Discover every file generation would write for ``plan`` (no I/O writes).

    Uses the same framework tree, ``_shared`` overlay, module template mounts,
    ``should_emit``, and path transformation as real generation. ``_includes``
    is never emitted.
    """
    template_dir = templates_root() / plan.template_subdir
    if not template_dir.is_dir():
        raise GenerationError(f"Template directory not found: {template_dir}")

    jobs: list[PlannedOutput] = list(
        iter_planned_outputs_from_dir(template_dir, plan)
    )

    shared = shared_template_dir(plan)
    if (
        shared is not None
        and shared.resolve() != template_dir.resolve()
    ):
        jobs.extend(iter_planned_outputs_from_dir(shared, plan))

    jobs.extend(_iter_module_planned_outputs(plan))

    if not jobs:
        raise GenerationError(f"No template files emitted from {template_dir}")

    _assert_no_output_collisions(jobs)
    return tuple(jobs)


def _module_mount_dirs(plan: GenerationPlan) -> list[Path]:
    """Resolved template roots for module / foundation mounts."""
    contrib = plan.contributions
    if contrib is None or not contrib.template_mounts:
        return []
    root = templates_root() / plan.definition.language.value
    dirs: list[Path] = []
    for mount in contrib.template_mounts:
        path = root / mount.source_subdir
        if not path.is_dir():
            raise GenerationError(
                f"Module template directory not found: {path}"
            )
        dirs.append(path)
    return dirs


def _iter_module_planned_outputs(plan: GenerationPlan) -> list[PlannedOutput]:
    jobs: list[PlannedOutput] = []
    for mount_dir in _module_mount_dirs(plan):
        jobs.extend(iter_planned_outputs_from_dir(mount_dir, plan))
    return jobs


def _assert_no_output_collisions(jobs: list[PlannedOutput]) -> None:
    seen: dict[str, Path] = {}
    for job in jobs:
        key = job.relative_path.as_posix()
        prior = seen.get(key)
        if prior is not None:
            raise GenerationError(
                "Template output collision for "
                f"{key!r}:\n  {prior}\n  {job.template_path}"
            )
        seen[key] = job.template_path


def planned_output_paths(plan: GenerationPlan) -> tuple[str, ...]:
    """Sorted destination-relative paths that generation would write."""
    return tuple(sorted(job.relative_path.as_posix() for job in planned_outputs(plan)))


def render_tree(
    template_dir: Path,
    destination: Path,
    plan: GenerationPlan,
) -> list[Path]:
    """Render framework templates, ``_shared``, then module mounts."""
    if not template_dir.is_dir():
        raise GenerationError(f"Template directory not found: {template_dir}")

    include_roots = [path for path in (includes_dir(plan),) if path is not None]

    # Discover all jobs first so collisions fail before any writes.
    all_jobs = list(planned_outputs(plan))

    roots_in_order: list[Path] = [template_dir.resolve()]
    shared = shared_template_dir(plan)
    if shared is not None and shared.resolve() != template_dir.resolve():
        roots_in_order.append(shared.resolve())
    roots_in_order.extend(path.resolve() for path in _module_mount_dirs(plan))

    jobs_by_root: dict[Path, list[PlannedOutput]] = {
        root: [] for root in roots_in_order
    }
    for job in all_jobs:
        root = _template_root_for(job.template_path, plan).resolve()
        if root not in jobs_by_root:
            jobs_by_root[root] = []
            roots_in_order.append(root)
        jobs_by_root[root].append(job)

    written: list[Path] = []
    for root in roots_in_order:
        jobs = jobs_by_root.get(root, [])
        if not jobs:
            continue
        written.extend(
            _render_planned_outputs(
                root,
                jobs,
                destination,
                plan,
                extra_dirs=include_roots,
            )
        )

    if not written:
        raise GenerationError(f"No template files emitted from {template_dir}")

    return written


def _template_root_for(template_path: Path, plan: GenerationPlan) -> Path:
    """Find which known template root contains ``template_path``."""
    candidates = [templates_root() / plan.template_subdir]
    shared = shared_template_dir(plan)
    if shared is not None:
        candidates.append(shared)
    candidates.extend(_module_mount_dirs(plan))
    resolved = template_path.resolve()
    for root in candidates:
        try:
            resolved.relative_to(root.resolve())
            return root
        except ValueError:
            continue
    raise GenerationError(f"Cannot locate template root for {template_path}")


def _render_planned_outputs(
    template_dir: Path,
    jobs: list[PlannedOutput],
    destination: Path,
    plan: GenerationPlan,
    *,
    extra_dirs: list[Path] | None = None,
) -> list[Path]:
    """Render planned outputs from one template root into ``destination``."""
    env = create_env(template_dir, extra_dirs=extra_dirs)
    written: list[Path] = []
    jinja_ctx = plan.as_jinja_dict()

    for job in jobs:
        target = destination / job.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        source = job.template_path

        if source.name.endswith(_TEMPLATE_SUFFIX):
            template_name = source.relative_to(template_dir).as_posix()
            content = env.get_template(template_name).render(**jinja_ctx)
            target.write_text(content, encoding="utf-8")
        else:
            target.write_bytes(source.read_bytes())

        written.append(job.relative_path)

    return written
