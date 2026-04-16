"""Tests for x-cc-bridge marker handling."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cc_plugin_to_codex.bridge import (
    BridgeMarker,
    build_marker,
    extract_marker,
    is_bridge_manifest,
)


def test_build_marker_has_required_fields() -> None:
    marker = build_marker(
        source_plugin="ios-dev",
        source="git@code.byted.org:luna/cc-marketplace.git",
        source_kind="git",
        ref="master",
        commit="abc123",
        marketplace="luna-cc-marketplace",
        agents=["cc_ios_dev_helper"],
    )
    assert marker["sourcePlugin"] == "ios-dev"
    assert marker["source"] == "git@code.byted.org:luna/cc-marketplace.git"
    assert marker["sourceKind"] == "git"
    assert marker["ref"] == "master"
    assert marker["commit"] == "abc123"
    assert marker["marketplace"] == "luna-cc-marketplace"
    assert marker["agents"] == ["cc_ios_dev_helper"]
    assert marker["tool"].startswith("cc-plugin-to-codex/")
    # syncedAt is ISO-8601 UTC
    ts = datetime.fromisoformat(marker["syncedAt"].replace("Z", "+00:00"))
    assert ts.tzinfo is not None


def test_build_marker_local_source() -> None:
    marker = build_marker(
        source_plugin="ios-dev",
        source="/local/path/to/marketplace",
        source_kind="local",
        ref=None,
        commit="local",
        marketplace="luna-cc-marketplace",
        agents=[],
    )
    assert marker["sourceKind"] == "local"
    assert marker["ref"] is None
    assert marker["commit"] == "local"


def test_is_bridge_manifest_true_when_marker_present() -> None:
    manifest = {"name": "cc-ios-dev", "x-cc-bridge": {"sourcePlugin": "ios-dev"}}
    assert is_bridge_manifest(manifest) is True


def test_is_bridge_manifest_false_without_marker() -> None:
    assert is_bridge_manifest({"name": "cc-ios-dev"}) is False
    assert is_bridge_manifest({}) is False


def test_extract_marker_returns_marker_dict() -> None:
    manifest = {
        "name": "cc-ios-dev",
        "x-cc-bridge": {"sourcePlugin": "ios-dev", "source": "x", "sourceKind": "git"},
    }
    marker = extract_marker(manifest)
    assert marker is not None
    assert marker["sourcePlugin"] == "ios-dev"


def test_extract_marker_returns_none_without_marker() -> None:
    assert extract_marker({"name": "cc-ios-dev"}) is None


from cc_plugin_to_codex.bridge import (  # noqa: E402
    build_agent_marker_line,
    extract_agent_marker,
)


def test_build_agent_marker_line_is_valid_toml_comment() -> None:
    line = build_agent_marker_line(
        source_plugin="ios-dev",
        source_agent="helper",
        bridge_plugin="cc-ios-dev",
        synced_at="2026-04-14T10:30:00Z",
    )
    assert line.startswith("# x-cc-bridge: ")
    # comment payload is valid JSON
    import json
    payload = json.loads(line.removeprefix("# x-cc-bridge: "))
    assert payload["sourcePlugin"] == "ios-dev"
    assert payload["sourceAgent"] == "helper"
    assert payload["bridgePlugin"] == "cc-ios-dev"
    assert payload["syncedAt"] == "2026-04-14T10:30:00Z"


def test_extract_agent_marker_from_toml_first_line(tmp_path: Path) -> None:
    toml_file = tmp_path / "cc_ios_dev_helper.toml"
    toml_file.write_text(
        '# x-cc-bridge: {"sourcePlugin":"ios-dev","sourceAgent":"helper","bridgePlugin":"cc-ios-dev","syncedAt":"2026-04-14T10:30:00Z"}\n'
        'name = "cc_ios_dev_helper"\n'
        'description = "d"\n'
        'developer_instructions = "i"\n'
    )
    marker = extract_agent_marker(toml_file)
    assert marker is not None
    assert marker["sourcePlugin"] == "ios-dev"
    assert marker["bridgePlugin"] == "cc-ios-dev"


def test_extract_agent_marker_none_when_no_comment(tmp_path: Path) -> None:
    toml_file = tmp_path / "user_authored.toml"
    toml_file.write_text('name = "user_authored"\ndescription = "d"\ndeveloper_instructions = "i"\n')
    assert extract_agent_marker(toml_file) is None


def test_extract_agent_marker_none_when_file_missing(tmp_path: Path) -> None:
    assert extract_agent_marker(tmp_path / "missing.toml") is None
