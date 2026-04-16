"""Tests for interactive prompt wrappers and non-interactive fallback."""
from __future__ import annotations

import pytest

from cc_plugin_to_codex.interactive import (
    StrictModeError,
    is_non_interactive,
    prompt_select_plugins,
    prompt_source_kind,
)


def test_is_non_interactive_true_when_flag_set() -> None:
    assert is_non_interactive(non_interactive_flag=True, stdin_isatty=True) is True


def test_is_non_interactive_true_when_not_tty() -> None:
    assert is_non_interactive(non_interactive_flag=False, stdin_isatty=False) is True


def test_is_non_interactive_false_when_tty_and_no_flag() -> None:
    assert is_non_interactive(non_interactive_flag=False, stdin_isatty=True) is False


def test_prompt_select_plugins_strict_without_selections_raises() -> None:
    with pytest.raises(StrictModeError, match="--plugin"):
        prompt_select_plugins(
            available=["demo-a", "demo-b"],
            preselected=[],
            all_plugins=False,
            strict=True,
        )


def test_prompt_select_plugins_strict_with_all_plugins_returns_all() -> None:
    result = prompt_select_plugins(
        available=["demo-a", "demo-b"],
        preselected=[],
        all_plugins=True,
        strict=True,
    )
    assert result == ["demo-a", "demo-b"]


def test_prompt_select_plugins_strict_with_preselected_returns_those() -> None:
    result = prompt_select_plugins(
        available=["demo-a", "demo-b", "demo-c"],
        preselected=["demo-a", "demo-c"],
        all_plugins=False,
        strict=True,
    )
    assert result == ["demo-a", "demo-c"]


def test_prompt_select_plugins_strict_rejects_unknown_preselected() -> None:
    with pytest.raises(StrictModeError, match="not found"):
        prompt_select_plugins(
            available=["demo-a"],
            preselected=["demo-b"],
            all_plugins=False,
            strict=True,
        )


def test_prompt_source_kind_strict_without_source_raises() -> None:
    with pytest.raises(StrictModeError, match="--source"):
        prompt_source_kind(source=None, strict=True)


def test_prompt_source_kind_scan_with_single_marketplace_returns_path(
    tmp_path, monkeypatch
) -> None:
    """Scan picks the marketplace automatically when only one exists."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    mk = tmp_path / ".claude" / "plugins" / "marketplaces" / "only"
    (mk / ".claude-plugin").mkdir(parents=True)
    (mk / ".claude-plugin" / "marketplace.json").write_text('{"name":"only","plugins":[]}')

    class _FakeQuestionary:
        @staticmethod
        def select(_msg, **_kw):
            class _Q:
                @staticmethod
                def ask():
                    return "Scan ~/.claude/plugins/marketplaces/"
            return _Q()

    monkeypatch.setitem(__import__("sys").modules, "questionary", _FakeQuestionary)

    result = prompt_source_kind(source=None, strict=False)
    assert result == str(mk.resolve())


def test_prompt_source_kind_scan_empty_raises(tmp_path, monkeypatch) -> None:
    """Scan with no local marketplaces aborts with a clear message."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    class _FakeQuestionary:
        @staticmethod
        def select(_msg, **_kw):
            class _Q:
                @staticmethod
                def ask():
                    return "Scan ~/.claude/plugins/marketplaces/"
            return _Q()

    monkeypatch.setitem(__import__("sys").modules, "questionary", _FakeQuestionary)

    with pytest.raises(StrictModeError, match="no marketplaces found"):
        prompt_source_kind(source=None, strict=False)
