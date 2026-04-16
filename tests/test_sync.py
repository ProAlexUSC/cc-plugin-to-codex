"""Tests for sync orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cc_plugin_to_codex.marketplace import read_source_marketplace
from cc_plugin_to_codex.scopes import resolve_scope
from cc_plugin_to_codex.sync import (
    SyncConflictError,
    sync_agents,
    sync_one,
    sync_plugin,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "src_marketplace"


def _get_plugin_info(name: str):
    mp = read_source_marketplace(FIXTURE_DIR)
    return next(p for p in mp.plugins if p.name == name), mp


def test_sync_plugin_translates_claude_manifest(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    info, mp = _get_plugin_info("demo-a")
    sync_plugin(
        info=info,
        marketplace_name=mp.name,
        source="/fake/src",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )
    bridge_dir = scope.plugins_dir / "cc-demo-a"
    manifest_path = bridge_dir / ".codex-plugin" / "plugin.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["name"] == "cc-demo-a"
    assert "hooks" not in manifest  # CC-only stripped
    assert "agents" not in manifest
    assert manifest["x-cc-bridge"]["sourcePlugin"] == "demo-a"
    assert manifest["x-cc-bridge"]["marketplace"] == "demo-marketplace"
    assert (bridge_dir / "skills" / "greet" / "SKILL.md").exists()


def test_sync_plugin_copies_existing_codex_manifest(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    info, mp = _get_plugin_info("demo-b")
    sync_plugin(
        info=info,
        marketplace_name=mp.name,
        source="/fake/src",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )
    manifest = json.loads(
        (scope.plugins_dir / "cc-demo-b" / ".codex-plugin" / "plugin.json").read_text()
    )
    # demo-b's codex manifest had description "Demo plugin B (codex variant)"
    assert manifest["description"] == "Demo plugin B (codex variant)"


def test_sync_plugin_refuses_overwrite_of_non_bridge(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    bridge_dir = scope.plugins_dir / "cc-demo-a"
    (bridge_dir / ".codex-plugin").mkdir(parents=True)
    (bridge_dir / ".codex-plugin" / "plugin.json").write_text('{"name":"cc-demo-a"}')  # no marker

    info, mp = _get_plugin_info("demo-a")
    with pytest.raises(SyncConflictError, match="non-bridge"):
        sync_plugin(
            info=info,
            marketplace_name=mp.name,
            source="/fake/src",
            source_kind="local",
            ref=None,
            commit="local",
            scope=scope,
        )


def test_sync_plugin_refuses_different_source(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    # first sync from source-A
    info, mp = _get_plugin_info("demo-a")
    sync_plugin(
        info=info,
        marketplace_name=mp.name,
        source="source-A",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )
    # second sync from source-B should fail
    with pytest.raises(SyncConflictError, match="different source"):
        sync_plugin(
            info=info,
            marketplace_name=mp.name,
            source="source-B",
            source_kind="local",
            ref=None,
            commit="local",
            scope=scope,
        )


def test_sync_plugin_allows_resync_from_same_source(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    info, mp = _get_plugin_info("demo-a")
    for _ in range(2):
        sync_plugin(
            info=info,
            marketplace_name=mp.name,
            source="same",
            source_kind="local",
            ref=None,
            commit="local",
            scope=scope,
        )
    # still only one bridge dir
    assert (scope.plugins_dir / "cc-demo-a" / ".codex-plugin" / "plugin.json").exists()


def test_sync_plugin_force_overwrites_non_bridge(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    bridge_dir = scope.plugins_dir / "cc-demo-a"
    (bridge_dir / ".codex-plugin").mkdir(parents=True)
    (bridge_dir / ".codex-plugin" / "plugin.json").write_text('{"name":"cc-demo-a"}')

    info, mp = _get_plugin_info("demo-a")
    sync_plugin(
        info=info,
        marketplace_name=mp.name,
        source="s",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
        force=True,
    )
    manifest = json.loads((bridge_dir / ".codex-plugin" / "plugin.json").read_text())
    assert "x-cc-bridge" in manifest


def test_sync_agents_converts_md_to_toml(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    info, mp = _get_plugin_info("demo-a")
    agent_names = sync_agents(
        info=info, bridge_name="cc-demo-a", scope=scope, synced_at="2026-04-14T10:30:00Z"
    )
    assert agent_names == ["cc_demo_a_helper"]
    toml_path = scope.agents_dir / "cc_demo_a_helper.toml"
    assert toml_path.exists()
    content = toml_path.read_text(encoding="utf-8")
    assert content.startswith("# x-cc-bridge: ")
    assert 'name = "cc_demo_a_helper"' in content


def test_sync_agents_refuses_non_bridge_toml(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    # user already has a non-bridge TOML with the same target name
    (scope.agents_dir / "cc_demo_a_helper.toml").write_text(
        'name = "cc_demo_a_helper"\ndescription = "user"\ndeveloper_instructions = "x"\n'
    )
    info, mp = _get_plugin_info("demo-a")
    with pytest.raises(SyncConflictError, match="non-bridge"):
        sync_agents(info=info, bridge_name="cc-demo-a", scope=scope, synced_at="x")


def test_sync_one_full_orchestrate_updates_manifest_agents_field(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    info, mp = _get_plugin_info("demo-a")
    result = sync_one(
        info=info,
        marketplace_name=mp.name,
        source="s",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )
    assert result.agents == ["cc_demo_a_helper"]
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["x-cc-bridge"]["agents"] == ["cc_demo_a_helper"]


def test_sync_one_registry_is_upserted(fake_home: Path) -> None:
    scope = resolve_scope("global")
    scope.ensure_dirs()
    info, mp = _get_plugin_info("demo-a")
    sync_one(
        info=info,
        marketplace_name=mp.name,
        source="s",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )
    reg = json.loads(scope.registry.read_text())
    names = [p["name"] for p in reg["plugins"]]
    assert "cc-demo-a" in names


def test_sync_plugin_copies_arbitrary_top_level_dirs(fake_home: Path, tmp_path: Path) -> None:
    """Any non-CC-only top-level entry (scripts/, CLAUDE.md, luna-rules/, ...)
    must survive the copy so skill helpers stay reachable."""
    from cc_plugin_to_codex.marketplace import read_source_marketplace

    src = tmp_path / "src_mk"
    (src / ".claude-plugin").mkdir(parents=True)
    (src / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "mk",
                "plugins": [
                    {"name": "demo", "source": {"source": "local", "path": "./plugins/demo"}}
                ],
            }
        )
    )
    plugin_dir = src / "plugins" / "demo"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": "1.0.0", "description": "t"})
    )
    (plugin_dir / "skills" / "greet").mkdir(parents=True)
    (plugin_dir / "skills" / "greet" / "SKILL.md").write_text("---\nname: greet\n---\nbody\n")
    # Skill-adjacent helper files that a naive whitelist would drop
    (plugin_dir / "scripts" / "python").mkdir(parents=True)
    (plugin_dir / "scripts" / "python" / "helper.py").write_text("# shared helper\n")
    (plugin_dir / "luna-rules").mkdir()
    (plugin_dir / "luna-rules" / "rule.md").write_text("rule\n")
    (plugin_dir / "CLAUDE.md").write_text("plugin instructions\n")
    # CC-only entries that MUST be dropped
    (plugin_dir / "hooks").mkdir()
    (plugin_dir / "hooks" / "start.sh").write_text("echo hi\n")
    # Noise that MUST be dropped
    (plugin_dir / "__pycache__").mkdir()
    (plugin_dir / "__pycache__" / "x.pyc").write_text("")

    mp = read_source_marketplace(src)
    info = mp.plugins[0]
    scope = resolve_scope("global")
    scope.ensure_dirs()
    sync_plugin(
        info=info,
        marketplace_name=mp.name,
        source="s",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )

    bridge = scope.plugins_dir / "cc-demo"
    assert (bridge / "skills" / "greet" / "SKILL.md").exists()
    assert (bridge / "scripts" / "python" / "helper.py").exists()
    assert (bridge / "luna-rules" / "rule.md").exists()
    assert (bridge / "CLAUDE.md").exists()
    assert not (bridge / "hooks").exists()
    assert not (bridge / "__pycache__").exists()


def test_sync_one_removes_stale_agents_on_resync(fake_home: Path, tmp_path: Path) -> None:
    """When an upstream drops an agent, the next sync must delete its TOML."""
    from cc_plugin_to_codex.marketplace import read_source_marketplace

    # Build a minimal source with two agents: a, b
    src = tmp_path / "src_mk"
    (src / ".claude-plugin").mkdir(parents=True)
    (src / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "test-mk",
                "plugins": [
                    {"name": "demo", "source": {"source": "local", "path": "./plugins/demo"}}
                ],
            }
        )
    )
    plugin_dir = src / "plugins" / "demo"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": "1.0.0", "description": "t"})
    )
    (plugin_dir / "agents").mkdir()
    (plugin_dir / "agents" / "keeper.md").write_text(
        "---\nname: keeper\ndescription: A\n---\n\nbody\n"
    )
    (plugin_dir / "agents" / "doomed.md").write_text(
        "---\nname: doomed\ndescription: B\n---\n\nbody\n"
    )

    scope = resolve_scope("global")
    scope.ensure_dirs()

    mp1 = read_source_marketplace(src)
    info1 = mp1.plugins[0]
    sync_one(
        info=info1,
        marketplace_name=mp1.name,
        source="x",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )
    assert (scope.agents_dir / "cc_demo_keeper.toml").exists()
    assert (scope.agents_dir / "cc_demo_doomed.toml").exists()

    # Upstream removes 'doomed'
    (plugin_dir / "agents" / "doomed.md").unlink()
    mp2 = read_source_marketplace(src)
    info2 = mp2.plugins[0]
    sync_one(
        info=info2,
        marketplace_name=mp2.name,
        source="x",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )
    assert (scope.agents_dir / "cc_demo_keeper.toml").exists()
    assert not (scope.agents_dir / "cc_demo_doomed.toml").exists(), (
        "stale bridge agent should be removed on re-sync"
    )


def test_sync_one_preserves_user_authored_toml_during_stale_cleanup(
    fake_home: Path,
) -> None:
    """Stale cleanup only deletes agents whose TOML carries a bridge marker."""
    scope = resolve_scope("global")
    scope.ensure_dirs()
    info, mp = _get_plugin_info("demo-a")

    # First sync creates cc_demo_a_helper.toml
    sync_one(
        info=info,
        marketplace_name=mp.name,
        source="s",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )

    # User writes their own TOML with a name that's NOT in the new marker
    user_toml = scope.agents_dir / "cc_demo_a_orphan.toml"
    user_toml.write_text(
        'name = "cc_demo_a_orphan"\ndescription = "user-owned"\ndeveloper_instructions = "x"\n'
    )

    # Manually tamper with the manifest to pretend "orphan" was bridged last time
    manifest_path = scope.plugins_dir / "cc-demo-a" / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["x-cc-bridge"]["agents"].append("cc_demo_a_orphan")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    # Re-sync: even though marker says orphan is bridged, TOML has no bridge marker → keep
    sync_one(
        info=info,
        marketplace_name=mp.name,
        source="s",
        source_kind="local",
        ref=None,
        commit="local",
        scope=scope,
    )
    assert user_toml.exists(), "user-authored TOML must never be deleted by stale cleanup"
