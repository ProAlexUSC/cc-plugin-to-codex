"""Read source marketplace.json and extract plugin metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PluginInfo:
    name: str
    version: str
    description: str
    plugin_dir: Path
    has_codex_manifest: bool
    skill_count: int
    agent_count: int


@dataclass(frozen=True)
class SourceMarketplace:
    name: str
    root: Path
    plugins: list[PluginInfo]


def read_source_marketplace(root: Path) -> SourceMarketplace:
    mp_path = root / ".claude-plugin" / "marketplace.json"
    if not mp_path.exists():
        raise FileNotFoundError(f"marketplace.json not found at {mp_path}")
    with mp_path.open("r", encoding="utf-8") as f:
        mp = json.load(f)

    plugins: list[PluginInfo] = []
    for entry in mp.get("plugins", []):
        plugin_rel = _extract_source_path(entry)
        plugin_dir = (root / plugin_rel).resolve()
        plugins.append(_read_plugin_info(plugin_dir, declared_name=entry["name"]))

    return SourceMarketplace(name=mp.get("name", "<unnamed>"), root=root, plugins=plugins)


def _extract_source_path(entry: dict) -> str:
    """Support both marketplace.json shapes:
      - {"source": "./plugins/foo"}          (string, used by Claude Code spec)
      - {"source": {"path": "./plugins/foo"}} (dict with path key)
    Falls back to ./plugins/<name> if neither present.
    """
    src = entry.get("source")
    if isinstance(src, str):
        return src
    if isinstance(src, dict):
        return src.get("path", f"./plugins/{entry['name']}")
    return f"./plugins/{entry['name']}"


def _read_plugin_info(plugin_dir: Path, declared_name: str) -> PluginInfo:
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest: dict = {}
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

    skills_dir = plugin_dir / "skills"
    agents_dir = plugin_dir / "agents"
    codex_manifest = plugin_dir / ".codex-plugin" / "plugin.json"

    return PluginInfo(
        name=manifest.get("name", declared_name),
        version=manifest.get("version", "0.0.0"),
        description=manifest.get("description", ""),
        plugin_dir=plugin_dir,
        has_codex_manifest=codex_manifest.exists(),
        skill_count=sum(1 for p in skills_dir.iterdir() if p.is_dir())
        if skills_dir.is_dir()
        else 0,
        agent_count=sum(1 for p in agents_dir.glob("*.md")) if agents_dir.is_dir() else 0,
    )
