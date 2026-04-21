# Gotchas for install-assisting agents

> **Audience**: any external agent (ChatGPT / Claude Web / Claude Code /
> Codex / Gemini etc.) helping a user install ClawSeat.
> **Why this file exists**: the install flow has non-obvious timings and
> environment assumptions. A fresh agent without this context will
> routinely misdiagnose and try to "fix" things that were already working.

## 1. tmux send-keys / paste can take 30 seconds

When ClawSeat (or its launcher) types a command into a tmux session via
`tmux send-keys`, or when you yourself are piping text into a tmux pane,
the command **may take up to 30 seconds to appear on screen and execute**.

Reasons (any combination):

- Inner Claude / Codex / Gemini TUI is doing a mid-frame redraw and
  swallows keystrokes until it idles.
- macOS IME (Chinese/Japanese/Korean input method) intercepts a keystroke
  and buffers it waiting for composition.
- The shell inside the pane is still sourcing `.zshrc` / `.bashrc` and
  running `pyenv rehash` (which can hold a filesystem lock ~60s on first
  install — see §2).
- tmux's own command queue is backed up if many `send-keys` calls fire
  in quick succession.

**What NOT to do when a command "looks stuck":**

- ❌ Re-send the command (you'll get double-execution once the buffer flushes).
- ❌ Kill the pane / tmux session (destroys state).
- ❌ Assume the launcher hung and restart it from scratch.
- ❌ `pkill claude` or equivalent. The process is fine.

**What TO do:**

- ✅ Wait at least 30 seconds. Set a timer.
- ✅ If still frozen after 60 seconds, capture the pane once with
  `tmux capture-pane -t '=<session-name>' -p` to see what's on screen.
- ✅ Report the capture to the user. Do not auto-recover.

Tests in `tests/test_iterm_panes_driver.py` cover the TUI driver side;
the 30-second window is observed empirically and documented here so that
install agents treat it as normal latency.

## 2. pyenv rehash lock on first install

If the user has `pyenv` installed, opening 6 shells simultaneously (as
ClawSeat's install_entrypoint does when launching 6 seats in parallel)
will trigger a **pyenv rehash race condition**:

```
pyenv: cannot rehash: couldn't acquire lock /Users/<user>/.pyenv/shims/.pyenv-shim for 60 seconds.
```

This is a `pyenv` issue, not a ClawSeat bug. The shells eventually all
finish rehashing and the launcher proceeds. **Tell the user this is
expected during first-install and will not recur on subsequent boots.**

If the user wants to eliminate the message entirely, they can:
```bash
pyenv rehash      # run ONCE manually before ClawSeat install
```

## 3. iTerm2 Python API must be enabled before install

ClawSeat's multi-pane monitor window driver
(`core/scripts/iterm_panes_driver.py`) requires iTerm2's Python API to
be enabled **and** iTerm2 to be running.

Check before launching install_entrypoint:

```bash
defaults read com.googlecode.iterm2 EnableAPIServer   # must be 1
pgrep -x iTerm2                                       # must return a PID
ls ~/Library/Application\ Support/iTerm2/private/socket  # must exist
```

If any of these fail, set + launch:

```bash
defaults write com.googlecode.iterm2 EnableAPIServer -bool true
open -a iTerm                                         # must be after writing defaults
```

If you skip this, the driver returns
`{"status": "error", "reason": "..."}` and install_entrypoint halts at
the monitor-window step. The tmux seats are still alive — just not
visible in iTerm yet. Recovery is to enable the API and re-run only the
driver (not the wizard).

## 4. iTerm2 Python module

The driver imports `iterm2` from user-site packages. Confirm:

```bash
python3 -c "import iterm2; print(iterm2.__file__)"
```

If missing:

```bash
pip3 install --user --break-system-packages iterm2
```

The `--break-system-packages` flag is required on macOS Homebrew Python
(PEP 668). It affects ONLY the user-site directory (`~/Library/Python/<ver>/`),
not the system / Homebrew Python installation.

## 5. Claude Code onboarding in isolated HOME

When ClawSeat launches a claude seat with API auth mode, it isolates
`HOME` to a per-seat runtime directory. If the isolated HOME has no
`~/.claude.json`, Claude Code shows the welcome + auth onboarding even
though API keys are live in the environment.

`core/launchers/agent-launcher.sh` handles this via `prepare_claude_home`
(added 2026-04-22) which symlinks the real user's `~/.claude.json`
into the isolated HOME. If an install agent sees the onboarding page
when API-mode is supposed to skip it, check:

```bash
ls -la ~/.agents/runtime/identities/claude/*/seat-*/home/.claude.json
```

The link must exist and resolve to `$HOME/.claude.json`. If it's missing,
your launcher is out of date — re-sync `core/launchers/`.

## 6. Don't poll / tail running launchers

When you invoke `agent-launcher.sh` interactively (no `--accept-defaults`),
it pops AppleScript dialogs for tool / auth / directory selection. These
dialogs are asynchronous from your agent's vantage point.

- ❌ Do not run `ps -p <PID>` in a tight loop expecting the launcher to exit quickly.
- ❌ Do not `pkill` the launcher if the user hasn't responded to a dialog.
- ❌ Do not background the launcher with `&` and then poll for tmux changes
  — AppleScript dialogs from a backgrounded bash process often fail silently.

Correct pattern:

```bash
# Option A: foreground the launcher and block until user completes dialogs
~/.clawseat/core/launchers/agent-launcher.sh

# Option B: drive launcher non-interactively with all args
~/.clawseat/core/launchers/agent-launcher.sh \
  --tool claude --auth oauth_token \
  --dir ~/.clawseat --session myproj-planner-claude \
  --headless
```

Install agents should prefer Option B — pass explicit arguments from the
wizard output so no user dialog is needed.

## 7. tmux kill-session NEVER with empty target

`tmux kill-session -t ""` kills EVERY session on the server. A stray
empty variable can destroy all the user's agent sessions.

Always gate:

```bash
if [[ -n "$SESSION" ]]; then
    tmux kill-session -t "=$SESSION"
fi
```

Use `=` prefix for exact match — without it, tmux does prefix-match which
can delete the wrong session (e.g., `kill-session -t cartooner` kills
the first session whose name starts with `cartooner-`).

## 8. Don't treat absence of process as absence of work

`ps aux | grep <seat>` returning zero rows doesn't mean the seat is
dead. The AI CLI may be:

- In the middle of a long-running subagent call (no visible subprocess).
- Idle at its prompt waiting for the next dispatch.
- Paused in a tmux background (check `tmux list-clients -t =<session>`).

Use `tmux has-session -t '=<name>'` as the single source of truth for
"is this seat alive?". Its exit code is authoritative.

---

## Quick diagnostic checklist for install agents

When something "seems wrong" during install, run these in order:

```bash
# 1. ClawSeat layout present
ls ~/.clawseat/core/launchers/agent-launcher.sh

# 2. iTerm API accessible
pgrep -x iTerm2 && defaults read com.googlecode.iterm2 EnableAPIServer

# 3. Python deps
python3 -c "import iterm2"

# 4. tmux version
tmux -V

# 5. No orphan sessions from a prior failed install
tmux list-sessions 2>/dev/null

# 6. Profile validator works
python3 -c "import sys; sys.path.insert(0, '$HOME/.clawseat/core/lib'); from profile_validator import LEGAL_SEATS; print(LEGAL_SEATS)"
```

If any of 1-4 fails, stop. Do NOT try to auto-remediate. Report the
specific failure and its output to the user; let them fix it manually
and re-run the install.
