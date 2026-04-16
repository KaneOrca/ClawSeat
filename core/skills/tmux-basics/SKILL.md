---
name: tmux-basics
description: >
  tmux session control for ClawSeat seats. Covers session naming, essential
  commands (send-keys, capture-pane), ClawSeat script wrappers
  (send-and-verify, check-engineer-status, wait-for-text, detect-prompt-state),
  common pitfalls (paste overflow, Enter swallowed, focus mismatch, TMUX env),
  and self-diagnosis. Loaded by koder and planner for seat communication.
---

# tmux Basics

Every ClawSeat backend seat runs inside a tmux session. This skill gives you
the commands and tools to communicate with those seats.

## Session naming

ClawSeat sessions follow the pattern `<project>-<seat>`:

```
myproject-koder       # frontstage (OpenClaw mode: no tmux, koder IS the agent)
myproject-planner     # planner-dispatcher
myproject-builder-1   # builder
myproject-reviewer-1  # reviewer
myproject-qa-1        # qa
myproject-designer-1  # designer
```

Resolve the canonical name for a seat:

```bash
$CLAWSEAT_ROOT/core/shell-scripts/agentctl.sh session-name <seat> --project <project>
```

## Essential commands

### Capture pane output

```bash
# Last 50 lines
tmux capture-pane -t <session> -p | tail -50

# Last N lines (negative index)
tmux capture-pane -t <session> -p -S -200

# Entire scrollback
tmux capture-pane -t <session> -p -S -
```

### Send text to a session

**Always use ClawSeat's transport wrapper** instead of raw `tmux send-keys`:

```bash
$CLAWSEAT_ROOT/core/shell-scripts/send-and-verify.sh --project <project> <seat> "message"
```

This script:
1. Resolves the canonical session name
2. Sends the text
3. Waits 1 second, then sends Enter
4. Verifies the message was consumed (not stuck in input buffer)
5. Auto-retries Enter if the message is still queued

**Fallback only** (when the wrapper is unavailable):

```bash
tmux send-keys -l -t <session> "text"
sleep 1
tmux send-keys -t <session> Enter
# Then verify: capture pane and check the message is gone from input
```

### Wait for specific output

Poll a pane until a pattern appears:

```bash
$CLAWSEAT_ROOT/core/shell-scripts/wait-for-text.sh \
  -t <session> -p "pattern" -T 60 -i 1
```

Options: `-T` timeout seconds, `-i` poll interval, `-F` fixed string match.

### Check seat status

```bash
# All project seats
$CLAWSEAT_ROOT/core/shell-scripts/check-engineer-status.sh <seat1> <seat2> ...

# Quick prompt state detection (5 states)
$CLAWSEAT_ROOT/core/shell-scripts/detect-prompt-state.sh <session>
# Returns: agent_input | agent_running | shell_confirmation | shell_waiting | focus_mismatch_or_queued | unknown
```

### Session management

```bash
tmux ls                              # list all sessions
tmux list-windows -t <session>       # list windows in a session
tmux list-panes -t <session>         # list panes in a window

# Pane metadata (alive? which command? PID?)
tmux display-message -p -t <session> \
  '#{pane_current_command} | dead=#{pane_dead} | pid=#{pane_pid}'
```

### Special keys

```bash
tmux send-keys -t <session> Enter     # Enter
tmux send-keys -t <session> Escape    # Escape
tmux send-keys -t <session> C-c       # Ctrl+C
tmux send-keys -t <session> C-d       # Ctrl+D (EOF)
tmux send-keys -t <session> C-z       # Ctrl+Z (suspend)
```

## Common pitfalls

### 1. Paste buffer overflow

Long text sent via `send-keys -l` can overwhelm a TUI's input buffer.
For messages over ~500 characters, split into chunks or write to a file
and instruct the target to read it.

### 2. Enter swallowed by slow TUI

Codex and Gemini CLI can be slow to process input. If `Enter` arrives
before the TUI has finished accepting the text, it gets swallowed.

Fix: use `send-and-verify.sh` (auto-retries), or manually add `sleep 1`
between text and Enter.

### 3. Text lands in wrong layer

When a seat is running a subprocess (e.g. shell command inside Claude Code),
`send-keys` may go to the outer TUI instead of the inner shell, or vice versa.
Check `detect-prompt-state.sh` output before sending.

### 4. Queued input ≠ delivered input

If the pane shows `Queued:` after your send, the outer TUI accepted the text
but the inner process did not receive it. This is a **focus mismatch**, not
a success. Do not claim the message was delivered.

### 5. TMUX env variable interference

When running tmux commands from inside a tmux session, the `$TMUX` variable
can cause `tmux` to refuse to operate. ClawSeat scripts use `env -u TMUX`
to work around this. If calling tmux directly, do the same:

```bash
env -u TMUX tmux capture-pane -t <session> -p
```

## Self-diagnosis

If you suspect a seat is stuck or unresponsive:

1. Check what process is running:
   ```bash
   tmux display-message -p -t <session> '#{pane_current_command}'
   ```
2. Check if pane is dead:
   ```bash
   tmux display-message -p -t <session> '#{pane_dead}'
   ```
3. Capture recent output:
   ```bash
   tmux capture-pane -t <session> -p | tail -20
   ```

If the seat cannot self-recover, write a DELIVERY.md with status `blocked`
and diagnostic output, so planner or koder can investigate.
