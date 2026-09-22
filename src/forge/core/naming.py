"""Project and package naming helpers (filesystem-safe, cross-platform)."""

from __future__ import annotations

import re
from pathlib import Path

_PACKAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def to_package_name(project_name: str) -> str:
    """Convert a project name to a valid Python package identifier.

    ``my-awesome-api`` → ``my_awesome_api``
    """
    normalized = project_name.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized)
    if normalized and normalized[0].isdigit():
        normalized = f"app_{normalized}"
    if not _PACKAGE_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"cannot derive a Python package name from {project_name!r}"
        )
    return normalized


def resolve_destination(project_name: str, base_dir: Path | None = None) -> Path:
    """Resolve ``./<project_name>`` under ``base_dir`` (default: cwd).

    Rejects names that look like paths to prevent traversal surprises.
    """
    if Path(project_name).name != project_name:
        raise ValueError(
            f"project name must not contain path separators: {project_name!r}"
        )
    if project_name in {".", ".."}:
        raise ValueError(f"invalid project name: {project_name!r}")

    root = (base_dir or Path.cwd()).resolve()
    destination = (root / project_name).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"project destination escapes the working directory: {project_name!r}"
        ) from exc
    return destination
