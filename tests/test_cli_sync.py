"""E2E tests for plugin-sync."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cc_plugin_to_codex.cli import app

runner = CliRunner()
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "src_marketplace"


def test_sync_local_to_global_with_all_plugins(fake_home: Path) -> None:
    result = runner.invoke(
        app,
        [
            "plugin-sync",
            "--source", str(FIXTURE_DIR),
            "--scope", "global",
            "--all-plugins",
            "--non-interactive",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert (fake_home / ".codex" / "plugins" / "cc-demo-a" / ".codex-plugin" / "plugin.json").exists()
    assert (fake_home / ".codex" / "plugins" / "cc-demo-b" / ".codex-plugin" / "plugin.json").exists()
    assert (fake_home / ".codex" / "agents" / "cc_demo_a_helper.toml").exists()
    reg = json.loads((fake_home / ".agents" / "plugins" / "marketplace.json").read_text())
    names = sorted(p["name"] for p in reg["plugins"])
    assert names == ["cc-demo-a", "cc-demo-b"]


def test_sync_specific_plugin(fake_home: Path) -> None:
    result = runner.invoke(
        app,
        [
            "plugin-sync",
            "--source", str(FIXTURE_DIR),
            "--scope", "global",
            "--plugin", "demo-a",
            "--non-interactive",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert (fake_home / ".codex" / "plugins" / "cc-demo-a").exists()
    assert not (fake_home / ".codex" / "plugins" / "cc-demo-b").exists()


def test_sync_unknown_plugin_errors(fake_home: Path) -> None:
    result = runner.invoke(
        app,
        [
            "plugin-sync",
            "--source", str(FIXTURE_DIR),
            "--plugin", "does-not-exist",
            "--non-interactive",
            "--yes",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower() or "not found" in (result.stderr or "").lower()


def test_sync_without_scope_flag_strict_errors(fake_home: Path) -> None:
    """In strict / non-interactive mode, omitting --scope must fail loudly
    rather than picking a default silently — the caller is forced to decide."""
    result = runner.invoke(
        app,
        [
            "plugin-sync",
            "--source", str(FIXTURE_DIR),
            "--plugin", "demo-a",
            "--non-interactive",
            "--yes",
        ],
    )
    assert result.exit_code != 0
    combined = result.stdout + (result.stderr or "")
    assert "--scope" in combined


def test_sync_json_output(fake_home: Path) -> None:
    result = runner.invoke(
        app,
        [
            "plugin-sync",
            "--source", str(FIXTURE_DIR),
            "--scope", "global",
            "--all-plugins",
            "--json",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert len(payload["synced"]) == 2
    for item in payload["synced"]:
        assert "bridgeName" in item
        assert "agents" in item
