"""Tests for reading source marketplace.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cc_plugin_to_codex.marketplace import read_source_marketplace

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "src_marketplace"


def test_read_source_marketplace_lists_plugins() -> None:
    mp = read_source_marketplace(FIXTURE_DIR)
    assert mp.name == "demo-marketplace"
    plugin_names = [p.name for p in mp.plugins]
    assert plugin_names == ["demo-a", "demo-b"]


def test_plugin_info_detects_codex_manifest() -> None:
    mp = read_source_marketplace(FIXTURE_DIR)
    by_name = {p.name: p for p in mp.plugins}
    assert by_name["demo-a"].has_codex_manifest is False
    assert by_name["demo-b"].has_codex_manifest is True


def test_plugin_info_counts_skills_and_agents() -> None:
    mp = read_source_marketplace(FIXTURE_DIR)
    by_name = {p.name: p for p in mp.plugins}
    assert by_name["demo-a"].skill_count == 1
    assert by_name["demo-a"].agent_count == 1
    assert by_name["demo-b"].skill_count == 1
    assert by_name["demo-b"].agent_count == 0


def test_plugin_info_exposes_version_description() -> None:
    mp = read_source_marketplace(FIXTURE_DIR)
    demo_a = next(p for p in mp.plugins if p.name == "demo-a")
    assert demo_a.version == "1.0.0"
    assert demo_a.description == "Demo plugin A"


def test_read_missing_marketplace_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_source_marketplace(tmp_path)


def test_read_source_marketplace_supports_string_source(tmp_path: Path) -> None:
    """Real cc-marketplace uses `"source": "./plugins/foo"` (string), not
    `{"source": {"path": "..."}}`. Both shapes should work.
    """
    mp_dir = tmp_path / ".claude-plugin"
    mp_dir.mkdir()
    (mp_dir / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "str-src",
                "plugins": [{"name": "foo", "source": "./plugins/foo"}],
            }
        )
    )
    plugin_dir = tmp_path / "plugins" / "foo" / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "foo", "version": "1.0.0", "description": "ok"})
    )
    mp = read_source_marketplace(tmp_path)
    assert [p.name for p in mp.plugins] == ["foo"]
    assert mp.plugins[0].description == "ok"
