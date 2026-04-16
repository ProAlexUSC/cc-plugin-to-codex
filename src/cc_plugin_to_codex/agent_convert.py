"""Convert CC agent markdown (YAML frontmatter + body) to Codex agent TOML."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w
import yaml

from cc_plugin_to_codex.bridge import build_agent_marker_line

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

# Codex-supported top-level fields we preserve from frontmatter if present
_PASSTHROUGH_FIELDS = {"nickname_candidates"}

# Fields we explicitly drop (not Codex-compatible)
_DROPPED_FIELDS = {"model", "tools"}


@dataclass
class ConversionWarning:
    field: str
    reason: str


@dataclass
class ConversionResult:
    agent_name: str
    toml: str
    warnings: list[ConversionWarning] = field(default_factory=list)


def snake_case_name(s: str) -> str:
    return s.replace("-", "_")


def convert_agent(
    md_path: Path,
    *,
    bridge_plugin: str,
    source_plugin: str,
    synced_at: str,
) -> ConversionResult:
    text = md_path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{md_path}: no YAML frontmatter found")
    fm_text, body = m.group(1), m.group(2).lstrip("\n")
    frontmatter = yaml.safe_load(fm_text) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{md_path}: frontmatter must be a YAML mapping")

    source_agent = frontmatter.get("name")
    if not source_agent:
        raise ValueError(f"{md_path}: frontmatter missing required 'name'")

    description = frontmatter.get("description") or f"Bridged from CC plugin {source_plugin}"

    warnings: list[ConversionWarning] = []
    for key in frontmatter:
        if key in {"name", "description"} or key in _PASSTHROUGH_FIELDS:
            continue
        if key in _DROPPED_FIELDS:
            warnings.append(ConversionWarning(field=key, reason="Not compatible with Codex"))
        else:
            warnings.append(ConversionWarning(field=key, reason="Unknown frontmatter field, dropped"))

    agent_name = f"cc_{snake_case_name(source_plugin)}_{snake_case_name(source_agent)}"

    toml_dict: dict[str, Any] = {
        "name": agent_name,
        "description": description,
        "developer_instructions": body,
    }
    # passthrough fields
    for key in _PASSTHROUGH_FIELDS:
        if key in frontmatter:
            toml_dict[key] = frontmatter[key]

    toml_body = tomli_w.dumps(toml_dict)
    marker_line = build_agent_marker_line(
        source_plugin=source_plugin,
        source_agent=source_agent,
        bridge_plugin=bridge_plugin,
        synced_at=synced_at,
    )
    full_toml = f"{marker_line}\n{toml_body}"

    return ConversionResult(agent_name=agent_name, toml=full_toml, warnings=warnings)
