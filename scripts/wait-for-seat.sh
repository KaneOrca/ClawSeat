#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENTCTL="${AGENTCTL_BIN:-$REPO_ROOT/core/shell-scripts/agentctl.sh}"

usage() {
  printf 'Usage: %s <project> <seat>\n' "$0" >&2
  exit 2
}

PROJECT_SCOPE="${CLAWSEAT_PROJECT:-}"
SEAT_ID=""
BASE_SESSION=""
if [[ $# -eq 1 ]]; then
  printf 'error: 1-arg form is retired; rerun as: %s <project> <seat>\n' "$0" >&2
  exit 2
elif [[ $# -eq 2 ]]; then
  PROJECT_SCOPE="$1"
  SEAT_ID="$2"
  BASE_SESSION="$PROJECT_SCOPE-$SEAT_ID"
else
  usage
fi

POLL_SECONDS="${WAIT_FOR_SEAT_POLL_SECONDS:-2}"
RECONNECT_PAUSE="${WAIT_FOR_SEAT_RECONNECT_PAUSE:-2}"
PRIMARY_FAILURE_BUDGET="${WAIT_FOR_SEAT_PRIMARY_FAILURE_BUDGET:-10}"
DEGRADED_WARN_EVERY_POLLS="${WAIT_FOR_SEAT_DEGRADED_WARN_EVERY_POLLS:-15}"
PRIMARY_FAILURE_COUNT=0
TARGET_SESSION=""

resolve_via_agentctl() {
  local resolved=""
  [[ -x "$AGENTCTL" ]] || return 1
  resolved="$("$AGENTCTL" session-name "$SEAT_ID" --project "$PROJECT_SCOPE" 2>/dev/null || true)"
  [[ -n "$resolved" ]] || return 1
  printf '%s\n' "$resolved"
}

fallback_session_prefix() {
  printf '%s-%s\n' "$PROJECT_SCOPE" "$SEAT_ID"
}

warn_fallback_attach() {
  local attempt_count="$1"
  local session_name="$2"
  printf "WARN: agentctl resolution failed after %s attempts; falling back to '%s'\n" \
    "$attempt_count" "$session_name" >&2
}

warn_degraded_wait() {
  local attempt_count="$1"
  printf "WARN: agentctl resolution still degraded for %s after %s attempts; waiting for canonical session or fixed suffix fallback\n" \
    "$BASE_SESSION" "$attempt_count" >&2
}

resolve_via_fixed_suffix_fallback() {
  local prefix="" suffix="" candidate=""
  prefix="$(fallback_session_prefix || true)"
  [[ -n "$prefix" ]] || return 1
  for suffix in claude codex gemini; do
    candidate="${prefix}-${suffix}"
    if tmux has-session -t "=$candidate" 2>/dev/null; then
      warn_fallback_attach "$PRIMARY_FAILURE_COUNT" "$candidate"
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

resolve_session() {
  local base="$1" resolved=""
  TARGET_SESSION=""
  resolved="$(resolve_via_agentctl || true)"
  if [[ -n "$resolved" ]] && tmux has-session -t "=$resolved" 2>/dev/null; then
    PRIMARY_FAILURE_COUNT=0
    TARGET_SESSION="$resolved"
    return 0
  fi
  PRIMARY_FAILURE_COUNT=$((PRIMARY_FAILURE_COUNT + 1))
  if (( PRIMARY_FAILURE_COUNT >= PRIMARY_FAILURE_BUDGET )); then
    if resolved="$(resolve_via_fixed_suffix_fallback)"; then
      TARGET_SESSION="$resolved"
      return 0
    fi
    if (( PRIMARY_FAILURE_COUNT == PRIMARY_FAILURE_BUDGET )) || \
       (( DEGRADED_WARN_EVERY_POLLS > 0 && PRIMARY_FAILURE_COUNT % DEGRADED_WARN_EVERY_POLLS == 0 )); then
      warn_degraded_wait "$PRIMARY_FAILURE_COUNT"
    fi
  fi
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
  if resolve_session "$BASE_SESSION"; then
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
