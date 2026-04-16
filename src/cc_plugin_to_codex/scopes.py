"""Scope path resolution: global vs project."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ScopeName = Literal["global", "project"]


@dataclass(frozen=True)
class Scope:
    name: ScopeName
    marketplace_root: Path
    plugins_dir: Path
    agents_dir: Path
    registry: Path

    def ensure_dirs(self) -> None:
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.registry.parent.mkdir(parents=True, exist_ok=True)

    def plugin_path_relative_to_root(self, bridge_name: str) -> str:
        """Return ./-prefixed path from marketplace_root to plugin dir."""
        plugin_path = self.plugins_dir / bridge_name
        rel = plugin_path.relative_to(self.marketplace_root)
        return f"./{rel.as_posix()}"


def resolve_scope(name: str, cwd: Path | None = None) -> Scope:
    if name == "global":
        root = Path.home()
    elif name == "project":
        root = cwd or Path.cwd()
    else:
        raise ValueError(f"unknown scope: {name!r} (expected 'global' or 'project')")

    return Scope(
        name=name,  # type: ignore[arg-type]
        marketplace_root=root,
        plugins_dir=root / ".codex" / "plugins",
        agents_dir=root / ".codex" / "agents",
        registry=root / ".agents" / "plugins" / "marketplace.json",
    )
