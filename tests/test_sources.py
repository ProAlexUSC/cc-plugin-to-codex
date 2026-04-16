"""Tests for source resolution: git URL, local path, scan local marketplaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_plugin_to_codex.sources import (
    GIT_SHA_RE,
    classify_source,
    resolve_local,
    scan_local_marketplaces,
)


def test_classify_source_git_ssh() -> None:
    assert classify_source("git@code.byted.org:luna/cc-marketplace.git") == "git"


def test_classify_source_git_https() -> None:
    assert classify_source("https://github.com/foo/bar.git") == "git"


def test_classify_source_local_absolute() -> None:
    assert classify_source("/Users/me/workspace/cc-marketplace") == "local"


def test_classify_source_local_home() -> None:
    assert classify_source("~/.claude/plugins/marketplaces/foo") == "local"


def test_resolve_local_expands_home(tmp_path: Path, monkeypatch) -> None:
    # Path.expanduser() reads $HOME via os.path.expanduser, so both must be set.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    target = tmp_path / ".claude" / "plugins" / "marketplaces" / "foo"
    (target / ".claude-plugin").mkdir(parents=True)
    (target / ".claude-plugin" / "marketplace.json").write_text('{"name":"foo","plugins":[]}')

    resolved = resolve_local("~/.claude/plugins/marketplaces/foo")
    assert resolved.root == target.resolve()
    assert resolved.source_kind == "local"
    assert resolved.commit == "local"


def test_resolve_local_missing_marketplace_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_local(str(tmp_path))


def test_git_sha_regex_matches_short_and_full_shas() -> None:
    assert GIT_SHA_RE.match("abc1234") is not None
    assert GIT_SHA_RE.match("abcdef1234567890abcdef1234567890abcdef12") is not None


def test_git_sha_regex_rejects_non_shas() -> None:
    assert GIT_SHA_RE.match("main") is None
    assert GIT_SHA_RE.match("v1.0.0") is None
    assert GIT_SHA_RE.match("abc") is None  # too short
    assert GIT_SHA_RE.match("XYZ1234") is None  # non-hex uppercase
    assert GIT_SHA_RE.match("feature/branch") is None


def test_scan_local_marketplaces(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    base = tmp_path / ".claude" / "plugins" / "marketplaces"
    for name in ("mkt-a", "mkt-b"):
        (base / name / ".claude-plugin").mkdir(parents=True)
        (base / name / ".claude-plugin" / "marketplace.json").write_text(
            '{"name":"' + name + '","plugins":[]}'
        )
    (base / "no-manifest").mkdir()  # should be skipped

    found = scan_local_marketplaces()
    names = sorted(f.root.name for f in found)
    assert names == ["mkt-a", "mkt-b"]
