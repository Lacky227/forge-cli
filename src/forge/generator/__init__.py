"""Project generation from a ProjectDefinition."""

from forge.generator.engine import (
    GenerationResult,
    generate_from_plan,
    generate_project,
)
from forge.generator.errors import GenerationError
from forge.generator.plan import GenerationFeatures, GenerationPlan, PlanSummarySection
from forge.generator.resolve import resolve_plan

__all__ = [
    "GenerationError",
    "GenerationFeatures",
    "GenerationPlan",
    "GenerationResult",
    "PlanSummarySection",
    "generate_from_plan",
    "generate_project",
    "resolve_plan",
]
