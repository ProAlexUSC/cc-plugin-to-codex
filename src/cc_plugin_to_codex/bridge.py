"""x-cc-bridge marker: plugin.json and agent TOML detection/creation."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict

from cc_plugin_to_codex import __version__

SourceKind = Literal["git", "local"]

MARKER_KEY = "x-cc-bridge"
TOOL_ID = f"cc-plugin-to-codex/{__version__}"


class BridgeMarker(TypedDict):
    sourcePlugin: str
    source: str
    sourceKind: SourceKind
    ref: str | None
    commit: str
    marketplace: str
    syncedAt: str
    tool: str
    agents: list[str]


def build_marker(
    *,
    source_plugin: str,
    source: str,
    source_kind: SourceKind,
    ref: str | None,
    commit: str,
    marketplace: str,
    agents: list[str],
    now: datetime | None = None,
) -> BridgeMarker:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return BridgeMarker(
        sourcePlugin=source_plugin,
        source=source,
        sourceKind=source_kind,
        ref=ref,
        commit=commit,
        marketplace=marketplace,
        syncedAt=ts,
        tool=TOOL_ID,
        agents=agents,
    )


def is_bridge_manifest(manifest: dict[str, Any]) -> bool:
    return MARKER_KEY in manifest and isinstance(manifest[MARKER_KEY], dict)


def extract_marker(manifest: dict[str, Any]) -> BridgeMarker | None:
    if not is_bridge_manifest(manifest):
        return None
    return manifest[MARKER_KEY]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Agent TOML first-line comment marker
# ---------------------------------------------------------------------------

AGENT_MARKER_REGEX = re.compile(r"^# x-cc-bridge: (\{.*\})$")


class AgentMarker(TypedDict):
    sourcePlugin: str
    sourceAgent: str
    bridgePlugin: str
    syncedAt: str


def build_agent_marker_line(
    *,
    source_plugin: str,
    source_agent: str,
    bridge_plugin: str,
    synced_at: str,
) -> str:
    payload = {
        "sourcePlugin": source_plugin,
        "sourceAgent": source_agent,
        "bridgePlugin": bridge_plugin,
        "syncedAt": synced_at,
    }
    return f"# x-cc-bridge: {json.dumps(payload, separators=(',', ':'), ensure_ascii=False)}"


def extract_agent_marker(toml_path: Path) -> AgentMarker | None:
    if not toml_path.exists():
        return None
    try:
        with toml_path.open("r", encoding="utf-8") as f:
            first_line = f.readline().rstrip("\n")
    except OSError:
        return None
    m = AGENT_MARKER_REGEX.match(first_line)
    if not m:
        return None
    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    required = {"sourcePlugin", "sourceAgent", "bridgePlugin", "syncedAt"}
    if not required.issubset(payload.keys()):
        return None
    return payload  # type: ignore[return-value]
