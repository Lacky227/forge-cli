"""Core domain: normalized project definitions, independent of CLI UI."""

from forge.core.config import ConfigError, definition_from_config, load_forge_config
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.naming import resolve_destination, to_package_name
from forge.core.presets import (
    PRESETS,
    Preset,
    PresetError,
    definition_from_preset,
    get_preset,
    list_presets,
)
from forge.core.types import ArchitectureStyle, Language, ProjectType

__all__ = [
    "ArchitectureStyle",
    "Capabilities",
    "ConfigError",
    "Language",
    "PRESETS",
    "Preset",
    "PresetError",
    "ProjectDefinition",
    "ProjectType",
    "definition_from_config",
    "definition_from_preset",
    "get_preset",
    "list_presets",
    "load_forge_config",
    "resolve_destination",
    "to_package_name",
]
