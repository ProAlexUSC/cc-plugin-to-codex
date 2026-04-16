"""End-to-end test: run plugin-sync against a file:// bare git repo and
validate every generated TOML conforms to the official Codex custom-agent
schema (docs/codex-spec/codex-subagents.md: required fields name,
description, developer_instructions).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cc_plugin_to_codex.cli import app

FIXTURE_DIR = Path(__file__).parent / "fixtures"
BARE_REPO = FIXTURE_DIR / "bare-marketplace.git"

# Required fields per Codex custom-agent file schema
# (docs/codex-spec/codex-subagents.md, "Custom agent file schema" table).
REQUIRED_AGENT_FIELDS = {"name", "description", "developer_instructions"}


def test_e2e_sync_from_bare_git_produces_valid_codex_tomls(fake_home: Path) -> None:
    """Run plugin-sync against a file:// bare git repo and assert every
    generated agent TOML parses and contains all required Codex fields."""
    if not BARE_REPO.is_dir():
        pytest.skip(
            "bare-marketplace.git fixture not built; "
            "run `python tests/fixtures/build_bare_marketplace.py`"
        )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plugin-sync",
            "--source",
            f"file://{BARE_REPO}",
            "--ref",
            "main",
            "--all-plugins",
            "--scope",
            "global",
            "--yes",
            "--non-interactive",
        ],
    )
    assert result.exit_code == 0, f"sync failed:\nstdout: {result.stdout}\nexc: {result.exception}"

    agents_dir = fake_home / ".codex" / "agents"
    assert agents_dir.is_dir(), "no agents dir produced"
    toml_files = list(agents_dir.glob("*.toml"))
    assert toml_files, "no agent TOMLs produced"

    for toml_path in toml_files:
        text = toml_path.read_text(encoding="utf-8")
        try:
            parsed = tomllib.loads(text)
        except tomllib.TOMLDecodeError as e:
            pytest.fail(f"{toml_path.name}: invalid TOML: {e}")

        missing = REQUIRED_AGENT_FIELDS - set(parsed)
        assert not missing, (
            f"{toml_path.name}: missing required Codex fields {missing}; "
            f"see docs/codex-spec/codex-subagents.md"
        )
        assert isinstance(parsed["name"], str) and parsed["name"], (
            f"{toml_path.name}: name must be non-empty string"
        )
        assert isinstance(parsed["description"], str) and parsed["description"], (
            f"{toml_path.name}: description must be non-empty string"
        )
        assert isinstance(parsed["developer_instructions"], str), (
            f"{toml_path.name}: developer_instructions must be string"
        )

    plugins_dir = fake_home / ".codex" / "plugins"
    assert plugins_dir.is_dir()
    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue
        manifest = plugin_dir / ".codex-plugin" / "plugin.json"
        assert manifest.exists(), f"{plugin_dir.name}: missing plugin.json"
        import json

        data = json.loads(manifest.read_text())
        assert "name" in data
        assert "x-cc-bridge" in data
        marker = data["x-cc-bridge"]
        assert marker["sourceKind"] == "git"
        assert marker["source"].startswith("file://")
        assert marker["ref"] == "main"
        assert marker["commit"]
