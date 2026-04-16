"""Shared pytest fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Replace $HOME with a temp directory so tests don't touch the real home."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


@pytest.fixture
def fake_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Replace cwd with a temp directory."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


@dataclass
class _QuestionaryResponses:
    """Pre-program answers for each questionary call type. None = simulate Ctrl-C."""

    select: list = field(default_factory=list)
    checkbox: list = field(default_factory=list)
    text: list = field(default_factory=list)
    path: list = field(default_factory=list)
    confirm: list = field(default_factory=list)


@pytest.fixture
def mock_questionary(monkeypatch: pytest.MonkeyPatch) -> _QuestionaryResponses:
    """Replace the `questionary` module with a stub driven by pre-programmed
    response queues. Each call pops from the relevant queue.

    Usage:
        def test_x(mock_questionary):
            mock_questionary.select = ["Git URL"]
            mock_questionary.text = ["https://example.com/repo.git"]
            ...

    A queue of [None] simulates Ctrl-C / aborted prompt.
    """
    import sys
    import types

    responses = _QuestionaryResponses()

    def _make_prompt(kind: str):
        def _prompt(*_args, **_kwargs):
            queue = getattr(responses, kind)

            class _Q:
                @staticmethod
                def ask():
                    if not queue:
                        raise AssertionError(f"questionary.{kind} called with no queued response")
                    return queue.pop(0)

            return _Q()

        return _prompt

    fake = types.ModuleType("questionary")
    fake.select = _make_prompt("select")
    fake.checkbox = _make_prompt("checkbox")
    fake.text = _make_prompt("text")
    fake.path = _make_prompt("path")
    fake.confirm = _make_prompt("confirm")

    monkeypatch.setitem(sys.modules, "questionary", fake)
    return responses
