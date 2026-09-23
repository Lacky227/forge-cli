"""Forge — interactive architecture and project generator CLI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("forge-scaffolder")
except PackageNotFoundError:  # pragma: no cover - editable/dev fallback
    __version__ = "0.4.0"
