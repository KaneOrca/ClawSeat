#!/usr/bin/env bash
set -euo pipefail

PROJECT="clawseat"
CLAWSEAT_ROOT="$HOME/ClawSeat"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --clawseat-root) CLAWSEAT_ROOT="$2"; shift 2 ;;
    --help)
      echo "Usage: scripts/launch-grid.sh [--project <name>] [--clawseat-root <path>]"
      exit 0
      ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

CLAWSEAT_ROOT="${CLAWSEAT_ROOT/#\~/$HOME}"
SEATS=(ancestor planner builder reviewer qa designer)

ensure_session() {
  local name="$1" cmd="$2"
  tmux has-session -t "$name" 2>/dev/null && return 0
  tmux new-session -d -s "$name" -c "$CLAWSEAT_ROOT" "$cmd"
}

ensure_session "${PROJECT}-ancestor" "bash -lc 'claude --dangerously-skip-permissions; exec bash'"
for seat in "${SEATS[@]:1}"; do
  ensure_session "${PROJECT}-${seat}" "bash"
done

PROJECT="$PROJECT" CLAWSEAT_ROOT="$CLAWSEAT_ROOT" python3 - <<'PY'
import os
import sys
from pathlib import Path
from types import SimpleNamespace

root = Path(os.environ["CLAWSEAT_ROOT"]).expanduser()
sys.path.insert(0, str(root / "core" / "scripts"))
from agent_admin_window import build_monitor_layout

seats = ["ancestor", "planner", "builder", "reviewer", "qa", "designer"]
project = SimpleNamespace(
    name=os.environ["PROJECT"],
    repo_root=str(root),
    monitor_session=f"{os.environ['PROJECT']}-monitor",
    monitor_engineers=seats,
    monitor_max_panes=len(seats),
    window_mode="grid-6up",
)
sessions = {
    seat: SimpleNamespace(engineer_id=seat, session=f"{os.environ['PROJECT']}-{seat}")
    for seat in seats
}
build_monitor_layout(project, sessions)
PY

echo "tmux attach -t ${PROJECT}-monitor"
