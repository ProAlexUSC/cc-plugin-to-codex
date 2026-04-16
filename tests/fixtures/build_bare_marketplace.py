"""Build (or rebuild) tests/fixtures/bare-marketplace.git from src_marketplace/.

Run this whenever src_marketplace/ changes. The bare repo is committed to
the repo so the e2e test does not require running this script in CI.

Usage:
    python tests/fixtures/build_bare_marketplace.py
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src_marketplace"
BARE = HERE / "bare-marketplace.git"
WORK = HERE / "_bare_workdir"


def main() -> None:
    if not SRC.is_dir():
        raise SystemExit(f"missing source: {SRC}")

    if BARE.exists():
        shutil.rmtree(BARE)
    if WORK.exists():
        shutil.rmtree(WORK)

    shutil.copytree(SRC, WORK)
    subprocess.run(["git", "init", "--initial-branch=main", str(WORK)], check=True)
    subprocess.run(
        ["git", "-C", str(WORK), "config", "user.email", "fixture@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(WORK), "config", "user.name", "Fixture Builder"],
        check=True,
    )
    subprocess.run(["git", "-C", str(WORK), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(WORK), "commit", "-m", "fixture: initial marketplace snapshot"],
        check=True,
    )

    subprocess.run(
        ["git", "clone", "--bare", str(WORK), str(BARE)],
        check=True,
    )

    shutil.rmtree(WORK)

    print(f"Built {BARE}")


if __name__ == "__main__":
    main()
