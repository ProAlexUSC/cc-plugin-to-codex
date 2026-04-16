"""E2E tests for plugin-browse."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cc_plugin_to_codex.cli import app

runner = CliRunner()
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "src_marketplace"


def test_browse_local_source_text() -> None:
    result = runner.invoke(
        app, ["plugin-browse", "--source", str(FIXTURE_DIR), "--non-interactive"]
    )
    assert result.exit_code == 0, result.stdout
    assert "demo-a" in result.stdout
    assert "demo-b" in result.stdout
    assert "demo-marketplace" in result.stdout


def test_browse_local_source_json() -> None:
    result = runner.invoke(app, ["plugin-browse", "--source", str(FIXTURE_DIR), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["marketplace"]["name"] == "demo-marketplace"
    names = [p["name"] for p in payload["plugins"]]
    assert names == ["demo-a", "demo-b"]


def test_browse_missing_source_strict_errors() -> None:
    result = runner.invoke(app, ["plugin-browse", "--non-interactive"])
    assert result.exit_code != 0
    assert "source" in result.stdout.lower() or "source" in (result.stderr or "").lower()


def test_cli_version_flag_prints_version() -> None:
    """`cc2codex --version` prints the installed package version and exits 0."""
    from cc_plugin_to_codex import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"cc2codex {__version__}"
