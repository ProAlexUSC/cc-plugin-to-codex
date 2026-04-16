"""Tests for source resolution: git URL, local path, scan local marketplaces."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cc_plugin_to_codex.sources import (
    GIT_SHA_RE,
    classify_source,
    resolve_git,
    resolve_local,
    scan_local_marketplaces,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # Network schemes with .git suffix — classified as git
        ("git@code.byted.org:luna/cc-marketplace.git", "git"),
        ("https://github.com/foo/bar.git", "git"),
        # file:// accepts any path — real local checkouts often lack .git suffix
        ("file:///tmp/repo.git", "git"),
        ("file:///Users/me/my-repo", "git"),
        # Filesystem paths and typo'd network URLs fall back to local
        ("/Users/me/workspace/cc-marketplace", "local"),
        ("~/.claude/plugins/marketplaces/foo", "local"),
        # Non-file network schemes require .git to guard against typos
        ("https://example.com/foo", "local"),
    ],
)
def test_classify_source(source: str, expected: str) -> None:
    assert classify_source(source) == expected


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


def test_resolve_git_timeout_raises(monkeypatch, tmp_path) -> None:
    """A hung git command must surface as a RuntimeError mentioning timeout."""

    def _fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr("cc_plugin_to_codex.sources.subprocess.run", _fake_run)

    with pytest.raises(RuntimeError, match="timed out"):
        resolve_git("https://example.com/repo.git", ref="main", timeout=1)


def test_resolve_git_nonzero_exit_raises(monkeypatch) -> None:
    """A failed git clone must surface as a RuntimeError with stderr."""

    def _fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd, returncode=128, stdout="", stderr="fatal: repository not found"
        )

    monkeypatch.setattr("cc_plugin_to_codex.sources.subprocess.run", _fake_run)

    with pytest.raises(RuntimeError, match="repository not found"):
        resolve_git("https://example.com/missing.git", ref="main")


def test_resolve_git_cleans_temp_dir_on_failure(monkeypatch, tmp_path) -> None:
    """When clone fails, the temp dir created at the start must be removed."""
    captured = {}

    def _fake_run(cmd, **kwargs):
        if "clone" in cmd:
            for arg in cmd:
                if "/cc2codex-" in str(arg):
                    captured["tmp"] = Path(str(arg))
                    break
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr("cc_plugin_to_codex.sources.subprocess.run", _fake_run)

    with pytest.raises(RuntimeError, match="boom"):
        resolve_git("https://example.com/repo.git", ref="main")

    assert "tmp" in captured, "fake _run_git should have captured a temp dir path"
    assert not captured["tmp"].exists(), "temp dir must be cleaned up on failure"


def test_resolve_git_sha_path_uses_fetch_then_checkout(monkeypatch, tmp_path) -> None:
    """When ref is a SHA, the code must clone --no-checkout, fetch, then checkout."""
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="abc1234deadbeef\n", stderr=""
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("cc_plugin_to_codex.sources.subprocess.run", _fake_run)

    result = resolve_git("https://example.com/repo.git", ref="abc1234deadbeef")

    assert "--no-checkout" in calls[0], "SHA-mode clone should use --no-checkout"
    assert "fetch" in calls[1]
    assert "checkout" in calls[2]
    assert "rev-parse" in calls[-1]
    assert result.commit == "abc1234deadbeef"

    if result.cleanup and result.cleanup.exists():
        import shutil

        shutil.rmtree(result.cleanup, ignore_errors=True)


def test_resolve_git_branch_path_uses_clone_branch(monkeypatch) -> None:
    """When ref is a branch name (not a SHA), the code must use --branch."""
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="aaaa\n", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("cc_plugin_to_codex.sources.subprocess.run", _fake_run)

    result = resolve_git("https://example.com/repo.git", ref="main")
    assert "--branch" in calls[0]
    assert "main" in calls[0]

    if result.cleanup and result.cleanup.exists():
        import shutil

        shutil.rmtree(result.cleanup, ignore_errors=True)
