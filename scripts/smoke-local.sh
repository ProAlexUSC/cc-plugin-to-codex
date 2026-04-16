#!/usr/bin/env bash
# Local smoke test: install the package in ephemeral tool form via `uvx --from .`
# and run a full plugin-sync against the committed bare-marketplace.git fixture.
# Redirects HOME to a throwaway temp dir so real ~/.codex is untouched.
#
# Run from the repo root:
#   ./scripts/smoke-local.sh
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$repo_root/tests/fixtures/bare-marketplace.git"

if [[ ! -d "$fixture" ]]; then
    echo "missing fixture: $fixture"
    echo "run: uv run python tests/fixtures/build_bare_marketplace.py"
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found in PATH; install via https://docs.astral.sh/uv/"
    exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

echo "==> uv       : $(uv --version)"
echo "==> smoke HOME: $tmpdir"
echo "==> source    : file://$fixture"

HOME="$tmpdir" uvx --quiet --from "$repo_root" cc2codex plugin-sync \
    --source "file://$fixture" \
    --ref main \
    --all-plugins \
    --scope global \
    --yes \
    --non-interactive

echo
echo "==> plugins installed:"
ls "$tmpdir/.codex/plugins/"
echo
echo "==> agents generated:"
ls "$tmpdir/.codex/agents/"
echo
echo "smoke: OK"
