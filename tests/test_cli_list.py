"""E2E tests for plugin-list."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cc_plugin_to_codex.cli import app

runner = CliRunner()
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "src_marketplace"


def _prepopulate(fake_home: Path) -> None:
    runner.invoke(
        app,
        [
            "plugin-sync", "--source", str(FIXTURE_DIR), "--scope", "global",
            "--all-plugins", "--non-interactive", "--yes",
        ],
    )


def test_list_global_after_sync_text(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(app, ["plugin-list", "--scope", "global"])
    assert result.exit_code == 0, result.stdout
    assert "cc-demo-a" in result.stdout
    assert "cc-demo-b" in result.stdout
    assert str(fake_home / ".codex" / "plugins") in result.stdout


def test_list_json(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(app, ["plugin-list", "--scope", "global", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    global_scope = payload["scopes"]["global"]
    names = [b["name"] for b in global_scope["bridges"]]
    assert sorted(names) == ["cc-demo-a", "cc-demo-b"]
    assert global_scope["pluginsDir"].endswith(".codex/plugins")


def test_list_all_scopes_includes_project_even_if_empty(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(app, ["plugin-list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "global" in payload["scopes"]
    assert "project" in payload["scopes"]
    assert payload["scopes"]["project"]["bridges"] == []
