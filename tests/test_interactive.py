"""Tests for interactive prompt wrappers and non-interactive fallback."""

from __future__ import annotations

import pytest

from cc_plugin_to_codex.interactive import (
    StrictModeError,
    confirm,
    is_non_interactive,
    prompt_scope,
    prompt_select_bridges,
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


def test_prompt_select_plugins_interactive_returns_user_choice(mock_questionary) -> None:
    mock_questionary.checkbox = [["demo-a"]]
    result = prompt_select_plugins(
        available=["demo-a", "demo-b"],
        preselected=[],
        all_plugins=False,
        strict=False,
    )
    assert result == ["demo-a"]


def test_prompt_select_plugins_interactive_empty_choice_raises(mock_questionary) -> None:
    mock_questionary.checkbox = [None]  # user hit Ctrl-C
    with pytest.raises(StrictModeError, match="no plugins selected"):
        prompt_select_plugins(
            available=["demo-a"],
            preselected=[],
            all_plugins=False,
            strict=False,
        )


def test_prompt_source_kind_interactive_git_url(mock_questionary) -> None:
    mock_questionary.select = ["Git URL"]
    mock_questionary.text = ["https://example.com/repo.git"]
    result = prompt_source_kind(source=None, strict=False)
    assert result == "https://example.com/repo.git"


def test_prompt_source_kind_interactive_local_path(mock_questionary, tmp_path) -> None:
    mock_questionary.select = ["Local path"]
    mock_questionary.path = [str(tmp_path)]
    result = prompt_source_kind(source=None, strict=False)
    assert result == str(tmp_path)


def test_prompt_source_kind_aborted_top_level(mock_questionary) -> None:
    mock_questionary.select = [None]  # user hit Ctrl-C on the type picker
    with pytest.raises(StrictModeError, match="source required"):
        prompt_source_kind(source=None, strict=False)


def test_prompt_source_kind_text_empty_raises(mock_questionary) -> None:
    mock_questionary.select = ["Git URL"]
    mock_questionary.text = [""]
    with pytest.raises(StrictModeError, match="source required"):
        prompt_source_kind(source=None, strict=False)


def test_prompt_source_kind_scan_multi_marketplace(mock_questionary, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    base = tmp_path / ".claude" / "plugins" / "marketplaces"
    for name in ("alpha", "beta"):
        (base / name / ".claude-plugin").mkdir(parents=True)
        (base / name / ".claude-plugin" / "marketplace.json").write_text(
            '{"name":"' + name + '","plugins":[]}'
        )
    mock_questionary.select = [
        "Scan ~/.claude/plugins/marketplaces/",
        f"alpha  ({(base / 'alpha').resolve()})",
    ]
    result = prompt_source_kind(source=None, strict=False)
    assert result == str((base / "alpha").resolve())


def test_prompt_source_kind_scan_multi_aborted(mock_questionary, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    base = tmp_path / ".claude" / "plugins" / "marketplaces"
    for name in ("alpha", "beta"):
        (base / name / ".claude-plugin").mkdir(parents=True)
        (base / name / ".claude-plugin" / "marketplace.json").write_text(
            '{"name":"' + name + '","plugins":[]}'
        )
    mock_questionary.select = ["Scan ~/.claude/plugins/marketplaces/", None]
    with pytest.raises(StrictModeError, match="no marketplace selected"):
        prompt_source_kind(source=None, strict=False)


def test_prompt_scope_strict_without_value_raises() -> None:
    with pytest.raises(StrictModeError, match="--scope"):
        prompt_scope(scope=None, strict=True)


def test_prompt_scope_passes_through_valid_value() -> None:
    assert prompt_scope(scope="global", strict=True) == "global"
    assert prompt_scope(scope="project", strict=False) == "project"


def test_prompt_scope_interactive_returns_choice(mock_questionary) -> None:
    mock_questionary.select = ["project"]
    assert prompt_scope(scope=None, strict=False) == "project"


def test_prompt_scope_interactive_aborted_raises(mock_questionary) -> None:
    mock_questionary.select = [None]
    with pytest.raises(StrictModeError, match="scope required"):
        prompt_scope(scope=None, strict=False)


def test_confirm_yes_flag_returns_true_without_prompt() -> None:
    assert confirm(message="proceed?", yes_flag=True, strict=False) is True


def test_confirm_strict_returns_true_without_prompt() -> None:
    assert confirm(message="proceed?", yes_flag=False, strict=True) is True


def test_confirm_interactive_returns_user_choice(mock_questionary) -> None:
    mock_questionary.confirm = [True]
    assert confirm(message="proceed?", yes_flag=False, strict=False) is True
    mock_questionary.confirm = [False]
    assert confirm(message="proceed?", yes_flag=False, strict=False) is False


def test_prompt_select_bridges_empty_list_raises() -> None:
    with pytest.raises(StrictModeError, match="no bridge plugins"):
        prompt_select_bridges(available=[], strict=False)


def test_prompt_select_bridges_strict_with_options_raises() -> None:
    with pytest.raises(StrictModeError, match="must specify"):
        prompt_select_bridges(available=["cc-foo", "cc-bar"], strict=True)


def test_prompt_select_bridges_interactive_returns_choice(mock_questionary) -> None:
    mock_questionary.checkbox = [["cc-foo"]]
    result = prompt_select_bridges(available=["cc-foo", "cc-bar"], strict=False)
    assert result == ["cc-foo"]


def test_prompt_select_bridges_interactive_empty_raises(mock_questionary) -> None:
    mock_questionary.checkbox = [None]
    with pytest.raises(StrictModeError, match="no bridges selected"):
        prompt_select_bridges(available=["cc-foo"], strict=False)
