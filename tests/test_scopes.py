from pathlib import Path

import pytest

from cc_plugin_to_codex.scopes import Scope, resolve_scope


def test_resolve_global(fake_home: Path) -> None:
    scope = resolve_scope("global")
    assert scope.name == "global"
    assert scope.plugins_dir == fake_home / ".codex" / "plugins"
    assert scope.agents_dir == fake_home / ".codex" / "agents"
    assert scope.registry == fake_home / ".agents" / "plugins" / "marketplace.json"
    assert scope.marketplace_root == fake_home


def test_resolve_project(fake_cwd: Path) -> None:
    scope = resolve_scope("project")
    assert scope.name == "project"
    assert scope.plugins_dir == fake_cwd / ".codex" / "plugins"
    assert scope.agents_dir == fake_cwd / ".codex" / "agents"
    assert scope.registry == fake_cwd / ".agents" / "plugins" / "marketplace.json"
    assert scope.marketplace_root == fake_cwd


def test_resolve_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown scope"):
        resolve_scope("invalid")


def test_ensure_dirs_creates_missing_paths(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    assert scope.plugins_dir.is_dir()
    assert scope.agents_dir.is_dir()
    assert scope.registry.parent.is_dir()


def test_relative_plugin_path_from_marketplace_root(fake_home: Path) -> None:
    scope = resolve_scope("global")
    rel = scope.plugin_path_relative_to_root("cc-ios-dev")
    # marketplace root = fake_home, target = fake_home/.codex/plugins/cc-ios-dev
    assert rel == "./.codex/plugins/cc-ios-dev"
