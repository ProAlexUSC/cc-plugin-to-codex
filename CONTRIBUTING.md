# Contributing to cc-plugin-to-codex

Thank you for considering a contribution. This project bridges Claude Code
marketplace plugins into Codex. Contributions of any size are welcome —
bug reports, doc fixes, test additions, feature work.

## Development setup

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ProAlexUSC/cc-plugin-to-codex
cd cc-plugin-to-codex
uv sync --extra dev
uv run pre-commit install
```

`pre-commit install` wires up the same lint/format/type checks that CI runs,
so issues surface before push.

## Running tests

```bash
uv run pytest -v                         # full suite
uv run pytest tests/test_sync.py -v      # single file
uv run pytest --cov=cc_plugin_to_codex   # with coverage report
```

CI enforces an overall coverage floor of 85% and per-file floors for
`interactive.py` (≥90%) and `sources.py` (≥85%). The e2e test under
`tests/test_e2e_sync.py` requires the bare-git fixture under
`tests/fixtures/bare-marketplace.git/` (committed to the repo).
If you change `tests/fixtures/src_marketplace/`, rebuild the bare
repo with:

```bash
uv run python tests/fixtures/build_bare_marketplace.py
```

## Lint and type checks

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/cc_plugin_to_codex
```

Or just run all hooks:

```bash
uv run pre-commit run --all-files
```

## Local smoke test

To verify the published CLI form (`uvx --from .`) works end-to-end against
the bare-marketplace fixture without touching your real `~/.codex`:

```bash
./scripts/smoke-local.sh
```

The script redirects `$HOME` to a throwaway temp dir, runs `plugin-sync`,
prints the produced bridges + agents, and cleans up. Useful before opening
a PR that touches CLI/sync code.

## Codex schema reference

When changing how the tool generates `plugin.json` manifests or agent
TOML files, consult the official Codex documentation in
`docs/codex-spec/`:

- `codex-plugins.md` — plugin manifest and marketplace structure
- `codex-subagents.md` — custom agent TOML schema; required fields are
  `name`, `description`, `developer_instructions`

These two files are mirrored from the official Codex docs and represent
the authoritative source of truth for output format.

## Release flow

1. Bump `version` in `pyproject.toml` and add a section under the new
   version in `CHANGELOG.md`.
2. Commit: `git commit -m "release: vX.Y.Z"`.
3. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. The `Publish to PyPI` workflow (`.github/workflows/publish.yml`) builds
   the wheel + sdist and uploads to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/).

The Trusted Publisher must be configured once on PyPI with:
- Project: `cc-plugin-to-codex`
- Owner / Repo: `ProAlexUSC/cc-plugin-to-codex`
- Workflow: `publish.yml`
- Environment: `pypi`

## Code style

- Follow the rules ruff enforces (configured in `pyproject.toml`).
- Add type annotations to all new functions (`disallow_untyped_defs = true`).
- Prefer pure functions; minimize global state.
- Tests use real filesystem operations via `tmp_path`. Avoid mocking unless
  exercising error paths that cannot be reached otherwise (e.g.,
  `subprocess.run` failures).
