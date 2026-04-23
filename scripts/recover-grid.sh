#!/usr/bin/env bash
# recover-grid.sh — recover misrouted iTerm grid panes.
#
# Use this when specialist panes (planner/builder/reviewer/qa/designer)
# are showing ancestor's TUI content instead of their own seat.
#
# Root cause (suspected): panes' wait-for-seat.sh attached to install-ancestor
# before specialist tmux sessions existed, and their tmux-attach loop
# is still blocking on that stale connection.
#
# What this does: detaches every client on install-ancestor except the
# primary ancestor pane client. Each detached pane's wait-for-seat.sh
# loop will re-resolve via agentctl and attach to its canonical seat.
#
# Usage:
#   bash scripts/recover-grid.sh [project]
# Default project = "install".
#
# If panes are still misrouted after this, rebuild the window:
#   python3 core/scripts/agent_admin.py window open-grid <project>
set -euo pipefail

PROJECT="${1:-install}"
ANCESTOR_SESSION="${PROJECT}-ancestor"

if ! env -u TMUX tmux has-session -t "=$ANCESTOR_SESSION" 2>/dev/null; then
  echo "error: no tmux session named '$ANCESTOR_SESSION'" >&2
  echo "hint: is the ancestor seat running? check \`tmux list-sessions\`" >&2
  exit 1
fi

clients="$(env -u TMUX tmux list-clients -t "=$ANCESTOR_SESSION" -F '#{client_tty}' 2>/dev/null || true)"
total=$(printf '%s\n' "$clients" | grep -c . || true)

if [[ "$total" -le 1 ]]; then
  echo "ok: $ANCESTOR_SESSION has $total client(s) — no recovery needed"
  exit 0
fi

extras="$(printf '%s\n' "$clients" | tail -n +2)"
count=0
while IFS= read -r tty; do
  [[ -z "$tty" ]] && continue
  if env -u TMUX tmux detach-client -t "$tty" 2>/dev/null; then
    echo "detached: $tty"
    count=$((count + 1))
  else
    echo "skip (gone): $tty"
  fi
done <<< "$extras"

echo
echo "recovered: detached $count wrong client(s) from $ANCESTOR_SESSION"
echo "each affected pane's wait-for-seat.sh loop will now re-resolve + attach to its canonical seat"
echo
echo "verify with:"
echo "  for s in ${PROJECT}-ancestor ${PROJECT}-planner-claude ${PROJECT}-builder-codex ${PROJECT}-reviewer-codex ${PROJECT}-qa-claude ${PROJECT}-designer-gemini; do"
echo "    tmux list-clients -t =\$s 2>/dev/null | wc -l | awk -v s=\$s '{print s\": \"\$1\" client(s)\"}'"
echo "  done"
