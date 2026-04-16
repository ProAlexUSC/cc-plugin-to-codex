"""Console output helpers. Supports text and JSON modes."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console

_console = Console()
_err_console = Console(stderr=True)

_json_mode = False


def set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def info(msg: str) -> None:
    if not _json_mode:
        _console.print(msg, soft_wrap=True)


def success(msg: str) -> None:
    if not _json_mode:
        _console.print(f"[green]✓[/green] {msg}", soft_wrap=True)


def warn(msg: str) -> None:
    if not _json_mode:
        _console.print(f"[yellow]![/yellow] {msg}", soft_wrap=True)


def error(msg: str) -> None:
    _err_console.print(f"[red]Error:[/red] {msg}", soft_wrap=True)


def emit_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
