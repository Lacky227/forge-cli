"""Tests for project modules (Stage 1: products / categories)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge.core.config import ConfigError, definition_from_config, load_forge_config
from forge.core.definition import Capabilities, ProjectDefinition
from forge.core.modules import ModuleId, normalize_modules
from forge.core.types import ArchitectureStyle, Language, ProjectType
from forge.generator.engine import generate_project
from forge.generator.render import planned_output_paths
from forge.generator.resolve import resolve_plan


def _definition(
    *,
    framework: str = "fastapi",
    architecture: ArchitectureStyle = ArchitectureStyle.SIMPLE,
    modules: tuple[str, ...] = (),
    sql: str | None = "sqlite",
    migrations: bool = True,
) -> ProjectDefinition:
    return ProjectDefinition(
        name="mod-api",
        language=Language.PYTHON,
        project_type=ProjectType.REST_API,
        framework=framework,
        architecture=architecture,
        capabilities=Capabilities(
            sql_database=sql,
            migrations=migrations,
            testing=True,
            linting=True,
            docker=False,
        ),
        modules=modules,
    )


class TestNormalizeModules:
    def test_empty(self) -> None:
        assert normalize_modules(None) == ()
        assert normalize_modules([]) == ()

    def test_dedupe_and_order(self) -> None:
        assert normalize_modules(["categories", "products", "products"]) == (
            "products",
            "categories",
        )

    def test_unknown(self) -> None:
        with pytest.raises(ValueError, match="unknown module"):
            normalize_modules(["products", "auth"])


class TestProjectDefinitionModules:
    def test_no_modules_ok_without_sql_for_fastapi(self) -> None:
        d = _definition(modules=(), sql=None, migrations=False)
        assert d.modules == ()

    def test_products_require_sql(self) -> None:
        with pytest.raises(ValueError, match="require an SQL database"):
            _definition(modules=("products",), sql=None, migrations=False)

    def test_both_modules(self) -> None:
        d = _definition(modules=("products", "categories"))
        assert d.modules == ("products", "categories")


class TestYamlModules:
    def test_modules_list(self, tmp_path: Path) -> None:
        path = tmp_path / "forge.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "cfg-api",
                    "type": "rest-api",
                    "framework": "fastapi",
                    "architecture": "simple",
                    "modules": ["categories", "products"],
                    "persistence": {"sql": "sqlite"},
                    "migrations": True,
                }
            ),
            encoding="utf-8",
        )
        definition = definition_from_config(path)
        assert definition.modules == ("products", "categories")

    def test_modules_omitted(self, tmp_path: Path) -> None:
        path = tmp_path / "forge.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "cfg-api",
                    "type": "rest-api",
                    "framework": "flask",
                    "architecture": "simple",
                    "persistence": {"sql": "sqlite"},
                }
            ),
            encoding="utf-8",
        )
        assert definition_from_config(path).modules == ()

    def test_unknown_module_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "forge.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "cfg-api",
                    "type": "rest-api",
                    "framework": "fastapi",
                    "architecture": "simple",
                    "modules": ["unknown-module"],
                    "persistence": {"sql": "sqlite"},
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="unknown module"):
            load_forge_config(path).to_definition()

    def test_modules_without_sql_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "forge.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "cfg-api",
                    "type": "rest-api",
                    "framework": "fastapi",
                    "architecture": "simple",
                    "modules": ["products"],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="SQL"):
            definition_from_config(path)


class TestResolveModules:
    def test_contributions_products(self) -> None:
        plan = resolve_plan(_definition(modules=("products",)))
        assert plan.contributions is not None
        assert plan.contributions.has_products
        assert not plan.contributions.has_categories
        assert not plan.contributions.products_link_categories
        assert len(plan.contributions.fastapi_routers) == 1
        assert plan.contributions.fastapi_routers[0].prefix == "/products"

    def test_relationship_when_both(self) -> None:
        plan = resolve_plan(
            _definition(modules=("products", "categories"))
        )
        assert plan.contributions is not None
        assert plan.contributions.products_link_categories
        sections = {s.title: s for s in plan.summary_sections()}
        assert "Modules" in sections
        assert "Relationship" in sections

    def test_flask_gets_pydantic(self) -> None:
        plan = resolve_plan(
            _definition(framework="flask", modules=("products",))
        )
        assert any(d.startswith("pydantic") for d in plan.runtime_dependencies)

    def test_flask_without_modules_no_pydantic(self) -> None:
        plan = resolve_plan(_definition(framework="flask", modules=()))
        assert not any(d.startswith("pydantic") for d in plan.runtime_dependencies)

    def test_django_apps(self) -> None:
        plan = resolve_plan(
            _definition(
                framework="django",
                architecture=ArchitectureStyle.MODULAR_MONOLITH,
                modules=("products", "categories"),
                migrations=False,
            )
        )
        assert plan.contributions is not None
        apps = {a.module_id: a.app_config for a in plan.contributions.django_apps}
        assert apps["products"] == "apps.products"
        assert apps["categories"] == "apps.categories"


@pytest.mark.parametrize(
    ("framework", "architecture", "modules"),
    [
        ("fastapi", ArchitectureStyle.SIMPLE, ("products",)),
        ("fastapi", ArchitectureStyle.MODULAR_MONOLITH, ("products", "categories")),
        ("fastapi", ArchitectureStyle.CLEAN, ("products", "categories")),
        ("django", ArchitectureStyle.SIMPLE, ("products",)),
        ("django", ArchitectureStyle.MODULAR_MONOLITH, ("categories",)),
        ("django", ArchitectureStyle.CLEAN, ("products", "categories")),
        ("flask", ArchitectureStyle.SIMPLE, ("categories",)),
        ("flask", ArchitectureStyle.MODULAR_MONOLITH, ("products",)),
        ("flask", ArchitectureStyle.CLEAN, ("products", "categories")),
    ],
)
def test_module_dry_run_parity(
    tmp_path: Path,
    framework: str,
    architecture: ArchitectureStyle,
    modules: tuple[str, ...],
) -> None:
    definition = _definition(
        framework=framework,
        architecture=architecture,
        modules=modules,
        migrations=framework != "django",
    )
    planned = planned_output_paths(resolve_plan(definition))
    result = generate_project(definition, base_dir=tmp_path)
    assert planned == result.files_written
    joined = "\n".join(planned)
    if "products" in modules:
        assert "product" in joined.lower()
    if "categories" in modules:
        assert "categor" in joined.lower()


def test_no_module_files_without_modules(tmp_path: Path) -> None:
    definition = _definition(modules=())
    paths = planned_output_paths(resolve_plan(definition))
    assert not any("product" in p.lower() for p in paths)
    assert not any("categor" in p.lower() for p in paths)
    assert not any("pagination" in p.lower() for p in paths)
    result = generate_project(definition, base_dir=tmp_path)
    assert paths == result.files_written


def test_collision_impossible_for_standard_modules() -> None:
    """Standard mounts must not collide across products+categories."""
    plan = resolve_plan(
        _definition(
            architecture=ArchitectureStyle.MODULAR_MONOLITH,
            modules=("products", "categories"),
        )
    )
    # planned_outputs raises GenerationError on collision
    paths = planned_output_paths(plan)
    assert len(paths) == len(set(paths))


def test_module_id_enum_stable() -> None:
    assert ModuleId.PRODUCTS.value == "products"
    assert ModuleId.CATEGORIES.value == "categories"
