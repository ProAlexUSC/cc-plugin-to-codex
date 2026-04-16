---
name: cc2codex
description: How to use the cc2codex CLI — a tool that bridges Claude Code marketplace plugins into Codex. Trigger when the user asks to "sync / bridge / install a CC plugin into Codex", "list Codex bridges that come from CC", "uninstall a bridge from Codex", or "update a bridge"; when the user mentions cc2codex, plugin-sync, plugin-browse, plugin-list, plugin-update, plugin-uninstall, x-cc-bridge, cc- prefixed Codex plugins; or whenever the user needs to manage Claude-Code-derived bridge plugins under ~/.codex/plugins/. Do NOT use this skill for developing CC plugins themselves or for installing things into Claude Code.
---

# cc2codex

CLI that syncs CC marketplace plugins into Codex. Each source plugin becomes a
`cc-<name>` bridge, CC agent Markdown is converted to Codex TOML, and every
artifact is stamped with an `x-cc-bridge` marker so list / update / uninstall
can manage them in bulk.

## Installation

The package is published on PyPI. Pick one of these invocation styles — the
examples below assume `cc2codex` is on `$PATH`:

1. **`uvx` zero-install** (recommended, always latest):
   ```bash
   uvx --from cc-plugin-to-codex cc2codex --help
   ```

2. **`uv tool install`** (persistent):
   ```bash
   uv tool install cc-plugin-to-codex
   cc2codex --help
   ```

3. **Plain pip**:
   ```bash
   pip install cc-plugin-to-codex
   cc2codex --help
   ```

## 5 commands

| Command | What it does |
|---|---|
| `plugin-browse` | Read-only list of plugins exposed by a source marketplace |
| `plugin-sync` | Install a bridge: copy files + convert agents + update registry |
| `plugin-list` | Show installed bridges (identified by `x-cc-bridge` marker) |
| `plugin-update` | Re-sync from the source recorded in the marker |
| `plugin-uninstall` | Remove a bridge by marker |

## Core concepts

- **Scope**: `global` = `~/.codex/ ~/.agents/`; `project` = `$PWD/.codex/ $PWD/.agents/`.
  `--scope` is required in strict mode.
- **Source**: a Git URL (`git@host:org/repo.git`, `https://…/repo.git`, `ssh://…`,
  `git://…`, or bare `git@host:path`) or a local checkout path that contains
  `.claude-plugin/marketplace.json`. Git sources are cloned into `/tmp` and
  cleaned up afterwards. `--ref` accepts a branch, tag, or commit SHA.
- **`x-cc-bridge` marker**: top-level field in a bridge `plugin.json` plus a
  first-line comment in every bridge agent TOML. Files without the marker are
  user-authored and the tool will never overwrite them unless `--force` is
  passed.
- **Naming**: bridge name is `cc-<source-plugin>`; agent TOML filename is
  `cc_<plugin-snake>_<agent-snake>.toml` (kebab-case → snake_case).

## Typical flows

### Sync one or all plugins (AI-friendly)

```bash
# Specific plugins
cc2codex plugin-sync \
  --source https://github.com/your-org/cc-marketplace.git \
  --plugin ios-dev --plugin base \
  --scope global \
  --non-interactive --yes

# Everything
cc2codex plugin-sync \
  --source /path/to/cc-marketplace \
  --all-plugins --scope global \
  --non-interactive --yes
```

Re-syncing the same source is safe: agents that existed in the old marker but
are no longer present in the source are cleaned up automatically.

> **⚠️ After `plugin-sync` the user must install the bridge inside Codex**
>
> Codex does not hot-reload `~/.agents/plugins/marketplace.json`. Once cc2codex
> has finished writing the files, the user needs to **restart Codex** (or start
> a new session), run `/plugins`, pick the newly added bridge in the "CC
> Bridged Plugins" marketplace, and install it. Until that install step runs,
> Codex will not load the skills and agents. When explaining a successful
> sync, always follow up with this instruction.

### Check state

```bash
cc2codex plugin-list                       # human text
cc2codex plugin-list --scope global --json # machine readable
```

### Update

```bash
cc2codex plugin-update cc-ios-dev --scope global --non-interactive --yes
cc2codex plugin-update --all --non-interactive --yes
```

No need to pass `--source` again — the tool reads it from the marker.

### Uninstall

```bash
cc2codex plugin-uninstall cc-ios-dev --scope global --non-interactive --yes
cc2codex plugin-uninstall --all --scope all --non-interactive --yes
```

Removes the plugin directory + every associated agent TOML + the registry entry.

> **⚠️ Codex has its own cache; uninstall only covers half the story**
>
> cc2codex only removes files it wrote. Codex has **two extra state locations**
> cc2codex cannot touch:
>
> - `~/.codex/plugins/cache/cc-bridged-plugins/<bridge>/<version>/` — Codex
>   copies bridges here when the user runs `/plugins install`, and loads from
>   here at runtime.
> - `~/.codex/config.toml`, section
>   `[plugins."<bridge>@cc-bridged-plugins"] enabled = true` — Codex's own
>   enable state.
>
> As a result, a bridge that was previously installed inside Codex will still
> be loaded from the cache after a cc2codex uninstall. After explaining that
> the uninstall succeeded, also tell the user to run `/plugins` inside Codex
> and uninstall the same bridge there so Codex can clean its own cache +
> config.
>
> Or, manually: `rm -rf ~/.codex/plugins/cache/cc-bridged-plugins/<bridge>`
> and edit `~/.codex/config.toml` to drop the matching
> `[plugins."…"]` section.

## Strict-mode rules (important)

When there is no TTY or any of `--yes` / `--json` / `--non-interactive` is
passed, the command runs in **strict mode**. In strict mode every decision
must be supplied explicitly:

| Missing | Error message |
|---|---|
| `--source` | `source not specified; pass --source <git-url-or-path>` |
| `--plugin` or `--all-plugins` | `no plugins selected; pass --plugin <name> (repeatable) or --all-plugins` |
| `--scope` | `scope not specified; pass --scope global\|project` |
| `uninstall`/`update` without name or `--all` | `must specify a bridge name or --all to X (installed: …)` |

When calling from an AI or a script, pass every flag up front — do not rely on
defaults.

## Interactive mode

In a real TTY, omitting a flag pops a `questionary` selector:

- Source type: Git URL / Local path / Scan `~/.claude/plugins/marketplaces/`
- Plugins: multi-select checkbox
- Scope: global / project
- `uninstall` / `update` bridge target: multi-select checkbox

## Common pitfalls

1. **Non-bridge conflict**: a plugin directory already exists at the target
   path but has no `x-cc-bridge` marker → refused (protects user-authored
   content). Pass `--force` to override.
2. **Source switch conflict**: a bridge with the same name was previously
   synced from source A and now you are pointing at source B → refused. Run
   `plugin-uninstall` first, or pass `--force`.
3. **Plugin name vs bridge name**: `--plugin` takes the **source** name (e.g.
   `ios-dev`), not the bridge name (`cc-ios-dev`). The positional argument of
   `plugin-uninstall` / `plugin-update` takes the **bridge** name.
4. **Registry policy**: each registry entry is written with
   `installation: INSTALLED_BY_DEFAULT` + `authentication: ON_USE`, so Codex
   activates the bridge automatically once installed.
5. **Stale-agent cleanup is safe**: only TOMLs carrying the `x-cc-bridge`
   comment are ever deleted; hand-authored TOMLs are left alone.

---

## Full flag reference

### Shared flags

| Flag | Meaning |
|---|---|
| `--source <url-or-path>` | Git URL (`git@host:org/repo.git`, `https://…/repo.git`) or local path (directory containing `.claude-plugin/marketplace.json`). Omit to select interactively. |
| `--ref <branch\|tag\|sha>` | Ref to check out when `--source` is a Git URL. Default `master`. SHAs go through `fetch + checkout`; everything else uses `clone --branch`. Ignored for local sources. |
| `--scope {global,project}` | Target scope. `global` → `~/.codex/ ~/.agents/`; `project` → `$PWD/.codex/ $PWD/.agents/`. Required in strict mode for `plugin-sync`. |
| `--scope {global,project,all}` | Scope filter for `plugin-list`, `plugin-update`, `plugin-uninstall`. Default `all`. |
| `--plugin <name>` | Repeatable. Takes the source-side plugin name (no `cc-` prefix). Mutually exclusive with `--all-plugins`. |
| `--all-plugins` | Sync every plugin exposed by the source. |
| `--all` | Apply `plugin-update` / `plugin-uninstall` to every bridge in the target scope. |
| `--yes` | Skip confirmation prompts (implies strict). |
| `--non-interactive` | Force strict mode; auto-enabled when stdin is not a TTY. |
| `--force` | Bypass conflict protection (non-bridge overwrite, different source). |
| `--json` | Emit machine-readable JSON on stdout (implies strict). |

### `plugin-browse`

Read-only listing of plugins in a source marketplace. Writes nothing.

```bash
cc2codex plugin-browse --source <url-or-path> [--ref <ref>] [--json]
```

Non-interactive: `--source` is required.

### `plugin-sync`

Core install command. Pipeline:

1. Resolve the source (Git clone into `/tmp`, or read the local path).
2. Read `<source>/.claude-plugin/marketplace.json` to list available plugins.
3. Filter with `--plugin` / `--all-plugins`.
4. For each selected plugin:
   - Pre-convert every `agents/*.md` (fail fast).
   - Check agent TOML conflicts (user-authored → refuse unless `--force`).
   - Stage a sibling directory and copy (blacklist excludes `.claude-plugin/`,
     `.codex-plugin/`, `hooks/`, `commands/`, `agents/`, VCS/build noise).
   - Write `.codex-plugin/plugin.json` including the `x-cc-bridge` marker and
     the final agent list.
   - POSIX atomic rename the staged directory over the old bridge.
   - Write agent TOMLs (`# x-cc-bridge: {…}` comment on line 1).
   - Remove stale agents (in the old marker but not in the new list).
   - Upsert the `marketplace.json` entry
     (`policy.installation = INSTALLED_BY_DEFAULT`).

```bash
cc2codex plugin-sync \
  --source <url-or-path> [--ref <ref>] \
  --scope {global|project} \
  {--plugin <name> [--plugin <name>] … | --all-plugins} \
  [--force] [--yes] [--non-interactive] [--json]
```

Non-interactive: `--source`, `--scope`, and `--plugin|--all-plugins` are all
required.

### `plugin-list`

Scan every plugin directory in the target scope and list the ones that carry
an `x-cc-bridge` marker.

```bash
cc2codex plugin-list [--scope {global|project|all}] [--json]
```

Text mode prints `pluginsDir / agentsDir / registry` paths for each scope
followed by the bridge inventory with agent names. JSON mode groups the same
data by scope.

### `plugin-update`

Use the bridge's `x-cc-bridge.source` + `.ref` to re-resolve the source and
run the sync pipeline. Source arguments are NOT required again.

```bash
cc2codex plugin-update [cc-<name> | --all] \
  [--scope {global|project|all}] \
  [--force] [--yes] [--non-interactive] [--json]
```

- The positional argument is the **bridge** name (with `cc-` prefix).
- `--all` updates every bridge in the target scope.
- In strict mode, a missing name / `--all` triggers an error that lists the
  installed bridges.

### `plugin-uninstall`

Cleanup driven by `x-cc-bridge.agents`. **Only files with the marker are
removed**; user-authored plugins and agents are always safe.

```bash
cc2codex plugin-uninstall [cc-<name> | --all] \
  [--scope {global|project|all}] \
  [--yes] [--non-interactive] [--json]
```

Deletion order:
1. Every agent TOML listed under `x-cc-bridge.agents`.
2. The `scope.plugins_dir/cc-<name>/` directory itself.
3. The entry in `scope.registry` (the `plugins[]` array of `marketplace.json`).

**The `marketplace.json` file itself is never removed**, even when the array
ends up empty (`plugins: []`).

## JSON schemas

### `plugin-browse --json`

```json
{
  "marketplace": {
    "name": "<string>",
    "source": "<string>",
    "sourceKind": "git|local",
    "ref": "<string or null>",
    "commit": "<string>"
  },
  "plugins": [
    {
      "name": "<string>",
      "version": "<string>",
      "description": "<string>",
      "skillCount": 0,
      "agentCount": 0,
      "hasCodexManifest": true
    }
  ]
}
```

### `plugin-sync --json`

```json
{
  "scope": "global|project",
  "synced": [
    {
      "bridgeName": "cc-<name>",
      "bridgeDir": "<absolute path>",
      "agents": ["cc_<plugin>_<agent>", "..."]
    }
  ]
}
```

### `plugin-list --json`

```json
{
  "scopes": {
    "global": {
      "pluginsDir": "<path>",
      "agentsDir": "<path>",
      "registry": "<path>",
      "bridges": [
        {
          "name": "cc-<name>",
          "version": "<string>",
          "sourcePlugin": "<source name>",
          "source": "<url-or-path>",
          "sourceKind": "git|local",
          "ref": "<string or null>",
          "commit": "<sha or 'local'>",
          "marketplace": "<source market name>",
          "syncedAt": "<ISO-8601 UTC>",
          "agents": ["cc_<plugin>_<agent>", "..."]
        }
      ]
    },
    "project": { "...": "same shape" }
  }
}
```

### `plugin-update --json`

```json
{
  "updated": [
    {"bridgeName": "cc-<name>", "commit": "<sha>", "scope": "global|project"}
  ]
}
```

### `plugin-uninstall --json`

```json
{
  "removed": [
    {"bridge": "cc-<name>", "agents": ["cc_<plugin>_<agent>", "..."], "scope": "global|project"}
  ]
}
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Runtime error (bridge not found, unresolved conflict, `SyncConflictError`, …) |
| `2` | Missing / invalid arguments (strict mode, unknown plugin name, …) |

## `x-cc-bridge` marker format

Written at the top level of `<scope.plugins_dir>/cc-<name>/.codex-plugin/plugin.json`:

```json
{
  "x-cc-bridge": {
    "sourcePlugin": "<source name without cc- prefix>",
    "source": "<url or absolute path>",
    "sourceKind": "git|local",
    "ref": "<branch/tag/sha or null>",
    "commit": "<sha or 'local'>",
    "marketplace": "<name from source marketplace.json>",
    "syncedAt": "<ISO-8601 UTC>",
    "tool": "cc-plugin-to-codex/<version>",
    "agents": ["cc_<plugin>_<agent>", "..."]
  }
}
```

First-line comment in each bridge agent TOML:

```toml
# x-cc-bridge: {"sourcePlugin":"<name>","sourceAgent":"<original-name>","bridgePlugin":"cc-<name>","syncedAt":"..."}
name = "cc_<plugin>_<agent>"
description = "..."
developer_instructions = """..."""
```

Detection rules:

- `plugin.json` is a bridge iff it has a top-level `x-cc-bridge` dictionary.
- An agent TOML is a bridge iff its first line matches the regex
  `^# x-cc-bridge: (\{.*\})$`, the JSON payload parses, and the four required
  keys are present.

Anything without a match is treated as user-authored; the tool leaves it
alone. `--force` is the only way to override.
