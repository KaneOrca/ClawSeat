#!/usr/bin/env bash
set -euo pipefail
# send-and-verify.sh — fire-and-forget: send message + 3 Enter flushes
# Usage: ./send-and-verify.sh [--project <project>] <session> "<message>"
# Exit codes: 0=sent, 1=param error/SESSION_NOT_FOUND/SESSION_DEAD/TMUX_MISSING, 2=SKIPPED (reserved)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT=""; if [ "${1:-}" = "--project" ]; then PROJECT="${2:-}"; shift 2; fi
SESSION="${1:-}"; MSG="${2:-}"
if [ -z "$SESSION" ] || [ -z "$MSG" ]; then
  echo "Usage: send-and-verify.sh [--project <project>] <session> \"<message>\""; exit 1
fi

TMUX_BIN="$(command -v tmux 2>/dev/null || for c in /opt/homebrew/bin/tmux /usr/local/bin/tmux /usr/bin/tmux; do [ -x "$c" ] && echo "$c" && break; done || true)"
[ -z "$TMUX_BIN" ] && { echo "send-and-verify: TMUX_MISSING"; exit 1; }

AGENTCTL="${AGENTCTL_BIN:-$REPO_ROOT/core/shell-scripts/agentctl.sh}"
if [ -n "$PROJECT" ]; then RESOLVED="$("$AGENTCTL" session-name "$SESSION" --project "$PROJECT")"
else RESOLVED="$("$AGENTCTL" session-name "$SESSION")"; fi
[ -z "$RESOLVED" ] && { echo "send-and-verify: SESSION_NOT_FOUND project=$PROJECT seat=$SESSION"; exit 1; }
SESSION="$RESOLVED"
env -u TMUX "$TMUX_BIN" has-session -t "$SESSION" 2>/dev/null \
  || { echo "send-and-verify: SESSION_DEAD session=$SESSION"; exit 1; }

env -u TMUX "$TMUX_BIN" send-keys -l -t "$SESSION" "$MSG"
sleep 0.3
for _ in 1 2 3; do env -u TMUX "$TMUX_BIN" send-keys -t "$SESSION" Enter; sleep 0.2; done
echo "SENT: $SESSION"
exit 0
