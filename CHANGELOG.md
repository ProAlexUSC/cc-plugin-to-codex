# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-16

### Added

- Initial release.
- `plugin-browse`: list plugins exposed by a Claude Code marketplace (Git URL or local checkout).
- `plugin-sync`: install a bridge plugin into Codex with atomic stage + rename semantics.
- `plugin-list`: show installed bridges across `global` / `project` scopes.
- `plugin-update`: re-sync a bridge from the source recorded in its `x-cc-bridge` marker.
- `plugin-uninstall`: remove bridge plugin directory, associated agent TOMLs, and registry entry.
- Automatic CC agent (`.md` with YAML frontmatter) → Codex agent (`.toml`) conversion.
- Stale agent cleanup on re-sync.
- Dual mode: interactive (`questionary`) + strict (AI/CI friendly, all flags required).
- `--json` output for all commands.
- Conflict protection via `x-cc-bridge` marker — user-authored files never overwritten unless `--force`.
