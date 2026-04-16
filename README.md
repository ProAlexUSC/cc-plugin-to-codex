# cc-plugin-to-codex

[![CI](https://github.com/fangzzzjjj/cc-plugin-to-codex/actions/workflows/ci.yml/badge.svg)](https://github.com/fangzzzjjj/cc-plugin-to-codex/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cc-plugin-to-codex.svg)](https://pypi.org/project/cc-plugin-to-codex/)
[![Python](https://img.shields.io/pypi/pyversions/cc-plugin-to-codex.svg)](https://pypi.org/project/cc-plugin-to-codex/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Bridge [Claude Code](https://docs.claude.com/en/docs/claude-code) marketplace
plugins into [Codex](https://developers.openai.com/codex). Every source plugin
becomes a `cc-<name>` Codex bridge, CC agent Markdown files are converted into
Codex TOML agents, and everything is marked with an `x-cc-bridge` tag so `list`,
`update`, and `uninstall` can cleanly manage them later.

## Features

- **Multi-source**: accept a Git URL or a local marketplace checkout; interactive
  mode can also scan `~/.claude/plugins/marketplaces/` for every local market.
- **Dual scope**: install either globally (`~/.codex/`, `~/.agents/`) or per
  project (`$PWD/.codex/`, `$PWD/.agents/`).
- **Atomic swap**: each plugin is staged in a sibling temp directory and swapped
  in with a POSIX rename, so a crash mid-sync leaves no half-written state.
- **Dual-mode CLI**:
  - TTY: `questionary`-driven selectors for source, plugins, scope, bridges.
  - Non-TTY / `--yes` / `--json` / `--non-interactive`: strict mode — missing
    required flags fail loudly instead of hanging.
- **Safe re-sync**: stale agents removed automatically; switching source on the
  same bridge is refused unless `--force`.
- **Hands-off marker**: user-authored plugins / agents without `x-cc-bridge` are
  never touched.

## Installation

### `uvx` (recommended, zero install)

[`uv`](https://docs.astral.sh/uv/) ships with a one-shot runner:

```bash
uvx --from cc-plugin-to-codex cc2codex --help
```

Every invocation grabs the latest released version from PyPI. Add a shell alias
if you use it often:

```bash
alias cc2codex='uvx --from cc-plugin-to-codex cc2codex'
```

### `uv tool install` (persistent)

```bash
uv tool install cc-plugin-to-codex
cc2codex --help
```

Upgrade later with:

```bash
uv tool upgrade cc-plugin-to-codex
```

### Plain pip

```bash
pip install cc-plugin-to-codex
cc2codex --help
```

## Commands

| Command | Purpose |
|---|---|
| `cc2codex plugin-browse` | List plugins exposed by a source marketplace. Read-only. |
| `cc2codex plugin-sync` | Install bridge plugins (skills + subagents) into Codex. |
| `cc2codex plugin-list` | Show installed bridges and their scope paths. |
| `cc2codex plugin-update` | Re-sync a bridge from the source recorded in its marker. |
| `cc2codex plugin-uninstall` | Remove bridge plugins by `x-cc-bridge` marker. |

Each command supports `--help` for the full flag reference.

## Quick start

Browse a marketplace:

```bash
cc2codex plugin-browse --source https://github.com/your-org/your-cc-marketplace.git
```

Sync specific plugins to the global Codex scope:

```bash
cc2codex plugin-sync \
  --source https://github.com/your-org/your-cc-marketplace.git \
  --plugin ios-dev --plugin base \
  --scope global \
  --yes
```

Sync every plugin to the current project:

```bash
cc2codex plugin-sync \
  --source /path/to/local/cc-marketplace \
  --all-plugins --scope project \
  --yes
```

AI / scripting flow — full JSON output, no prompts:

```bash
cc2codex plugin-sync \
  --source <url> --all-plugins --scope global \
  --non-interactive --json
```

List, update, remove:

```bash
cc2codex plugin-list
cc2codex plugin-update --all --scope global --yes
cc2codex plugin-uninstall cc-ios-dev --scope global --yes
```

> **Codex needs one manual step after `plugin-sync`**
>
> Codex does not hot-reload `~/.agents/plugins/marketplace.json`. After the
> first `plugin-sync`, restart Codex (or open a new session) and run
> `/plugins` to install the bridge from the "CC Bridged Plugins" marketplace.
> Until then Codex will not load the skills and agents.

## How it works

For each selected plugin, `plugin-sync`:

1. Resolves the source (Git clone into `/tmp`, or reads the local path).
2. Copies the plugin directory to `cc-<name>/`, blacklisting CC-only mechanisms
   (`hooks/`, `commands/`, `agents/`, `.claude-plugin/`) and VCS/build noise
   (`__pycache__`, `.git`, `.DS_Store`, …). Skills, scripts, assets, and docs
   survive.
3. Writes `.codex-plugin/plugin.json` with the `x-cc-bridge` marker (source URL,
   ref, commit SHA, synced timestamp, agent list, …).
4. Converts every `agents/*.md` to a `cc_<plugin>_<agent>.toml` under
   `~/.codex/agents/`, prefixing each file with a `# x-cc-bridge: {…}` comment
   so later runs recognise them as tool-generated.
5. Upserts the entry into `marketplace.json` with
   `policy.installation = INSTALLED_BY_DEFAULT`.

Re-syncing the same source compares the old marker's `agents` list with the new
one and unlinks stale bridge agents; hand-authored TOMLs never match the marker
and are kept.

## Development

```bash
git clone https://github.com/fangzzzjjj/cc-plugin-to-codex
cd cc-plugin-to-codex
uv sync --extra dev
uv run pytest -v
```

CI runs the same `pytest` across Python 3.11 / 3.12 / 3.13 on Ubuntu and macOS.

## Releasing

1. Bump `version` in `pyproject.toml` and update `CHANGELOG.md`.
2. Commit and tag: `git tag v0.X.Y && git push origin v0.X.Y`.
3. The `Publish to PyPI` workflow builds the wheel + sdist and uploads them via
   [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/).
   Configure the trusted publisher once on PyPI with `workflow = publish.yml`
   and `environment = pypi`.

## License

[MIT](LICENSE).
