"""Generation engine: ProjectDefinition → filesystem project."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from forge.core import catalog
from forge.core.definition import ProjectDefinition
from forge.core.naming import resolve_destination, to_package_name
from forge.generator.context import TemplateContext, template_subdir
from forge.generator.errors import GenerationError
from forge.generator.render import render_tree, templates_root


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a successful generation."""

    destination: Path
    definition: ProjectDefinition
    package_name: str
    files_written: tuple[str, ...] = field(default_factory=tuple)

    @property
    def entry_file(self) -> str:
        return f"src/{self.package_name}/main.py"

    def next_steps(self) -> list[str]:
        steps = [
            f"cd {self.destination.name}",
            "uv sync",
        ]
        caps = self.definition.capabilities
        if caps.database and caps.database_engine == "postgresql" and caps.docker:
            steps.append("docker compose up -d db")
        if caps.migrations:
            steps.append("uv run alembic upgrade head")
        steps.append(f"uv run fastapi dev {self.entry_file}")
        if caps.testing:
            steps.append("uv run pytest")
        if caps.linting:
            steps.append("uv run ruff check .")
        return steps


def generate_project(
    definition: ProjectDefinition,
    *,
    base_dir: Path | None = None,
    destination: Path | None = None,
) -> GenerationResult:
    """Materialize a project from ``definition``.

    Creates ``./<name>`` under ``base_dir`` (cwd by default) unless
    ``destination`` is provided. Refuses to overwrite an existing path.
    """
    _assert_supported(definition)

    package_name = to_package_name(definition.name)
    target = (
        destination.resolve()
        if destination is not None
        else resolve_destination(definition.name, base_dir=base_dir)
    )

    if target.exists():
        if target.is_dir() and any(target.iterdir()):
            raise GenerationError(
                f"destination already exists and is not empty: {target}"
            )
        if target.is_file():
            raise GenerationError(f"destination exists as a file: {target}")

    context = TemplateContext.from_definition(definition)
    template_dir = templates_root() / template_subdir(definition)

    target.mkdir(parents=True, exist_ok=True)
    try:
        written = render_tree(template_dir, target, context)
    except Exception:
        # Best-effort cleanup of a failed partial tree we created
        if target.is_dir() and target.exists():
            _safe_rmtree(target)
        raise

    return GenerationResult(
        destination=target,
        definition=definition,
        package_name=package_name,
        files_written=tuple(sorted(p.as_posix() for p in written)),
    )


def _assert_supported(definition: ProjectDefinition) -> None:
    if not catalog.is_generatable(
        definition.language,
        definition.framework,
        definition.project_type,
        definition.architecture,
    ):
        raise GenerationError(
            "Generation is not implemented yet for "
            f"{definition.language.value}/{definition.framework}/"
            f"{definition.project_type.value}/"
            f"{definition.architecture.value}. "
            "Currently supported: Python FastAPI REST API "
            "(simple or modular-monolith)."
        )


def _safe_rmtree(path: Path) -> None:
    import shutil

    try:
        shutil.rmtree(path)
    except OSError:
        pass
