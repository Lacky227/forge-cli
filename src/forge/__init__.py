"""Forge — interactive architecture and project generator CLI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("forge-cli")
except PackageNotFoundError:  # pragma: no cover - editable/dev fallback
    __version__ = "0.1.0"
