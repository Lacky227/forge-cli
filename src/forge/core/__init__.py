"""Core domain: normalized project definitions, independent of CLI UI."""

from forge.core.compatibility import (
    SUPPORTED_GENERATION_CASES,
    GenerationCase,
    executable_smoke_cases,
    supported_generation_cases,
)
from forge.core.config import ConfigError, definition_from_config, load_forge_config
from forge.core.definition import AuthenticationOptions, Capabilities, ProjectDefinition
from forge.core.modules import (
    MODULE_LABELS,
    MODULE_ORDER,
    ModuleId,
    StorageBackend,
    expand_module_dependencies,
    normalize_modules,
)
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
    "MODULE_LABELS",
    "MODULE_ORDER",
    "PRESETS",
    "SUPPORTED_GENERATION_CASES",
    "ArchitectureStyle",
    "AuthenticationOptions",
    "Capabilities",
    "ConfigError",
    "GenerationCase",
    "Language",
    "ModuleId",
    "Preset",
    "PresetError",
    "ProjectDefinition",
    "ProjectType",
    "StorageBackend",
    "definition_from_config",
    "definition_from_preset",
    "executable_smoke_cases",
    "expand_module_dependencies",
    "get_preset",
    "list_presets",
    "load_forge_config",
    "normalize_modules",
    "resolve_destination",
    "supported_generation_cases",
    "to_package_name",
]
