"""Typer CLI entry point."""

from __future__ import annotations

import typer

from cc_plugin_to_codex import __version__, log
from cc_plugin_to_codex.interactive import (
    StrictModeError,
    is_non_interactive,
    prompt_scope,
    prompt_select_bridges,
    prompt_select_plugins,
    prompt_source_kind,
)
from cc_plugin_to_codex.marketplace import read_source_marketplace
from cc_plugin_to_codex.scopes import Scope, resolve_scope
from cc_plugin_to_codex.sources import cleanup_source, resolve_source
from cc_plugin_to_codex.sync import (
    SyncConflictError,
    list_bridges,
    sync_one,
    uninstall_bridge,
)

app = typer.Typer(
    name="cc2codex",
    help=(
        "Bridge Claude Code marketplace plugins to Codex. Reads a CC marketplace, "
        "copies each plugin's skills/scripts/assets into the Codex plugin directory "
        "(prefixed with cc-<name>), converts CC agents to Codex TOML, and writes a "
        ".agents/plugins/marketplace.json registry. "
        "Typical flow: plugin-browse to inspect, plugin-sync to install, "
        "plugin-list/update/uninstall to manage."
    ),
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"cc2codex {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None: ...


# Shared option descriptions reused across commands for consistent wording.
_HELP_SOURCE = (
    "Marketplace source. Supported:\n"
    "  - Git URL: git@host:org/repo.git or https://.../repo.git (cloned into /tmp)\n"
    "  - Local path: absolute or ~/ path pointing at a CC marketplace checkout"
    " (must contain .claude-plugin/marketplace.json).\n"
    "If omitted, enters interactive selection (Git URL / local path / scan "
    "~/.claude/plugins/marketplaces/)."
)
_HELP_REF = (
    "Ref to check out when --source is a Git URL. Accepts branch, tag, or commit SHA "
    "(SHAs are handled via fetch+checkout). Ignored for local-path sources."
)
_HELP_SCOPE_GP = (
    "Install scope. 'global' writes to ~/.codex/ and ~/.agents/; "
    "'project' writes to $PWD/.codex/ and $PWD/.agents/. "
    "In a TTY, omitting this opens a picker; in non-interactive/strict mode "
    "it must be passed explicitly or the command errors out."
)
_HELP_SCOPE_ALL = "Scope to act on. 'global' = ~/.codex, 'project' = $PWD/.codex, 'all' = both."
_HELP_PLUGIN = (
    "Plugin name to sync; repeatable (e.g. --plugin ios-dev --plugin base). "
    "Use the source plugin's original name, without the cc- prefix. "
    "Mutually exclusive with --all-plugins."
)
_HELP_ALL_PLUGINS = "Sync every plugin in the source marketplace."
_HELP_YES = (
    "Skip all confirmation prompts. Implies --non-interactive (missing interactive "
    "options raise a strict-mode error instead of opening a questionary prompt)."
)
_HELP_NON_INTERACTIVE = (
    "Force non-interactive mode: missing required options exit with an error instead "
    "of opening a questionary prompt. Enabled automatically when stdin is not a TTY "
    "(AI/CI invocations), so it usually does not need to be passed explicitly."
)
_HELP_FORCE = (
    "Force-overwrite conflicts that would otherwise abort: existing non-bridge plugin "
    "directories, user-authored agent TOML files, and existing bridges from a different "
    "source. Use with care; may overwrite hand-written files."
)
_HELP_JSON = (
    "Emit machine-readable JSON to stdout (suppresses human-readable logs). "
    "Implies --non-interactive."
)

# Module-level singletons for typer.Option defaults that would otherwise trigger
# ruff B008 (function call in argument default). Typer's contract allows these to
# be shared across commands.
_PLUGIN_OPTION = typer.Option([], "--plugin", help=_HELP_PLUGIN)


@app.command("plugin-browse")
def plugin_browse(
    source: str | None = typer.Option(None, "--source", help=_HELP_SOURCE),
    ref: str = typer.Option("master", "--ref", help=_HELP_REF),
    non_interactive: bool = typer.Option(False, "--non-interactive", help=_HELP_NON_INTERACTIVE),
    json_output: bool = typer.Option(False, "--json", help=_HELP_JSON),
) -> None:
    """List every installable plugin in the source marketplace without installing anything.

    Read-only. Git sources are cloned into /tmp (cleaned up on exit); local paths are
    read in place. Run this before installing to see what the marketplace offers.

    Examples:
      cc2codex plugin-browse --source /path/to/cc-marketplace
      cc2codex plugin-browse --source git@github.com:org/mk.git --ref v1.2
      cc2codex plugin-browse --source <url> --json
    """
    log.set_json_mode(json_output)
    strict = is_non_interactive(non_interactive_flag=non_interactive or json_output)
    try:
        src_val = prompt_source_kind(source=source, strict=strict)
    except StrictModeError as e:
        log.error(str(e))
        raise typer.Exit(code=2) from e
    resolved = resolve_source(src_val, ref=ref)
    try:
        mp = read_source_marketplace(resolved.root)
        if json_output:
            log.emit_json(
                {
                    "marketplace": {
                        "name": mp.name,
                        "source": resolved.source,
                        "sourceKind": resolved.source_kind,
                        "ref": resolved.ref,
                        "commit": resolved.commit,
                    },
                    "plugins": [
                        {
                            "name": p.name,
                            "version": p.version,
                            "description": p.description,
                            "skillCount": p.skill_count,
                            "agentCount": p.agent_count,
                            "hasCodexManifest": p.has_codex_manifest,
                        }
                        for p in mp.plugins
                    ],
                }
            )
        else:
            log.info(
                f"[bold]Marketplace:[/bold] {mp.name} ({resolved.source} @ {resolved.ref or 'local'})"
            )
            log.info("")
            for p in mp.plugins:
                log.info(
                    f"  {p.name:20} v{p.version:8} {p.description} "
                    f"(skills×{p.skill_count}, agents×{p.agent_count})"
                )
            log.info("")
            log.info(f"  Total: {len(mp.plugins)} plugins")
    finally:
        cleanup_source(resolved)


@app.command("plugin-sync")
def plugin_sync(
    source: str | None = typer.Option(None, "--source", help=_HELP_SOURCE),
    ref: str = typer.Option("master", "--ref", help=_HELP_REF),
    scope: str | None = typer.Option(None, "--scope", help=_HELP_SCOPE_GP),
    plugin: list[str] = _PLUGIN_OPTION,
    all_plugins: bool = typer.Option(False, "--all-plugins", help=_HELP_ALL_PLUGINS),
    yes: bool = typer.Option(False, "--yes", help=_HELP_YES),
    non_interactive: bool = typer.Option(False, "--non-interactive", help=_HELP_NON_INTERACTIVE),
    force: bool = typer.Option(False, "--force", help=_HELP_FORCE),
    json_output: bool = typer.Option(False, "--json", help=_HELP_JSON),
) -> None:
    """Install bridged plugins from a CC marketplace into Codex.

    For each selected plugin, cc2codex will:
      1. Copy the plugin directory (skills, scripts, assets, docs, etc. -- excluding
         CC-only hooks/commands/agents and VCS noise) into cc-<name>/ under the target
         scope.
      2. Generate a Codex-format .codex-plugin/plugin.json with an injected x-cc-bridge
         marker (recording source, ref, commit, and agent list).
      3. Convert each agents/*.md to Codex TOML and write it into the scope's agents
         directory (named cc_<plugin>_<agent>.toml, snake_case).
      4. Upsert the bridge entry in the scope's marketplace.json with
         policy.installation = INSTALLED_BY_DEFAULT.

    Re-syncing from the same source is safe: agents present in the old marker but no
    longer in the new source are cleaned up. Switching to a different source is refused
    unless --force is passed.

    Examples (local source):
      cc2codex plugin-sync --source ~/cc-marketplace --plugin ios-dev --scope global --yes
      cc2codex plugin-sync --source ./cc-marketplace --all-plugins --scope project --yes

    Examples (Git source):
      cc2codex plugin-sync --source git@github.com:org/mk.git --plugin base --yes
      cc2codex plugin-sync --source <url> --ref feature/xyz --all-plugins --yes

    AI/CI usage (--non-interactive is auto-enabled when stdin is not a TTY):
      cc2codex plugin-sync --source <url> --all-plugins --json
    """
    log.set_json_mode(json_output)
    strict = is_non_interactive(non_interactive_flag=non_interactive or json_output or yes)

    try:
        src_val = prompt_source_kind(source=source, strict=strict)
    except StrictModeError as e:
        log.error(str(e))
        raise typer.Exit(code=2) from e

    resolved = resolve_source(src_val, ref=ref)
    try:
        mp = read_source_marketplace(resolved.root)
        try:
            selected_names = prompt_select_plugins(
                available=[p.name for p in mp.plugins],
                preselected=plugin,
                all_plugins=all_plugins,
                strict=strict,
            )
        except StrictModeError as e:
            log.error(str(e))
            raise typer.Exit(code=2) from e

        try:
            resolved_scope = resolve_scope(prompt_scope(scope=scope, strict=strict))
        except StrictModeError as e:
            log.error(str(e))
            raise typer.Exit(code=2) from e
        resolved_scope.ensure_dirs()

        info_by_name = {p.name: p for p in mp.plugins}
        synced_items: list[dict] = []
        for name in selected_names:
            info = info_by_name[name]
            try:
                result = sync_one(
                    info=info,
                    marketplace_name=mp.name,
                    source=resolved.source,
                    source_kind=resolved.source_kind,
                    ref=resolved.ref,
                    commit=resolved.commit,
                    scope=resolved_scope,
                    force=force,
                )
            except SyncConflictError as e:
                log.error(str(e))
                raise typer.Exit(code=1) from e
            synced_items.append(
                {
                    "bridgeName": result.bridge_name,
                    "bridgeDir": str(result.bridge_dir),
                    "agents": result.agents,
                }
            )
            log.success(f"{result.bridge_name} → {result.bridge_dir}")
            if result.agents:
                log.info(f"   agents: {', '.join(result.agents)}")

        if json_output:
            log.emit_json({"scope": resolved_scope.name, "synced": synced_items})
        else:
            log.info("")
            log.success(f"Done. Registry: {resolved_scope.registry}")
            log.info("")
            log.info("[bold yellow]Next steps (required):[/bold yellow]")
            log.info("  1. Restart Codex or open a new session")
            log.info("  2. Run [bold]/plugins[/bold] in Codex to open the plugin browser")
            log.info("  3. Install the new bridges from the 'CC Bridged Plugins' marketplace")
            log.info("  (Codex does not currently auto-reload marketplace.json changes)")
    finally:
        cleanup_source(resolved)


@app.command("plugin-list")
def plugin_list(
    scope: str = typer.Option("all", "--scope", help=_HELP_SCOPE_ALL),
    json_output: bool = typer.Option(False, "--json", help=_HELP_JSON),
) -> None:
    """List installed bridge plugins and their scope paths.

    Only entries carrying the x-cc-bridge marker are shown; user-authored plugins in
    the same directory are intentionally ignored. Each scope prints its plugins, agents,
    and registry paths so you can cross-check file locations.

    Examples:
      cc2codex plugin-list                    # List both global and project scopes
      cc2codex plugin-list --scope global
      cc2codex plugin-list --json             # For AI / script consumption
    """
    log.set_json_mode(json_output)
    scope_names = ["global", "project"] if scope == "all" else [scope]

    result: dict = {"scopes": {}}
    for sname in scope_names:
        s = resolve_scope(sname)
        result["scopes"][sname] = {
            "pluginsDir": str(s.plugins_dir),
            "agentsDir": str(s.agents_dir),
            "registry": str(s.registry),
            "bridges": list_bridges(s),
        }

    if json_output:
        log.emit_json(result)
        return

    for sname, info in result["scopes"].items():
        log.info(f"[bold]{sname.capitalize()} scope[/bold]")
        log.info(f"  plugins:  {info['pluginsDir']}")
        log.info(f"  agents:   {info['agentsDir']}")
        log.info(f"  registry: {info['registry']}")
        log.info("")
        if not info["bridges"]:
            log.info("  (empty)")
        for b in info["bridges"]:
            log.info(
                f"  {b['name']}  v{b['version']}  synced {b['syncedAt']}  "
                f"from {b['marketplace']} @ {b['commit'][:7]}"
            )
            if b["agents"]:
                log.info(f"    └─ agents: {', '.join(b['agents'])}")
        log.info("")


@app.command("plugin-uninstall")
def plugin_uninstall(
    name: str | None = typer.Argument(
        None,
        help=(
            "Bridge name to uninstall (with cc- prefix, e.g. 'cc-ios-dev'). "
            "Optional when --all is passed."
        ),
    ),
    all_bridges: bool = typer.Option(
        False,
        "--all",
        help="Uninstall every bridge plugin in the target scope. Requires confirmation "
        "unless --yes is passed.",
    ),
    scope: str = typer.Option("all", "--scope", help=_HELP_SCOPE_ALL),
    yes: bool = typer.Option(False, "--yes", help=_HELP_YES),
    non_interactive: bool = typer.Option(False, "--non-interactive", help=_HELP_NON_INTERACTIVE),
    json_output: bool = typer.Option(False, "--json", help=_HELP_JSON),
) -> None:
    """Uninstall bridge plugins previously installed by cc2codex.

    For each bridge this removes:
      - The plugin directory under scope.plugins_dir
      - Every agent TOML recorded in the marker's x-cc-bridge.agents list
      - The matching bridge entry from scope.registry (marketplace.json)

    User-authored plugins (those without an x-cc-bridge marker) are never touched.

    Examples:
      cc2codex plugin-uninstall cc-ios-dev --yes
      cc2codex plugin-uninstall --all --scope global --yes
    """
    log.set_json_mode(json_output)
    strict = is_non_interactive(non_interactive_flag=non_interactive or json_output or yes)
    scope_names = ["global", "project"] if scope == "all" else [scope]

    # Snapshot bridges per scope so we can both collect targets and drive the picker
    scope_bridges: list[tuple[Scope, list[dict]]] = []
    for sname in scope_names:
        s = resolve_scope(sname)
        scope_bridges.append((s, list_bridges(s)))

    targets: list[tuple[Scope, str]] = []
    if all_bridges:
        for s, bridges in scope_bridges:
            for b in bridges:
                targets.append((s, b["name"]))
    elif name is not None:
        for s, bridges in scope_bridges:
            if any(b["name"] == name for b in bridges):
                targets.append((s, name))
    else:
        # Interactive: let the user pick from everything we found
        available = [b["name"] for _, bridges in scope_bridges for b in bridges]
        try:
            picked = prompt_select_bridges(available=available, strict=strict, action="uninstall")
        except StrictModeError as e:
            log.error(str(e))
            raise typer.Exit(code=2) from e
        picked_set = set(picked)
        for s, bridges in scope_bridges:
            for b in bridges:
                if b["name"] in picked_set:
                    targets.append((s, b["name"]))

    if not targets:
        if name is not None:
            log.error(f"bridge plugin '{name}' not found")
        else:
            log.error("no bridge plugins installed")
        raise typer.Exit(code=1)

    removed: list[dict] = []
    for s, bridge_name in targets:
        try:
            info = uninstall_bridge(bridge_name=bridge_name, scope=s)
        except (FileNotFoundError, ValueError) as e:
            log.error(str(e))
            raise typer.Exit(code=1) from e
        info["scope"] = s.name
        removed.append(info)
        log.success(f"Uninstalled {bridge_name} ({s.name})")
        for a in info["agents"]:
            log.info(f"  - removed agent {a}")

    if json_output:
        log.emit_json({"removed": removed})
    else:
        log.info("")
        log.info("[bold yellow]Next steps (required):[/bold yellow]")
        log.info(
            "  If the uninstalled bridges were previously installed inside Codex, "
            "Codex's enabled state and cache still remain."
        )
        log.info(
            "  Open Codex, run [bold]/plugins[/bold], and uninstall each bridge once there, "
            "or clean up manually:"
        )
        log.info("    rm -rf ~/.codex/plugins/cache/cc-bridged-plugins/<bridge-name>")
        log.info(
            '    # Edit ~/.codex/config.toml and remove [plugins."<bridge-name>@cc-bridged-plugins"]'
        )


@app.command("plugin-update")
def plugin_update(
    name: str | None = typer.Argument(
        None,
        help=(
            "Bridge name to update (with cc- prefix, e.g. 'cc-ios-dev'). "
            "Optional when --all is passed."
        ),
    ),
    all_bridges: bool = typer.Option(
        False,
        "--all",
        help="Update every installed bridge in the target scope.",
    ),
    scope: str = typer.Option("all", "--scope", help=_HELP_SCOPE_ALL),
    force: bool = typer.Option(False, "--force", help=_HELP_FORCE),
    yes: bool = typer.Option(False, "--yes", help=_HELP_YES),
    non_interactive: bool = typer.Option(False, "--non-interactive", help=_HELP_NON_INTERACTIVE),
    json_output: bool = typer.Option(False, "--json", help=_HELP_JSON),
) -> None:
    """Re-sync (upgrade) bridges using the source recorded in each marker.

    Reads each bridge's x-cc-bridge marker to recover the original source URL/path and
    ref, re-resolves the source (Git clone or local read), and runs the same pipeline
    as plugin-sync. Unlike plugin-sync, you do not need to remember the original source
    arguments.

    Examples:
      cc2codex plugin-update cc-ios-dev --yes
      cc2codex plugin-update --all --scope global --yes
      cc2codex plugin-update --all --force                 # Override stale conflicts
    """
    log.set_json_mode(json_output)
    strict = is_non_interactive(non_interactive_flag=non_interactive or json_output or yes)
    scope_names = ["global", "project"] if scope == "all" else [scope]

    scope_bridges: list[tuple[Scope, list[dict]]] = []
    for sname in scope_names:
        s = resolve_scope(sname)
        scope_bridges.append((s, list_bridges(s)))

    targets: list[tuple[Scope, dict]] = []
    if all_bridges:
        for s, bridges in scope_bridges:
            for b in bridges:
                targets.append((s, b))
    elif name is not None:
        for s, bridges in scope_bridges:
            for b in bridges:
                if b["name"] == name:
                    targets.append((s, b))
    else:
        available = [b["name"] for _, bridges in scope_bridges for b in bridges]
        try:
            picked = prompt_select_bridges(available=available, strict=strict, action="update")
        except StrictModeError as e:
            log.error(str(e))
            raise typer.Exit(code=2) from e
        picked_set = set(picked)
        for s, bridges in scope_bridges:
            for b in bridges:
                if b["name"] in picked_set:
                    targets.append((s, b))

    if not targets:
        if name is not None:
            log.error(f"bridge plugin '{name}' not found")
        else:
            log.error("no bridge plugins installed")
        raise typer.Exit(code=1)

    updated: list[dict] = []
    for s, b in targets:
        resolved = resolve_source(b["source"], ref=b.get("ref") or "master")
        try:
            mp = read_source_marketplace(resolved.root)
            info = next((p for p in mp.plugins if p.name == b["sourcePlugin"]), None)
            if info is None:
                log.error(f"source no longer contains plugin {b['name']}")
                raise typer.Exit(code=1)
            result = sync_one(
                info=info,
                marketplace_name=mp.name,
                source=resolved.source,
                source_kind=resolved.source_kind,
                ref=resolved.ref,
                commit=resolved.commit,
                scope=s,
                force=force,
            )
            updated.append(
                {"bridgeName": result.bridge_name, "commit": resolved.commit, "scope": s.name}
            )
            log.success(f"Updated {result.bridge_name} ({s.name}) → {resolved.commit[:7]}")
        finally:
            cleanup_source(resolved)

    if json_output:
        log.emit_json({"updated": updated})
    else:
        log.info("")
        log.info("[bold yellow]Next steps (required):[/bold yellow]")
        log.info(
            "  Restart Codex, run [bold]/plugins[/bold], and re-install each bridge "
            "so Codex picks up the latest files."
        )


if __name__ == "__main__":
    app()
