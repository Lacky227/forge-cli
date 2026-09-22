"""Deterministic Typer CliRunner helpers for CI and colored terminals.

Rich may style each hyphen of ``--option`` separately when color is forced
(e.g. ``FORCE_COLOR=1`` on GitHub Actions), so the contiguous substring
``"--version"`` is absent from the raw capture even though help is correct.

These helpers disable color for invokes and strip ANSI when asserting
semantic help text.
"""

from __future__ import annotations

import re
from typing import Any

from typer.testing import CliRunner

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_COLORLESS_ENV = {
    "NO_COLOR": "1",
    "FORCE_COLOR": "0",
    "CLICOLOR_FORCE": "0",
    "TERM": "dumb",
}


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR sequences from captured terminal output."""
    return _ANSI_RE.sub("", text)


def invoke_cli(app: Any, args: list[str], **kwargs: Any) -> Any:
    """Invoke the Typer app with a colorless, CI-safe environment."""
    runner: CliRunner = kwargs.pop("runner", None) or CliRunner()
    env = {**_COLORLESS_ENV, **(kwargs.pop("env", None) or {})}
    return runner.invoke(app, args, env=env, color=False, **kwargs)


def plain_output(result: Any) -> str:
    """Return CliRunner output with ANSI escapes removed."""
    return strip_ansi(result.output)
