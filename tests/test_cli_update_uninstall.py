"""E2E tests for plugin-update and plugin-uninstall."""

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
            "plugin-sync",
            "--source",
            str(FIXTURE_DIR),
            "--scope",
            "global",
            "--all-plugins",
            "--non-interactive",
            "--yes",
        ],
    )


def test_uninstall_no_args_strict_hints_at_syntax(fake_home: Path) -> None:
    """With bridges installed but no name / no --all in strict mode, the error
    must tell the caller what to pass instead of silently saying 'none found'."""
    _prepopulate(fake_home)
    result = runner.invoke(app, ["plugin-uninstall", "--non-interactive"])
    assert result.exit_code != 0
    combined = result.stdout + (result.stderr or "")
    assert "--all" in combined or "must specify" in combined
    # names of installed bridges surface so the user knows what's available
    assert "cc-demo-a" in combined or "cc-demo-b" in combined


def test_update_no_args_strict_hints_at_syntax(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(app, ["plugin-update", "--non-interactive"])
    assert result.exit_code != 0
    combined = result.stdout + (result.stderr or "")
    assert "--all" in combined or "must specify" in combined


def test_uninstall_removes_bridge_agents_and_registry(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(app, ["plugin-uninstall", "cc-demo-a", "--non-interactive", "--yes"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert not (fake_home / ".codex" / "plugins" / "cc-demo-a").exists()
    assert not (fake_home / ".codex" / "agents" / "cc_demo_a_helper.toml").exists()
    reg = json.loads((fake_home / ".agents" / "plugins" / "marketplace.json").read_text())
    assert "cc-demo-a" not in [p["name"] for p in reg["plugins"]]
    # demo-b still present
    assert (fake_home / ".codex" / "plugins" / "cc-demo-b").exists()


def test_uninstall_all(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(app, ["plugin-uninstall", "--all", "--non-interactive", "--yes"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert not (fake_home / ".codex" / "plugins" / "cc-demo-a").exists()
    assert not (fake_home / ".codex" / "plugins" / "cc-demo-b").exists()


def test_uninstall_unknown_bridge_errors(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(
        app, ["plugin-uninstall", "cc-does-not-exist", "--non-interactive", "--yes"]
    )
    assert result.exit_code != 0
    combined = result.stdout + (result.stderr or "")
    assert "cc-does-not-exist" in combined
    assert "not found" in combined


def test_uninstall_no_bridges_installed_errors(fake_home: Path) -> None:
    # no _prepopulate => no bridges installed
    result = runner.invoke(app, ["plugin-uninstall", "--all", "--non-interactive", "--yes"])
    assert result.exit_code != 0
    combined = result.stdout + (result.stderr or "")
    assert "no bridge plugins installed" in combined


def test_update_unknown_bridge_errors(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(app, ["plugin-update", "cc-nope", "--non-interactive", "--yes"])
    assert result.exit_code != 0
    combined = result.stdout + (result.stderr or "")
    assert "cc-nope" in combined
    assert "not found" in combined


def test_update_resyncs_from_recorded_source(fake_home: Path) -> None:
    _prepopulate(fake_home)
    result = runner.invoke(
        app,
        ["plugin-update", "cc-demo-a", "--non-interactive", "--yes", "--force"],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    # bridge still exists
    manifest = json.loads(
        (
            fake_home / ".codex" / "plugins" / "cc-demo-a" / ".codex-plugin" / "plugin.json"
        ).read_text()
    )
    assert manifest["x-cc-bridge"]["sourcePlugin"] == "demo-a"
