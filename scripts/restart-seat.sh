#!/usr/bin/env bash
# restart-seat.sh — kill and re-launch a single project seat's tmux session.
#
# Why this exists: `agent_admin.py session start-engineer` requires a
# CLAWSEAT_ENGINEER_PROFILE with dispatch_authority. Most project profiles
# don't grant this to any seat, so operators have no convenient way to
# restart a single dead seat — they have to hand-write the tmux + launcher
# invocation. This script does the wrapping.
#
# Usage:
#   scripts/restart-seat.sh <project> <seat> [--auth <mode>] [--no-window]
#
# Examples:
#   scripts/restart-seat.sh cartooner-front memory
#   scripts/restart-seat.sh cartooner-front memory --auth chatgpt
#   scripts/restart-seat.sh install reviewer --no-window
#
# What it does:
#   1. Reads (tool, auth_mode, workspace) from `agent_admin session
#      effective-launch <project> <seat>`.
#   2. Kills the existing tmux session for that seat if alive.
#   3. Launches a new tmux session via core/launchers/agent-launcher.sh
#      with --headless (which re-execs with --exec-agent inside tmux).
#   4. Unless --no-window, asks agent_admin to refresh the project grid
#      so any orphaned iTerm pane re-attaches to the fresh session.

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: scripts/restart-seat.sh <project> <seat> [--auth <mode>] [--no-window]

Options:
  --auth <mode>   Override the engineer profile's default auth mode
                  (e.g. chatgpt to access global ~/.codex session history).
  --no-window     Skip iTerm grid refresh; only restart the tmux session.
  -h, --help      Show this help.
EOF
  exit "${1:-1}"
}

PROJECT=""
SEAT=""
AUTH_OVERRIDE=""
NO_WINDOW=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --auth)
      [[ $# -ge 2 ]] || { echo "error: --auth requires a value" >&2; usage 2; }
      AUTH_OVERRIDE="$2"; shift 2 ;;
    --no-window) NO_WINDOW=1; shift ;;
    --) shift; break ;;
    -*)
      echo "error: unknown flag: $1" >&2; usage 2 ;;
    *)
      if [[ -z "$PROJECT" ]]; then PROJECT="$1"
      elif [[ -z "$SEAT" ]]; then SEAT="$1"
      else echo "error: unexpected positional argument: $1" >&2; usage 2
      fi
      shift ;;
  esac
done

[[ -n "$PROJECT" && -n "$SEAT" ]] || usage 2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENT_ADMIN="$REPO_ROOT/core/scripts/agent_admin.py"
LAUNCHER="$REPO_ROOT/core/launchers/agent-launcher.sh"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TMUX_BIN="${TMUX_BIN:-tmux}"

command -v "$TMUX_BIN" >/dev/null 2>&1 || {
  echo "error: tmux not found in PATH (set TMUX_BIN to override)" >&2
  exit 3
}

# Read effective launch config — single source of truth for tool/auth/workspace.
if ! launch_out="$("$PYTHON_BIN" "$AGENT_ADMIN" session effective-launch --project "$PROJECT" "$SEAT" 2>&1)"; then
  echo "error: agent_admin effective-launch failed for $PROJECT/$SEAT:" >&2
  printf '%s\n' "$launch_out" >&2
  exit 1
fi

extract() {
  printf '%s\n' "$launch_out" | awk -v key="$1" '$1 == key && $2 == "=" { sub(/^[^=]*= /, ""); print; exit }'
}

TOOL="$(extract tool)"
AUTH_MODE="$(extract auth_mode)"
PROVIDER="$(extract provider)"
WORKSPACE="$(extract workspace)"

[[ -n "$AUTH_OVERRIDE" ]] && AUTH_MODE="$AUTH_OVERRIDE"

if [[ -z "$TOOL" || -z "$AUTH_MODE" || -z "$WORKSPACE" ]]; then
  echo "error: incomplete launch config from agent_admin:" >&2
  printf '%s\n' "$launch_out" >&2
  exit 1
fi

SESSION_NAME="${PROJECT}-${SEAT}-${TOOL}"
LAUNCHER_AUTH="$AUTH_MODE"
if [[ -z "$AUTH_OVERRIDE" ]]; then
  case "$TOOL:$AUTH_MODE:$PROVIDER" in
    claude:api:minimax) LAUNCHER_AUTH="minimax" ;;
    claude:api:deepseek) LAUNCHER_AUTH="deepseek" ;;
    claude:api:xcode-best) LAUNCHER_AUTH="xcode" ;;
    claude:api:anthropic-console) LAUNCHER_AUTH="anthropic-console" ;;
    codex:api:xcode-best) LAUNCHER_AUTH="xcode" ;;
    codex:oauth:openai) LAUNCHER_AUTH="chatgpt" ;;
    gemini:api:google-api-key) LAUNCHER_AUTH="custom" ;;
  esac
fi

printf 'restart-seat:\n  project:       %s\n  seat:          %s\n  tool:          %s\n  auth:          %s\n  launcher_auth: %s\n  workspace:     %s\n  session:       %s\n' \
  "$PROJECT" "$SEAT" "$TOOL" "$AUTH_MODE" "$LAUNCHER_AUTH" "$WORKSPACE" "$SESSION_NAME"

if "$TMUX_BIN" has-session -t "=$SESSION_NAME" 2>/dev/null; then
  echo "  status:    killing existing session"
  "$TMUX_BIN" kill-session -t "=$SESSION_NAME"
else
  echo "  status:    no existing session"
fi

# agent-launcher.sh --headless creates the tmux session itself (don't wrap
# in `tmux new-session`). It validates inputs, wires env (HOME, CODEX_HOME,
# etc.), and re-execs as --exec-agent inside the session it spawns.
CLAWSEAT_PROJECT="$PROJECT" CLAWSEAT_SEAT="$SEAT" \
  bash "$LAUNCHER" \
  --headless \
  --tool "$TOOL" \
  --session "$SESSION_NAME" \
  --auth "$LAUNCHER_AUTH" \
  --dir "$WORKSPACE" >/dev/null

# Verify the session came up.
for _ in 1 2 3 4 5; do
  sleep 0.5
  "$TMUX_BIN" has-session -t "=$SESSION_NAME" 2>/dev/null && break
done

if ! "$TMUX_BIN" has-session -t "=$SESSION_NAME" 2>/dev/null; then
  echo "error: tmux session $SESSION_NAME failed to come up" >&2
  exit 1
fi

echo "  result:    tmux session alive"

if [[ "$NO_WINDOW" == "0" ]]; then
  # Refresh the project grid so any iTerm pane re-attaches to the fresh
  # session. Tolerate failure — the tmux session is the durable artifact.
  if ! "$PYTHON_BIN" "$AGENT_ADMIN" window open-grid "$PROJECT" --quiet 2>&1; then
    echo "warn: window open-grid $PROJECT failed; tmux is alive — attach manually with:" >&2
    echo "  $TMUX_BIN attach -t '=$SESSION_NAME'" >&2
  fi
fi

echo "done."
