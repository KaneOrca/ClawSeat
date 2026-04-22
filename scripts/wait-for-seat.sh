#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s <project-seat> | <project> <seat>\n' "$0" >&2
  exit 2
}

if [[ $# -eq 1 ]]; then
  BASE_SESSION="$1"
elif [[ $# -eq 2 ]]; then
  BASE_SESSION="$1-$2"
else
  usage
fi

POLL_SECONDS="${WAIT_FOR_SEAT_POLL_SECONDS:-5}"

resolve_session() {
  local base="$1" candidate=""
  for candidate in "$base" "$base-claude" "$base-codex" "$base-gemini"; do
    if tmux has-session -t "=$candidate" 2>/dev/null; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

printf 'pane is waiting for %s ...\n' "$BASE_SESSION"
printf '(seat will appear here once ancestor spawns it)\n'

while true; do
  if TARGET_SESSION="$(resolve_session "$BASE_SESSION")"; then
    exec tmux attach -t "=$TARGET_SESSION"
  fi
  sleep "$POLL_SECONDS"
done
