"""Tests for target marketplace.json registry upsert/remove."""
from __future__ import annotations

import json
from pathlib import Path

from cc_plugin_to_codex.registry import (
    load_or_init_registry,
    upsert_plugin_entry,
    remove_plugin_entry,
    save_registry,
)


def test_load_or_init_creates_default(tmp_path: Path) -> None:
    registry_path = tmp_path / "marketplace.json"
    reg = load_or_init_registry(registry_path)
    assert reg["name"] == "cc-bridged-plugins"
    assert reg["interface"]["displayName"] == "CC Bridged Plugins"
    assert reg["plugins"] == []


def test_load_or_init_preserves_existing(tmp_path: Path) -> None:
    registry_path = tmp_path / "marketplace.json"
    registry_path.write_text(
        json.dumps({"name": "user-market", "plugins": [{"name": "foo"}]}),
        encoding="utf-8",
    )
    reg = load_or_init_registry(registry_path)
    assert reg["name"] == "user-market"
    assert len(reg["plugins"]) == 1


def test_upsert_adds_new_entry() -> None:
    reg = {"name": "x", "plugins": []}
    upsert_plugin_entry(reg, name="cc-ios-dev", relative_path="./.codex/plugins/cc-ios-dev")
    assert len(reg["plugins"]) == 1
    entry = reg["plugins"][0]
    assert entry["name"] == "cc-ios-dev"
    assert entry["source"] == {"source": "local", "path": "./.codex/plugins/cc-ios-dev"}
    assert entry["policy"]["installation"] == "INSTALLED_BY_DEFAULT"
    assert entry["policy"]["authentication"] == "ON_USE"
    assert entry["category"] == "Productivity"


def test_upsert_replaces_existing_entry() -> None:
    reg = {
        "name": "x",
        "plugins": [{"name": "cc-ios-dev", "source": {"path": "old"}, "policy": {}, "category": "X"}],
    }
    upsert_plugin_entry(reg, name="cc-ios-dev", relative_path="./new")
    assert len(reg["plugins"]) == 1
    assert reg["plugins"][0]["source"]["path"] == "./new"


def test_upsert_preserves_user_entries() -> None:
    reg = {
        "name": "x",
        "plugins": [
            {"name": "user-plugin", "source": {"path": "./user"}, "policy": {}, "category": "X"},
        ],
    }
    upsert_plugin_entry(reg, name="cc-ios-dev", relative_path="./cc")
    names = [p["name"] for p in reg["plugins"]]
    assert "user-plugin" in names
    assert "cc-ios-dev" in names


def test_remove_plugin_entry() -> None:
    reg = {
        "name": "x",
        "plugins": [
            {"name": "cc-ios-dev", "source": {}, "policy": {}, "category": "X"},
            {"name": "cc-base", "source": {}, "policy": {}, "category": "X"},
        ],
    }
    remove_plugin_entry(reg, name="cc-ios-dev")
    names = [p["name"] for p in reg["plugins"]]
    assert names == ["cc-base"]


def test_save_registry_pretty_prints(tmp_path: Path) -> None:
    registry_path = tmp_path / "marketplace.json"
    reg = {"name": "x", "plugins": []}
    save_registry(registry_path, reg)
    content = registry_path.read_text(encoding="utf-8")
    assert '"name": "x"' in content  # pretty-printed
    # round-trip
    assert json.loads(content) == reg
