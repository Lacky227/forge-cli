"""Generation engine: ProjectDefinition → GenerationPlan → filesystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from forge.core.definition import ProjectDefinition
from forge.core.naming import resolve_destination
from forge.generator.errors import GenerationError
from forge.generator.plan import GenerationPlan
from forge.generator.render import planned_output_paths, render_tree, templates_root
from forge.generator.resolve import resolve_plan


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a successful generation."""

    destination: Path
    plan: GenerationPlan
    files_written: tuple[str, ...] = field(default_factory=tuple)

    @property
    def definition(self) -> ProjectDefinition:
        return self.plan.definition

    @property
    def package_name(self) -> str:
        return self.plan.package_name

    @property
    def entry_file(self) -> str:
        return self.plan.entry_file

    def next_steps(self) -> list[str]:
        return next_steps_for(self.plan, destination_name=self.destination.name)


@dataclass(frozen=True)
class GenerationPreview:
    """Outcome of a dry-run: intended destination and files, nothing written."""

    destination: Path
    plan: GenerationPlan
    files: tuple[str, ...] = field(default_factory=tuple)

    @property
    def definition(self) -> ProjectDefinition:
        return self.plan.definition

    def next_steps(self) -> list[str]:
        return next_steps_for(self.plan, destination_name=self.destination.name)


def next_steps_for(plan: GenerationPlan, *, destination_name: str) -> list[str]:
    """Local-dev bootstrap commands for a resolved plan.

    ``docker compose up -d <services>`` lists *dependency* services only
    (``db`` / ``mongodb`` / ``redis`` / ``minio``). It is omitted when Docker
    is off or when there are no dependency services (Docker packaging alone).
    Full-stack ``docker compose up --build`` remains documented in the
    generated README Docker section.
    """
    steps = [
        f"cd {destination_name}",
        "uv sync",
    ]
    features = plan.features
    if plan.emits_env_example and not plan.emits_local_env:
        steps.append("cp .env.example .env")
    if features.docker and plan.docker_services:
        steps.append(
            f"docker compose up -d {' '.join(plan.docker_services)}"
        )
    if plan.migrate_command:
        steps.append(plan.migrate_command)
    steps.append(plan.run_command)
    if plan.worker_command:
        steps.append(f"# in another terminal: {plan.worker_command}")
    if features.testing:
        steps.append("uv run pytest")
    if features.linting:
        steps.append("uv run ruff check .")
    return steps


def validate_generation_destination(target: Path) -> None:
    """Apply the same destination conflict rules used by real generation.

    Does not create or modify the path.
    """
    if target.exists():
        if target.is_dir() and any(target.iterdir()):
            raise GenerationError(
                f"destination already exists and is not empty: {target}"
            )
        if target.is_file():
            raise GenerationError(f"destination exists as a file: {target}")


def generate_project(
    definition: ProjectDefinition,
    *,
    base_dir: Path | None = None,
    destination: Path | None = None,
) -> GenerationResult:
    """Resolve ``definition``, then materialize the project on disk.

    Resolution runs first so invalid combinations fail before any writes.
    """
    plan = resolve_plan(definition)
    return generate_from_plan(plan, base_dir=base_dir, destination=destination)


def generate_from_plan(
    plan: GenerationPlan,
    *,
    base_dir: Path | None = None,
    destination: Path | None = None,
) -> GenerationResult:
    """Write a project from an already-resolved plan."""
    target = _resolve_target(plan, base_dir=base_dir, destination=destination)
    validate_generation_destination(target)

    template_dir = templates_root() / plan.template_subdir
    target.mkdir(parents=True, exist_ok=True)
    try:
        written = render_tree(template_dir, target, plan)
    except Exception:
        if target.is_dir() and target.exists():
            _safe_rmtree(target)
        raise

    return GenerationResult(
        destination=target,
        plan=plan,
        files_written=tuple(sorted(p.as_posix() for p in written)),
    )


def preview_project(
    definition: ProjectDefinition,
    *,
    base_dir: Path | None = None,
    destination: Path | None = None,
) -> GenerationPreview:
    """Resolve ``definition`` and list intended outputs without writing."""
    plan = resolve_plan(definition)
    return preview_from_plan(plan, base_dir=base_dir, destination=destination)


def preview_from_plan(
    plan: GenerationPlan,
    *,
    base_dir: Path | None = None,
    destination: Path | None = None,
) -> GenerationPreview:
    """Dry-run generation for an already-resolved plan (zero filesystem writes)."""
    target = _resolve_target(plan, base_dir=base_dir, destination=destination)
    validate_generation_destination(target)
    return GenerationPreview(
        destination=target,
        plan=plan,
        files=planned_output_paths(plan),
    )


def _resolve_target(
    plan: GenerationPlan,
    *,
    base_dir: Path | None,
    destination: Path | None,
) -> Path:
    if destination is not None:
        return destination.resolve()
    return resolve_destination(plan.definition.name, base_dir=base_dir)


def _safe_rmtree(path: Path) -> None:
    import shutil

    try:
        shutil.rmtree(path)
    except OSError:
        pass
