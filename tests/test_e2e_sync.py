"""End-to-end test: run plugin-sync against a file:// bare git repo and
validate every observable effect — Codex custom-agent schema compliance
(docs/codex-spec/codex-subagents.md), skill-tree preservation including
nested references/assets, CC-only field stripping, agent body roundtrip,
agent name derivation, and Codex marketplace registry.
"""

from __future__ import annotations

import json
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


def _run_sync(fake_home: Path) -> None:
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


@pytest.fixture
def synced_home(fake_home: Path) -> Path:
    if not BARE_REPO.is_dir():
        pytest.skip(
            "bare-marketplace.git fixture not built; "
            "run `python tests/fixtures/build_bare_marketplace.py`"
        )
    _run_sync(fake_home)
    return fake_home


def test_e2e_generated_tomls_match_codex_schema(synced_home: Path) -> None:
    """Every generated agent TOML parses and carries all required Codex fields."""
    agents_dir = synced_home / ".codex" / "agents"
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
        assert isinstance(parsed["name"], str) and parsed["name"]
        assert isinstance(parsed["description"], str) and parsed["description"]
        assert isinstance(parsed["developer_instructions"], str)


def test_e2e_bridge_manifest_has_marker_and_strips_cc_only_fields(synced_home: Path) -> None:
    """Every bridge plugin.json carries a full x-cc-bridge marker and no CC-only fields."""
    plugins_dir = synced_home / ".codex" / "plugins"
    assert plugins_dir.is_dir()

    bridge_dirs = [d for d in plugins_dir.iterdir() if d.is_dir()]
    assert {d.name for d in bridge_dirs} == {"cc-demo-a", "cc-demo-b"}, (
        "expected exactly cc-demo-a and cc-demo-b bridges"
    )

    for plugin_dir in bridge_dirs:
        manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
        assert manifest_path.exists(), f"{plugin_dir.name}: missing plugin.json"
        data = json.loads(manifest_path.read_text())

        assert data["name"] == plugin_dir.name
        # CC-only fields must be stripped from the bridged manifest
        assert "hooks" not in data, f"{plugin_dir.name}: hooks should be stripped"
        assert "commands" not in data
        assert "agents" not in data

        marker = data["x-cc-bridge"]
        assert marker["sourceKind"] == "git"
        assert marker["source"].startswith("file://")
        assert marker["ref"] == "main"
        assert marker["commit"], "commit SHA must be recorded in marker"
        assert marker["marketplace"] == "demo-marketplace"


def test_e2e_skill_tree_is_copied_with_references(synced_home: Path) -> None:
    """Skill files plus nested references/ and assets/ must all land in the bridge,
    verbatim — a skill author's relative links (references/tone.md, assets/banner.txt)
    would otherwise break on the Codex side."""
    cc_demo_a = synced_home / ".codex" / "plugins" / "cc-demo-a"
    cc_demo_b = synced_home / ".codex" / "plugins" / "cc-demo-b"

    # demo-a: SKILL.md + references/ + assets/
    assert (cc_demo_a / "skills" / "greet" / "SKILL.md").exists()
    skill_text = (cc_demo_a / "skills" / "greet" / "SKILL.md").read_text(encoding="utf-8")
    assert "references/tone.md" in skill_text, "SKILL.md body must be preserved"

    tone = cc_demo_a / "skills" / "greet" / "references" / "tone.md"
    assert tone.exists(), "nested references/tone.md must be copied"
    assert "Keep greetings warm" in tone.read_text(encoding="utf-8")

    banner = cc_demo_a / "skills" / "greet" / "assets" / "banner.txt"
    assert banner.exists(), "nested assets/banner.txt must be copied"
    assert "WELCOME" in banner.read_text(encoding="utf-8")

    # demo-b: skill with reference
    assert (cc_demo_b / "skills" / "farewell" / "SKILL.md").exists()
    politeness = cc_demo_b / "skills" / "farewell" / "references" / "politeness.md"
    assert politeness.exists(), "demo-b nested references/politeness.md must be copied"


def test_e2e_agent_body_and_name_are_correct(synced_home: Path) -> None:
    """helper.md's body must land verbatim in developer_instructions, and the
    snake_cased bridge name must be cc_<plugin>_<agent>."""
    toml_path = synced_home / ".codex" / "agents" / "cc_demo_a_helper.toml"
    assert toml_path.exists(), (
        "expected cc_demo_a_helper.toml — agent name should be cc_<snake_plugin>_<snake_agent>"
    )

    parsed = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    assert parsed["name"] == "cc_demo_a_helper"
    # helper.md body is literally "You are helpful.\n"
    assert parsed["developer_instructions"].strip() == "You are helpful."
    # Description comes from frontmatter
    assert parsed["description"] == "Helpful agent"


def test_e2e_codex_marketplace_registry_is_written(synced_home: Path) -> None:
    """~/.agents/plugins/marketplace.json is Codex's pointer at the bridge
    list — without it, Codex won't see any of the synced plugins."""
    registry = synced_home / ".agents" / "plugins" / "marketplace.json"
    assert registry.exists(), "Codex marketplace.json registry must be written"
    data = json.loads(registry.read_text(encoding="utf-8"))
    plugin_names = {p["name"] for p in data.get("plugins", [])}
    assert {"cc-demo-a", "cc-demo-b"}.issubset(plugin_names)
