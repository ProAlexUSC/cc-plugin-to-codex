"""Source resolution: Git URL, local path, scan local marketplaces."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SourceKind = Literal["git", "local"]

GIT_URL_RE = re.compile(r"^(git@|https?://|ssh://|git://|file://).+\.git/?$|^git@.+:.+$")
# A plausible git SHA: 7–40 hex chars, all lowercase (git rev-parse output convention).
GIT_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

# Bound git operations so a hung remote doesn't freeze the CLI.
GIT_OP_TIMEOUT_SECONDS = 120
GIT_QUICK_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class ResolvedSource:
    root: Path  # directory containing .claude-plugin/marketplace.json
    source_kind: SourceKind
    source: str  # original URL or path
    ref: str | None
    commit: str  # git SHA or "local"
    cleanup: Path | None  # temp dir to rm on completion, None for local


def classify_source(s: str) -> SourceKind:
    if GIT_URL_RE.match(s):
        return "git"
    return "local"


def resolve_source(source: str, *, ref: str = "master") -> ResolvedSource:
    kind = classify_source(source)
    if kind == "git":
        return resolve_git(source, ref=ref)
    return resolve_local(source)


def resolve_git(
    url: str,
    *,
    ref: str = "master",
    timeout: int = GIT_OP_TIMEOUT_SECONDS,
) -> ResolvedSource:
    """Clone `url` at `ref` into /tmp and return ResolvedSource.

    `ref` accepts a branch, tag, or commit SHA. SHAs are handled via
    fetch+checkout since `git clone --branch` rejects raw SHAs.
    """
    tmp_dir = Path(tempfile.gettempdir()) / f"cc2codex-{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=False)

    try:
        if GIT_SHA_RE.match(ref):
            _run_git(
                ["git", "clone", "--filter=blob:none", "--no-checkout", url, str(tmp_dir)],
                timeout=timeout,
            )
            _run_git(
                ["git", "-C", str(tmp_dir), "fetch", "--depth=1", "origin", ref], timeout=timeout
            )
            _run_git(
                ["git", "-C", str(tmp_dir), "checkout", ref], timeout=GIT_QUICK_TIMEOUT_SECONDS
            )
        else:
            _run_git(
                ["git", "clone", "--depth=1", "--branch", ref, url, str(tmp_dir)],
                timeout=timeout,
            )
        commit = _run_git(
            ["git", "-C", str(tmp_dir), "rev-parse", "HEAD"],
            timeout=GIT_QUICK_TIMEOUT_SECONDS,
        ).strip()
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    return ResolvedSource(
        root=tmp_dir,
        source_kind="git",
        source=url,
        ref=ref,
        commit=commit,
        cleanup=tmp_dir,
    )


def _run_git(cmd: list[str], *, timeout: int) -> str:
    """Run a git command with a bounded timeout. Raise RuntimeError on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"git command timed out after {timeout}s: {' '.join(cmd)}") from e
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"git failed ({' '.join(cmd)}): {stderr}")
    return result.stdout


def resolve_local(path: str) -> ResolvedSource:
    p = Path(path).expanduser().resolve()
    mp = p / ".claude-plugin" / "marketplace.json"
    if not mp.exists():
        raise FileNotFoundError(f"not a CC marketplace (missing {mp})")
    return ResolvedSource(
        root=p,
        source_kind="local",
        source=str(p),
        ref=None,
        commit="local",
        cleanup=None,
    )


def scan_local_marketplaces() -> list[ResolvedSource]:
    base = Path.home() / ".claude" / "plugins" / "marketplaces"
    if not base.is_dir():
        return []
    results: list[ResolvedSource] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        mp = child / ".claude-plugin" / "marketplace.json"
        if not mp.exists():
            continue
        results.append(
            ResolvedSource(
                root=child.resolve(),
                source_kind="local",
                source=str(child.resolve()),
                ref=None,
                commit="local",
                cleanup=None,
            )
        )
    return results


def cleanup_source(resolved: ResolvedSource) -> None:
    if resolved.cleanup and resolved.cleanup.exists():
        shutil.rmtree(resolved.cleanup, ignore_errors=True)
