"""Core domain: normalized project definitions, independent of CLI UI."""

from forge.core.definition import ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType

__all__ = [
    "ArchitectureStyle",
    "Language",
    "ProjectDefinition",
    "ProjectType",
]
