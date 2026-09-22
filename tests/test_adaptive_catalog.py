"""Lightweight tests for adaptive capability mapping without terminal I/O."""

from __future__ import annotations

from forge.core.catalog import architectures_for, frameworks_for
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.types import ArchitectureStyle, Language, ProjectType


def test_cli_has_single_architecture_so_prompt_can_be_skipped() -> None:
    styles = architectures_for(ProjectType.CLI)
    assert styles == (ArchitectureStyle.SIMPLE,)


def test_rest_api_offers_multiple_architectures() -> None:
    styles = architectures_for(ProjectType.REST_API)
    assert ArchitectureStyle.MODULAR_MONOLITH in styles
    assert len(styles) > 1


def test_worker_frameworks_differ_from_api() -> None:
    api = set(frameworks_for(Language.PYTHON, ProjectType.REST_API))
    worker = set(frameworks_for(Language.PYTHON, ProjectType.WORKER))
    assert api.isdisjoint(worker)


def test_build_definition_from_plain_data() -> None:
    """Simulates a future non-interactive / config path."""
    data = {
        "name": "batch-worker",
        "language": "python",
        "project_type": "worker",
        "framework": "arq",
        "architecture": "simple",
        "capabilities": {
            "database": False,
            "docker": True,
            "testing": True,
        },
    }
    definition = ProjectDefinition.model_validate(data)
    assert definition.framework == "arq"
    assert isinstance(definition.capabilities, Capabilities)
    assert definition.capabilities.docker is True
