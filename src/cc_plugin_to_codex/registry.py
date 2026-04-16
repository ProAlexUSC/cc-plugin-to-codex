"""Manage target marketplace.json registry."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY: dict[str, Any] = {
    "name": "cc-bridged-plugins",
    "interface": {"displayName": "CC Bridged Plugins"},
    "plugins": [],
}


def load_or_init_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_REGISTRY))  # deep copy
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("plugins", [])
    return data


def upsert_plugin_entry(registry: dict[str, Any], *, name: str, relative_path: str) -> None:
    entry = {
        "name": name,
        "source": {"source": "local", "path": relative_path},
        "policy": {"installation": "INSTALLED_BY_DEFAULT", "authentication": "ON_USE"},
        "category": "Productivity",
    }
    plugins = registry.setdefault("plugins", [])
    for i, p in enumerate(plugins):
        if p.get("name") == name:
            plugins[i] = entry
            return
    plugins.append(entry)


def remove_plugin_entry(registry: dict[str, Any], *, name: str) -> None:
    plugins = registry.setdefault("plugins", [])
    registry["plugins"] = [p for p in plugins if p.get("name") != name]


def save_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")
