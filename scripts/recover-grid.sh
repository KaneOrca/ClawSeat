#!/usr/bin/env bash
# recover-grid.sh — recover misrouted iTerm grid panes.
#
# Use this when specialist panes (planner/builder/reviewer/qa/designer)
# are showing the primary seat's TUI content instead of their own seat.
#
# Root cause (suspected): panes' wait-for-seat.sh attached to the project's
# primary seat session before specialist tmux sessions existed, and their
# tmux-attach loop is still blocking on that stale connection.
#
# What this does: detaches every client on the primary seat session except the
# primary seat pane client. Each detached pane's wait-for-seat.sh
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
PRIMARY_SEAT_ID="$(
  PROJECT="$PROJECT" python3 - <<'PY'
import os
from pathlib import Path

try:
    import tomllib

    project = os.environ["PROJECT"]
    project_toml = Path.home() / ".agents" / "projects" / project / "project.toml"
    data = tomllib.loads(project_toml.read_text()) if project_toml.exists() else {}
    engineers = data.get("engineers") or []
    primary = engineers[0] if engineers else ""
    if isinstance(primary, dict):
        primary = primary.get("id", "")
    print(primary or "ancestor")
except Exception:
    print("ancestor")
PY
)"
PRIMARY_SESSION="${PROJECT}-${PRIMARY_SEAT_ID}"
WINDOW_TITLE="clawseat-${PROJECT}"

if ! env -u TMUX tmux has-session -t "=$PRIMARY_SESSION" 2>/dev/null; then
  echo "error: no tmux session named '$PRIMARY_SESSION'" >&2
  echo "hint: is the primary seat running? check \`tmux list-sessions\`" >&2
  exit 1
fi

# Step 1: if the iTerm 6-pane window has been closed entirely (distinct
# from "pane is misrouted inside the window"), reopen it and exit —
# open-grid creates a fresh window with correctly-wired panes, so the
# detach-client dance below is not needed.
if command -v osascript >/dev/null 2>&1; then
  window_count="$(osascript -e "tell application \"iTerm2\" to count of (windows whose name is \"$WINDOW_TITLE\")" 2>/dev/null || echo 0)"
  if [[ "${window_count:-0}" -eq 0 ]]; then
    echo "iTerm window '$WINDOW_TITLE' missing — invoking window open-grid ..."
    agent_admin_bin="$(cd "$(dirname "$0")/.." && pwd)/core/scripts/agent_admin.py"
    if [[ -f "$agent_admin_bin" ]]; then
      # Surface stderr so failures are visible (RCA 2026-04-25 — silent failure
      # masked a grid disappearance recovery attempt in a live project).
      if python3 "$agent_admin_bin" window open-grid "$PROJECT" >/dev/null; then
        echo "recovered: opened new iTerm grid for $PROJECT"
        exit 0
      fi
      echo "warn: agent_admin.py window open-grid failed; falling through to client cleanup" >&2
    else
      echo "warn: agent_admin.py not found at $agent_admin_bin; skipping window open" >&2
    fi
  fi
fi

clients="$(env -u TMUX tmux list-clients -t "=$PRIMARY_SESSION" -F '#{client_tty}' 2>/dev/null || true)"
total=$(printf '%s\n' "$clients" | grep -c . || true)

if [[ "$total" -le 1 ]]; then
  echo "ok: $PRIMARY_SESSION has $total client(s) — no recovery needed"
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
echo "recovered: detached $count wrong client(s) from $PRIMARY_SESSION"
echo "each affected pane's wait-for-seat.sh loop will now re-resolve + attach to its canonical seat"
echo
echo "verify: tmux list-clients per seat - see agent_admin window list-panes --project ${PROJECT}"
