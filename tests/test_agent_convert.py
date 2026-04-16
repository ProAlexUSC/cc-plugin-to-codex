"""Tests for CC agent md → Codex TOML conversion."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_plugin_to_codex.agent_convert import (
    convert_agent,
    snake_case_name,
)


def test_snake_case_name_converts_kebab() -> None:
    assert snake_case_name("ios-dev") == "ios_dev"
    assert snake_case_name("code-research-master") == "code_research_master"
    assert snake_case_name("simple") == "simple"


def test_convert_agent_basic(tmp_path: Path) -> None:
    md = tmp_path / "helper.md"
    md.write_text(
        """---
name: helper
description: A helpful agent
---

You are a helpful assistant. Do helpful things.
""",
        encoding="utf-8",
    )
    result = convert_agent(
        md, bridge_plugin="cc-ios-dev", source_plugin="ios-dev", synced_at="2026-04-14T10:30:00Z"
    )
    assert result.agent_name == "cc_ios_dev_helper"
    assert 'name = "cc_ios_dev_helper"' in result.toml
    assert 'description = "A helpful agent"' in result.toml
    assert "You are a helpful assistant" in result.toml
    assert result.toml.startswith("# x-cc-bridge: ")
    # warnings empty for clean input
    assert result.warnings == []


def test_convert_agent_drops_model_and_tools(tmp_path: Path) -> None:
    md = tmp_path / "helper.md"
    md.write_text(
        """---
name: helper
description: d
model: opus
tools: [Read, Grep]
---

body
""",
        encoding="utf-8",
    )
    result = convert_agent(
        md, bridge_plugin="cc-ios-dev", source_plugin="ios-dev", synced_at="2026-04-14T10:30:00Z"
    )
    assert "model" not in result.toml.lower().replace(
        "model_reasoning", ""
    )  # no top-level model key
    assert "tools" not in result.toml.lower()
    warnings_text = " ".join(w.field for w in result.warnings)
    assert "model" in warnings_text
    assert "tools" in warnings_text


def test_convert_agent_missing_description_uses_fallback(tmp_path: Path) -> None:
    md = tmp_path / "nameless.md"
    md.write_text(
        """---
name: nameless
---

body
""",
        encoding="utf-8",
    )
    result = convert_agent(
        md, bridge_plugin="cc-ios-dev", source_plugin="ios-dev", synced_at="2026-04-14T10:30:00Z"
    )
    assert "Bridged from CC plugin ios-dev" in result.toml


def test_convert_agent_missing_name_raises(tmp_path: Path) -> None:
    md = tmp_path / "bad.md"
    md.write_text(
        """---
description: d
---

body
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required 'name'"):
        convert_agent(md, bridge_plugin="cc-ios-dev", source_plugin="ios-dev", synced_at="x")


def test_convert_agent_no_frontmatter_raises(tmp_path: Path) -> None:
    md = tmp_path / "bare.md"
    md.write_text("just body\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        convert_agent(md, bridge_plugin="cc-ios-dev", source_plugin="ios-dev", synced_at="x")


def test_convert_agent_triple_quote_body_safe(tmp_path: Path) -> None:
    # body containing triple-quotes needs escaping
    md = tmp_path / "tricky.md"
    md.write_text(
        '---\nname: tricky\ndescription: d\n---\n\nbody with """triple""" quotes\n',
        encoding="utf-8",
    )
    result = convert_agent(md, bridge_plugin="cc-ios-dev", source_plugin="ios-dev", synced_at="x")
    # loading the TOML back should succeed
    import tomllib

    # strip marker comment line for parsing
    toml_body = "\n".join(result.toml.splitlines()[1:])
    parsed = tomllib.loads(toml_body)
    assert "triple" in parsed["developer_instructions"]


def test_convert_agent_non_dict_frontmatter_raises(tmp_path: Path) -> None:
    """Frontmatter that is a YAML list (not a mapping) must raise ValueError."""
    md = tmp_path / "list.md"
    md.write_text("---\n- item1\n- item2\n---\nbody\n")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        convert_agent(md, bridge_plugin="cc-x", source_plugin="x", synced_at="t")


def test_convert_agent_unknown_field_warns(tmp_path: Path) -> None:
    """Unknown frontmatter fields must produce a ConversionWarning, not raise."""
    md = tmp_path / "unknown.md"
    md.write_text("---\nname: thing\ndescription: d\nweird_field: 42\n---\nbody\n")
    result = convert_agent(md, bridge_plugin="cc-x", source_plugin="x", synced_at="t")
    warning_fields = [w.field for w in result.warnings]
    assert "weird_field" in warning_fields


def test_convert_agent_dropped_field_warns(tmp_path: Path) -> None:
    """Explicitly dropped fields (model, tools) must produce a ConversionWarning."""
    md = tmp_path / "dropped.md"
    md.write_text("---\nname: thing\ndescription: d\nmodel: gpt-4\ntools: [bash]\n---\nbody\n")
    result = convert_agent(md, bridge_plugin="cc-x", source_plugin="x", synced_at="t")
    fields = [w.field for w in result.warnings]
    assert "model" in fields
    assert "tools" in fields


def test_convert_agent_passthrough_nickname_candidates(tmp_path: Path) -> None:
    """nickname_candidates must be passed through to the TOML output."""
    md = tmp_path / "nicks.md"
    md.write_text(
        '---\nname: thing\ndescription: d\nnickname_candidates: ["foo", "bar"]\n---\nbody\n'
    )
    result = convert_agent(md, bridge_plugin="cc-x", source_plugin="x", synced_at="t")
    assert "nickname_candidates" in result.toml
    assert "foo" in result.toml
