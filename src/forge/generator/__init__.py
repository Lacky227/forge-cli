"""Project generation from a ProjectDefinition."""

from forge.generator.engine import (
    GenerationPreview,
    GenerationResult,
    generate_from_plan,
    generate_project,
    next_steps_for,
    preview_from_plan,
    preview_project,
    validate_generation_destination,
)
from forge.generator.errors import GenerationError
from forge.generator.plan import (
    EnvVarSpec,
    GeneratedSecretSpec,
    GenerationFeatures,
    GenerationPlan,
    PlanSummarySection,
)
from forge.generator.render import PlannedOutput, planned_output_paths, planned_outputs
from forge.generator.resolve import resolve_plan

__all__ = [
    "EnvVarSpec",
    "GeneratedSecretSpec",
    "GenerationError",
    "GenerationFeatures",
    "GenerationPlan",
    "GenerationPreview",
    "GenerationResult",
    "PlanSummarySection",
    "PlannedOutput",
    "generate_from_plan",
    "generate_project",
    "next_steps_for",
    "planned_output_paths",
    "planned_outputs",
    "preview_from_plan",
    "preview_project",
    "resolve_plan",
    "validate_generation_destination",
]
