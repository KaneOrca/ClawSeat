#!/usr/bin/env bash
set -uo pipefail

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
RECONNECT_PAUSE="${WAIT_FOR_SEAT_RECONNECT_PAUSE:-2}"

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

print_waiting() {
  printf 'pane is waiting for %s ...\n' "$BASE_SESSION"
  printf '(seat will appear here once ancestor spawns it)\n'
}

print_reconnecting() {
  local session_name="$1"
  printf 'DETACHED from %s - reconnecting in %ss ...\n' "$session_name" "$RECONNECT_PAUSE"
  printf '(tmux session is still alive; press Ctrl+C to stop waiting)\n'
}

print_trust_prompt_detected() {
  local session_name="$1"
  printf 'gemini trust prompt detected at %s - operator attach pane and press 1\n' "$session_name" >&2
}

capture_pane_text() {
  local session_name="$1"
  tmux capture-pane -t "=$session_name" -p -S -80 2>/dev/null || true
}

detect_trust_prompt() {
  case "$1" in
    *"Do you trust the files in this folder"*|*"Trust folder"*)
      return 0
      ;;
  esac
  return 1
}

while true; do
  if TARGET_SESSION="$(resolve_session "$BASE_SESSION")"; then
    if tmux attach -t "=$TARGET_SESSION"; then
      print_reconnecting "$TARGET_SESSION"
    else
      pane_text="$(capture_pane_text "$TARGET_SESSION")"
      if detect_trust_prompt "$pane_text"; then
        print_trust_prompt_detected "$TARGET_SESSION"
      else
        print_reconnecting "$TARGET_SESSION"
      fi
    fi
    sleep "$RECONNECT_PAUSE"
  else
    print_waiting
    sleep "$POLL_SECONDS"
  fi
done
