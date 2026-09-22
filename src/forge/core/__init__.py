"""Core domain: normalized project definitions, independent of CLI UI."""

from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.naming import resolve_destination, to_package_name
from forge.core.types import ArchitectureStyle, Language, ProjectType

__all__ = [
    "ArchitectureStyle",
    "Capabilities",
    "Language",
    "ProjectDefinition",
    "ProjectType",
    "resolve_destination",
    "to_package_name",
]
