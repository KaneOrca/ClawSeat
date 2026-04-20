#!/usr/bin/env bash
set -euo pipefail
# send-and-verify.sh — fire-and-forget: send message + 3 Enter flushes
# Usage: ./send-and-verify.sh [--project <project>] <session> "<message>"
# Exit codes: 0=sent, 1=param error/SESSION_NOT_FOUND/SESSION_DEAD/TMUX_MISSING,
#             2=INPUT_REJECTED (control chars or oversized message, audit H3)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT=""; if [ "${1:-}" = "--project" ]; then PROJECT="${2:-}"; shift 2; fi
SESSION="${1:-}"; MSG="${2:-}"
if [ -z "$SESSION" ] || [ -z "$MSG" ]; then
  echo "Usage: send-and-verify.sh [--project <project>] <session> \"<message>\""; exit 1
fi

# — 输入校验 (audit H3) —
# Session names flow straight into `tmux has-session` / `send-keys -t`, so any
# control character in $SESSION is rejected outright (LF/CR/VT/FF).
# Messages are rendered via `tmux send-keys -l`, which presses every byte
# literally. LF is an intentional multi-line feature (see
# test_send_notify_simplified::test_newline_message), but CR would act as a
# bare Return mid-message and VT/FF would produce garbled output in the pane.
# Bash cannot carry NUL inside a variable (truncated at parse), so no NUL case.
MAX_MSG_BYTES=8192

reject_session_control_chars() {
  local name="$1" origin="$2"
  case "$name" in
    *$'\n'*|*$'\r'*|*$'\v'*|*$'\f'*)
      echo "send-and-verify: INPUT_REJECTED ${origin} session contains control character (LF/CR/VT/FF)" >&2
      echo "send-and-verify: HARD_BLOCK caller must strip control chars before retry" >&2
      exit 2
      ;;
  esac
}

reject_session_control_chars "$SESSION" "argv"
case "$MSG" in
  *$'\r'*|*$'\v'*|*$'\f'*)
    echo "send-and-verify: INPUT_REJECTED message contains control character (CR/VT/FF)" >&2
    echo "send-and-verify: HARD_BLOCK caller must strip control chars before retry" >&2
    exit 2
    ;;
esac

msg_bytes=${#MSG}
if [ "$msg_bytes" -gt "$MAX_MSG_BYTES" ]; then
  echo "send-and-verify: INPUT_REJECTED message length ${msg_bytes} exceeds ${MAX_MSG_BYTES} bytes" >&2
  echo "send-and-verify: HARD_BLOCK caller must shorten message or chunk the send" >&2
  exit 2
fi

# Allow TMUX_BIN env override (same injection pattern as AGENTCTL_BIN, used in tests)
if [ -z "${TMUX_BIN:-}" ]; then
  TMUX_BIN="$(command -v tmux 2>/dev/null || for c in /opt/homebrew/bin/tmux /usr/local/bin/tmux /usr/bin/tmux; do [ -x "$c" ] && echo "$c" && break; done || true)"
fi
if [ -z "$TMUX_BIN" ] || ! [ -x "$TMUX_BIN" ]; then
  echo "send-and-verify: TMUX_MISSING"
  {
    echo "  reason: tmux_missing"
    echo "  searched: /opt/homebrew/bin/tmux /usr/local/bin/tmux /usr/bin/tmux"
    echo "  PATH: $PATH"
    echo "  fix: brew install tmux  # macOS | apt install tmux  # Linux"
  } >&2
  exit 1
fi

AGENTCTL="${AGENTCTL_BIN:-$REPO_ROOT/core/shell-scripts/agentctl.sh}"
_agentctl_err_file="$(mktemp)"
trap 'rm -f "$_agentctl_err_file"' EXIT
_agentctl_rc=0
if [ -n "$PROJECT" ]; then
  RESOLVED="$("$AGENTCTL" session-name "$SESSION" --project "$PROJECT" 2>"$_agentctl_err_file")" || _agentctl_rc=$?
else
  RESOLVED="$("$AGENTCTL" session-name "$SESSION" 2>"$_agentctl_err_file")" || _agentctl_rc=$?
fi
_agentctl_err="$(cat "$_agentctl_err_file" 2>/dev/null || true)"

if [ -z "$RESOLVED" ]; then
  echo "send-and-verify: SESSION_NOT_FOUND project=$PROJECT seat=$SESSION"
  {
    echo "  reason: session_not_found"
    echo "  project: ${PROJECT:-<unset>}"
    echo "  requested_seat: $SESSION"
    echo "  agentctl_bin: $AGENTCTL"
    echo "  agentctl_rc: $_agentctl_rc"
    [ -n "$_agentctl_err" ] && echo "  agentctl_stderr: $_agentctl_err"
    echo "  possible_causes: seat not started | project name typo | agentctl not registered for seat"
    echo "  fix: agentctl list / agentctl start --profile <profile>"
  } >&2
  exit 1
fi
reject_session_control_chars "$RESOLVED" "resolved"
SESSION="$RESOLVED"

if ! env -u TMUX "$TMUX_BIN" has-session -t "$SESSION" 2>/dev/null; then
  echo "send-and-verify: SESSION_DEAD session=$SESSION"
  {
    echo "  reason: session_dead"
    echo "  session: $SESSION"
    echo "  tmux_bin: $TMUX_BIN"
    echo "  fix: tmux ls to check active sessions; if none, agentctl start to restart seat"
    if [ "${CLAWSEAT_SEND_VERIFY_DEBUG:-0}" = "1" ]; then
      echo "  tmux_sessions: $(env -u TMUX "$TMUX_BIN" list-sessions 2>/dev/null || true)"
    fi
  } >&2
  exit 1
fi

if [ "${CLAWSEAT_SEND_VERIFY_DEBUG:-0}" = "1" ]; then
  {
    echo "send-and-verify: DEBUG"
    echo "  tmux_sessions: $(env -u TMUX "$TMUX_BIN" list-sessions 2>/dev/null || true)"
  } >&2
fi

env -u TMUX "$TMUX_BIN" send-keys -l -t "$SESSION" "$MSG"
sleep 0.3
for _ in 1 2 3; do env -u TMUX "$TMUX_BIN" send-keys -t "$SESSION" Enter; sleep 0.2; done
echo "SENT: $SESSION"
exit 0
