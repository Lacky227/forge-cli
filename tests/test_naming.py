"""Tests for naming and destination resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.core.naming import resolve_destination, to_package_name


def test_to_package_name_hyphenated() -> None:
    assert to_package_name("my-awesome-api") == "my_awesome_api"


def test_resolve_destination_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path separators"):
        resolve_destination("../elsewhere", base_dir=tmp_path)


def test_resolve_destination_under_base(tmp_path: Path) -> None:
    dest = resolve_destination("my-api", base_dir=tmp_path)
    assert dest == (tmp_path / "my-api").resolve()
