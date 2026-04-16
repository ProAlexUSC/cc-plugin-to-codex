"""Interactive prompts with TTY detection and strict-mode fallback."""

from __future__ import annotations

import sys


class StrictModeError(RuntimeError):
    """Raised when a required prompt can't be answered in non-interactive mode."""


def is_non_interactive(*, non_interactive_flag: bool, stdin_isatty: bool | None = None) -> bool:
    if non_interactive_flag:
        return True
    if stdin_isatty is None:
        stdin_isatty = sys.stdin.isatty()
    return not stdin_isatty


def prompt_select_plugins(
    *,
    available: list[str],
    preselected: list[str],
    all_plugins: bool,
    strict: bool,
) -> list[str]:
    if all_plugins:
        return list(available)
    if preselected:
        missing = [p for p in preselected if p not in available]
        if missing:
            raise StrictModeError(f"plugins not found in source: {', '.join(missing)}")
        return list(preselected)
    if strict:
        raise StrictModeError(
            "no plugins selected; pass --plugin <name> (repeatable) or --all-plugins"
        )
    # interactive fallback: questionary checkbox
    import questionary

    answer = questionary.checkbox(
        "Select plugins to sync",
        choices=available,
    ).ask()
    if not answer:
        raise StrictModeError("no plugins selected")
    return answer


def prompt_source_kind(*, source: str | None, strict: bool) -> str:
    """Resolve a source spec to something resolve_source() can consume.

    Returns a Git URL or an absolute local path to a CC marketplace root.
    Interactive "Scan local" choice is expanded here: we list every market
    under ~/.claude/plugins/marketplaces/ and let the user pick one, so the
    caller always gets a concrete address.
    """
    if source:
        return source
    if strict:
        raise StrictModeError("source not specified; pass --source <git-url-or-path>")
    import questionary

    from cc_plugin_to_codex.sources import scan_local_marketplaces

    kind = questionary.select(
        "Source type",
        choices=["Git URL", "Local path", "Scan ~/.claude/plugins/marketplaces/"],
    ).ask()
    if kind == "Git URL":
        answer = questionary.text("Git URL").ask()
    elif kind == "Local path":
        answer = questionary.path("Local path").ask()
    elif kind and kind.startswith("Scan "):
        found = scan_local_marketplaces()
        if not found:
            raise StrictModeError(
                "no marketplaces found under ~/.claude/plugins/marketplaces/ (nothing to scan)"
            )
        if len(found) == 1:
            return str(found[0].root)
        label_to_path = {f"{f.root.name}  ({f.root})": str(f.root) for f in found}
        picked = questionary.select("Select marketplace", choices=list(label_to_path.keys())).ask()
        if not picked:
            raise StrictModeError("no marketplace selected")
        return label_to_path[picked]
    else:
        # User hit Ctrl-C / aborted the top-level selector
        raise StrictModeError("source required")
    if not answer:
        raise StrictModeError("source required")
    return answer


def prompt_scope(*, scope: str | None, strict: bool) -> str:
    if scope in ("global", "project"):
        return scope
    if strict:
        raise StrictModeError("scope not specified; pass --scope global|project")
    import questionary

    answer = questionary.select(
        "Target scope",
        choices=["global", "project"],
        default="global",
    ).ask()
    if not answer:
        raise StrictModeError("scope required")
    return answer


def confirm(*, message: str, yes_flag: bool, strict: bool) -> bool:
    if yes_flag or strict:
        return True
    import questionary

    return bool(questionary.confirm(message, default=False).ask())


def prompt_select_bridges(
    *,
    available: list[str],
    strict: bool,
    action: str = "operate on",
) -> list[str]:
    """Let the user pick bridges to act on when no name/--all was given.

    `available` is the list of bridge names already collected from list_bridges()
    across all target scopes. Returns a non-empty subset. In strict mode or when
    the list is empty, raises StrictModeError with a caller-friendly message.
    """
    if not available:
        raise StrictModeError("no bridge plugins installed")
    if strict:
        raise StrictModeError(
            f"must specify a bridge name or --all to {action} (installed: {', '.join(available)})"
        )
    import questionary

    answer = questionary.checkbox(
        f"Select bridges to {action}",
        choices=available,
    ).ask()
    if not answer:
        raise StrictModeError("no bridges selected")
    return answer
