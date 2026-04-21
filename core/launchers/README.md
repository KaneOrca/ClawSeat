# ClawSeat agent launchers

Unified launcher for Claude Code, Codex, and Gemini CLI with iTerm + tmux
integration. Originally lived on `~/Desktop/`; merged into ClawSeat so
every install has a consistent entry point and operators don't have to
keep personal copies in sync.

## Files

| File | Purpose |
|------|---------|
| `agent-launcher.sh` | Main unified launcher — handles tool selection, auth resolution, tmux session creation, iTerm window opening, and runtime isolation (XDG / HOME redirects). |
| `agent-launcher-common.sh` | Shared bash helpers: choice UI (osascript dialogs + fuzzy picker fallback), state/preset storage, directory resolution. |
| `agent-launcher-discover.py` | API-key discovery across env vars / secret files for claude / codex / gemini. |
| `agent-launcher-fuzzy.py` | curses-based fuzzy directory picker + favorites menu (with env-driven roots). |
| `claude.sh` | Thin wrapper → `agent-launcher.sh --tool claude`. |
| `codex.sh` | Thin wrapper → `agent-launcher.sh --tool codex`. |
| `gemini.sh` | Thin wrapper → `agent-launcher.sh --tool gemini`. |

## Invocation

```bash
# Via wrapper (common case)
~/.clawseat/core/launchers/claude.sh --session install-planner-claude --dir ~/.clawseat

# Directly
~/.clawseat/core/launchers/agent-launcher.sh \
    --tool claude \
    --auth oauth_token \
    --session install-builder-1-claude \
    --dir ~/.clawseat

# Headless (build tmux session, skip opening an iTerm window)
~/.clawseat/core/launchers/agent-launcher.sh --tool claude --session X --headless

# Dry-run (print resolved launch config, do not spawn)
~/.clawseat/core/launchers/agent-launcher.sh --tool claude --dry-run
```

`--headless` is important for the ClawSeat install flow: `install_entrypoint.py`
uses it to spawn the ancestor-cc tmux session, then opens one iTerm window
separately via `iterm_panes_driver.py`. This keeps tmux creation and iTerm
window policy independent.

## Configuration (env vars)

The merged launcher is portable — no hard-coded `/Users/...` paths. User-specific
bookmarks are env-driven:

| Env var | Default | Purpose |
|---------|---------|---------|
| `CLAWSEAT_LAUNCHER_ROOTS` | `~/coding:5, ~/Desktop/work:4, ~/Desktop:3, ~/Documents:3` | Directory roots + weights for fuzzy search (`PATH:weight`, comma-separated) |
| `CLAWSEAT_LAUNCHER_FAVORITES` | `~/coding/cartooner, ~/coding/openclaw, ~/Desktop/work, ~/Desktop, ~/Documents, ~` | Favorite directories shown first in the fuzzy picker |
| `AGENT_LAUNCHER_CUSTOM_PRESET_STORE` | `~/.config/clawseat/launcher-custom-presets.json` | Where custom launch presets are saved |
| `LAUNCHER_STATE_STORE` | `~/.config/clawseat/launcher-state.json` | Recent-directory / selection history |
| `AGENT_LAUNCHER_DISCOVER_HOME` | `$HOME` | Alternate home for key discovery (useful for runtime isolation testing) |

## Migration from `~/Desktop/` version

The desktop scripts (`~/Desktop/agent-launcher.command` etc.) continue to work
until you delete them. The clawseat version is authoritative going forward.
To migrate cleanly:

```bash
# Optional: backup the legacy desktop version
tar czf ~/desktop-launcher-backup.tgz ~/Desktop/.agent-launcher-* ~/Desktop/agent-launcher.command

# Replace desktop scripts with thin shims that delegate to clawseat
cat > ~/Desktop/agent-launcher.command <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/.clawseat/core/launchers/agent-launcher.sh" "$@"
SHIM
chmod +x ~/Desktop/agent-launcher.command

# Same pattern for claude-minimax.command / codex.command / gemini.command
# ...
```

Not doing the migration is OK — the legacy desktop store paths
(`~/Desktop/.agent-launcher-{state,custom-presets}.json`) are honored as a
fallback so no state is lost.

## Related

- `core/scripts/iterm_panes_driver.py` — the iTerm Python API driver that
  opens multi-pane monitor windows once seats are running.
- `core/tui/install_wizard.py` — the v0.4 profile wizard that produces the
  project TOML consumed by the launcher.
- `docs/schemas/v0.4-layered-model.md` — the layered-architecture spec that
  motivates one canonical launcher location.
