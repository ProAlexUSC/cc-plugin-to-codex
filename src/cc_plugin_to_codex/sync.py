"""Sync orchestration: copy plugin body + convert subagents."""
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from cc_plugin_to_codex.agent_convert import ConversionResult, convert_agent
from cc_plugin_to_codex.bridge import (
    BridgeMarker,
    build_marker,
    extract_agent_marker,
    extract_marker,
    is_bridge_manifest,
)
from cc_plugin_to_codex.marketplace import PluginInfo
from cc_plugin_to_codex.registry import (
    load_or_init_registry,
    remove_plugin_entry,
    save_registry,
    upsert_plugin_entry,
)
from cc_plugin_to_codex.scopes import Scope

SourceKind = Literal["git", "local"]

# CC-only fields always stripped from the bridge manifest
CC_ONLY_KEYS = {"hooks", "commands", "agents"}

# Top-level entries that are CC-specific and must NOT land in a Codex bridge.
# .claude-plugin/ is ignored because we generate our own .codex-plugin/; agents/
# are transformed separately into TOML under scope.agents_dir; hooks/ and
# commands/ are Claude Code-only mechanisms.
_CC_ONLY_DIR_NAMES = {".claude-plugin", ".codex-plugin", "hooks", "commands", "agents"}

# Noise that gets picked up during blacklist copy if not filtered out.
_COPY_IGNORE_PATTERNS = (
    "__pycache__", "*.pyc", ".DS_Store", ".git", ".pytest_cache", ".venv", "node_modules",
)


class SyncConflictError(RuntimeError):
    pass


@dataclass
class SyncResult:
    bridge_name: str
    bridge_dir: Path
    manifest_path: Path
    agents: list[str] = field(default_factory=list)


def sync_plugin(
    *,
    info: PluginInfo,
    marketplace_name: str,
    source: str,
    source_kind: SourceKind,
    ref: str | None,
    commit: str,
    scope: Scope,
    force: bool = False,
    agents: list[str] | None = None,
) -> SyncResult:
    """Stage a bridge plugin dir in a sibling temp dir and atomically swap it in.

    `agents` is embedded in the manifest's x-cc-bridge marker at write time; pass
    the final list from sync_one to avoid a second manifest write. Defaults to [].
    """
    bridge_name = f"cc-{info.name}"
    bridge_dir = scope.plugins_dir / bridge_name
    manifest_path = bridge_dir / ".codex-plugin" / "plugin.json"

    _check_conflict(manifest_path, source=source, force=force)

    scope.plugins_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = scope.plugins_dir / f".{bridge_name}.stage-{uuid.uuid4().hex[:8]}"
    try:
        stage_dir.mkdir(parents=True)

        _copy_plugin_body(info.plugin_dir, stage_dir)

        # build manifest with agents pre-populated (no second write needed)
        manifest = _load_codex_or_claude_manifest(info.plugin_dir)
        for k in CC_ONLY_KEYS:
            manifest.pop(k, None)
        manifest["name"] = bridge_name
        manifest["x-cc-bridge"] = build_marker(
            source_plugin=info.name,
            source=source,
            source_kind=source_kind,
            ref=ref,
            commit=commit,
            marketplace=marketplace_name,
            agents=list(agents or []),
        )

        stage_manifest = stage_dir / ".codex-plugin" / "plugin.json"
        stage_manifest.parent.mkdir(parents=True, exist_ok=True)
        with stage_manifest.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")

        _atomic_replace(bridge_dir, stage_dir)
    except Exception:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    return SyncResult(
        bridge_name=bridge_name,
        bridge_dir=bridge_dir,
        manifest_path=manifest_path,
        agents=list(agents or []),
    )


def _copy_plugin_body(src: Path, dst: Path) -> None:
    """Copy plugin contents except CC-only mechanisms and VCS/build noise.

    Allows skills/, scripts/, assets/, luna-rules/, CHANGELOG.md, and any other
    skill-adjacent file without maintaining an allowlist.
    """
    ignore = shutil.ignore_patterns(*_COPY_IGNORE_PATTERNS)
    for item in src.iterdir():
        if item.name in _CC_ONLY_DIR_NAMES:
            continue
        if item.name in _COPY_IGNORE_PATTERNS:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=ignore)
        else:
            shutil.copy2(item, target)


def _atomic_replace(target: Path, staged: Path) -> None:
    """Swap `staged` into `target`. POSIX rename is atomic on same filesystem."""
    if target.exists():
        old_dir = target.parent / f".{target.name}.old-{uuid.uuid4().hex[:8]}"
        target.rename(old_dir)
        try:
            staged.rename(target)
        except Exception:
            try:
                old_dir.rename(target)  # rollback
            except Exception:
                pass
            raise
        shutil.rmtree(old_dir, ignore_errors=True)
    else:
        staged.rename(target)


def _read_manifest_with_marker(
    manifest_path: Path,
) -> tuple[dict | None, BridgeMarker | None]:
    """Read a bridge plugin.json. Returns (manifest, marker), or (None, None) if unreadable."""
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None, None
    return manifest, extract_marker(manifest)


def _check_conflict(manifest_path: Path, *, source: str, force: bool) -> None:
    if not manifest_path.exists():
        return
    manifest, marker = _read_manifest_with_marker(manifest_path)
    if manifest is None:
        if force:
            return
        raise SyncConflictError(f"{manifest_path} exists but is unreadable (use --force to overwrite)")
    if not is_bridge_manifest(manifest):
        if force:
            return
        raise SyncConflictError(
            f"{manifest_path.parent} exists and is non-bridge (user-authored). "
            f"Use --force to overwrite."
        )
    if marker is None:
        return
    if marker["source"] != source and not force:
        raise SyncConflictError(
            f"{manifest_path.parent} already synced from different source "
            f"({marker['source']!r} vs {source!r}). "
            f"Run 'cc2codex plugin-uninstall {marker.get('sourcePlugin','?')}' first, "
            f"or pass --force."
        )


def _load_codex_or_claude_manifest(plugin_dir: Path) -> dict:
    codex = plugin_dir / ".codex-plugin" / "plugin.json"
    claude = plugin_dir / ".claude-plugin" / "plugin.json"
    if codex.exists():
        with codex.open("r", encoding="utf-8") as f:
            return json.load(f)
    if claude.exists():
        with claude.open("r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError(f"neither .codex-plugin/ nor .claude-plugin/ plugin.json under {plugin_dir}")


def sync_agents(
    *,
    info: PluginInfo,
    bridge_name: str,
    scope: Scope,
    synced_at: str,
    force: bool = False,
) -> list[str]:
    """Convert every agents/*.md under info.plugin_dir to a Codex TOML file.

    Returns the list of written agent names (snake_case). Retained as a standalone
    helper; sync_one uses its own inline pipeline for atomicity.
    """
    conversions = _convert_all_agents(info, bridge_name=bridge_name, synced_at=synced_at)
    _check_agent_conflicts(scope, conversions, force=force)
    scope.agents_dir.mkdir(parents=True, exist_ok=True)
    for conv in conversions:
        (scope.agents_dir / f"{conv.agent_name}.toml").write_text(conv.toml, encoding="utf-8")
    return [c.agent_name for c in conversions]


def sync_one(
    *,
    info: PluginInfo,
    marketplace_name: str,
    source: str,
    source_kind: SourceKind,
    ref: str | None,
    commit: str,
    scope: Scope,
    force: bool = False,
) -> SyncResult:
    """Full sync: stage plugin dir, write agent TOMLs, cleanup stale, update registry."""
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bridge_name = f"cc-{info.name}"

    # Snapshot prior agent list for stale cleanup
    bridge_manifest = scope.plugins_dir / bridge_name / ".codex-plugin" / "plugin.json"
    old_agents = _read_bridge_agents(bridge_manifest)

    # Pre-convert all agents so any conversion error fails fast, before we touch disk
    conversions = _convert_all_agents(info, bridge_name=bridge_name, synced_at=synced_at)
    new_agent_names = [c.agent_name for c in conversions]

    # Refuse overwriting user-authored TOMLs before staging
    _check_agent_conflicts(scope, conversions, force=force)

    # Atomic plugin dir swap with agents list baked into the manifest
    result = sync_plugin(
        info=info,
        marketplace_name=marketplace_name,
        source=source,
        source_kind=source_kind,
        ref=ref,
        commit=commit,
        scope=scope,
        force=force,
        agents=new_agent_names,
    )

    # Write fresh agent TOMLs
    scope.agents_dir.mkdir(parents=True, exist_ok=True)
    for conv in conversions:
        (scope.agents_dir / f"{conv.agent_name}.toml").write_text(conv.toml, encoding="utf-8")

    # Remove agents that were in the previous marker but are no longer present
    for name in set(old_agents) - set(new_agent_names):
        toml_path = scope.agents_dir / f"{name}.toml"
        if toml_path.exists() and extract_agent_marker(toml_path) is not None:
            toml_path.unlink()

    # Upsert registry entry
    registry = load_or_init_registry(scope.registry)
    upsert_plugin_entry(
        registry,
        name=result.bridge_name,
        relative_path=scope.plugin_path_relative_to_root(result.bridge_name),
    )
    save_registry(scope.registry, registry)

    return result


def _read_bridge_agents(manifest_path: Path) -> list[str]:
    """Return the agents list recorded in an existing bridge manifest, or []."""
    _, marker = _read_manifest_with_marker(manifest_path)
    if marker is None:
        return []
    return list(marker.get("agents", []))


def _convert_all_agents(
    info: PluginInfo,
    *,
    bridge_name: str,
    synced_at: str,
) -> list[ConversionResult]:
    agents_src = info.plugin_dir / "agents"
    if not agents_src.is_dir():
        return []
    return [
        convert_agent(
            md,
            bridge_plugin=bridge_name,
            source_plugin=info.name,
            synced_at=synced_at,
        )
        for md in sorted(agents_src.glob("*.md"))
    ]


def _check_agent_conflicts(
    scope: Scope,
    conversions: list[ConversionResult],
    *,
    force: bool,
) -> None:
    for conv in conversions:
        target = scope.agents_dir / f"{conv.agent_name}.toml"
        if target.exists() and extract_agent_marker(target) is None and not force:
            raise SyncConflictError(
                f"{target} exists and is non-bridge (user-authored). Use --force."
            )


def list_bridges(scope: Scope) -> list[dict]:
    """Return list of bridge summaries for the given scope."""
    if not scope.plugins_dir.is_dir():
        return []
    bridges: list[dict] = []
    for plugin_dir in sorted(scope.plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
        manifest, marker = _read_manifest_with_marker(manifest_path)
        if manifest is None or marker is None:
            continue
        bridges.append(
            {
                "name": manifest.get("name", plugin_dir.name),
                "version": manifest.get("version", "0.0.0"),
                "sourcePlugin": marker["sourcePlugin"],
                "source": marker["source"],
                "sourceKind": marker["sourceKind"],
                "ref": marker.get("ref"),
                "commit": marker["commit"],
                "marketplace": marker["marketplace"],
                "syncedAt": marker["syncedAt"],
                "agents": marker.get("agents", []),
            }
        )
    return bridges


def uninstall_bridge(*, bridge_name: str, scope: Scope) -> dict:
    """Remove bridge plugin dir, its agents, and registry entry. Return summary."""
    bridge_dir = scope.plugins_dir / bridge_name
    manifest_path = bridge_dir / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no bridge '{bridge_name}' in {scope.plugins_dir}")

    _, marker = _read_manifest_with_marker(manifest_path)
    if marker is None:
        raise ValueError(f"{bridge_dir} is not a bridge (missing x-cc-bridge marker)")

    removed_agents: list[str] = []
    for agent_name in marker.get("agents", []):
        toml_path = scope.agents_dir / f"{agent_name}.toml"
        if toml_path.exists():
            toml_path.unlink()
            removed_agents.append(agent_name)

    shutil.rmtree(bridge_dir)

    if scope.registry.exists():
        registry = load_or_init_registry(scope.registry)
        remove_plugin_entry(registry, name=bridge_name)
        save_registry(scope.registry, registry)

    return {"bridge": bridge_name, "agents": removed_agents}
