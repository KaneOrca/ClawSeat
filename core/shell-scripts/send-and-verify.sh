#!/usr/bin/env bash
set -euo pipefail
# send-and-verify.sh — fire-and-forget: send message + 3 Enter flushes
# Usage: ./send-and-verify.sh [--project <project>] <session> "<message>"
# Exit codes: 0=sent, 1=param error/SESSION_NOT_FOUND/SESSION_DEAD/TMUX_MISSING,
#             2=INPUT_REJECTED (control chars or oversized message, audit H3)
#             3=PROJECT_REQUIRED (multi-project mode, no project scope given, audit C6)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT=""; if [ "${1:-}" = "--project" ]; then PROJECT="${2:-}"; shift 2; fi
SESSION="${1:-}"; MSG="${2:-}"
if [ -z "$SESSION" ] || [ -z "$MSG" ]; then
  echo "Usage: send-and-verify.sh [--project <project>] <session> \"<message>\""; exit 1
fi

# ── C6: multi-project guardrail ──────────────────────────────────────
# Without --project and without CLAWSEAT_PROJECT, `agentctl session-name`
# picks *any* session with a matching seat id, so sending a reminder
# for project install can silently land in another project's tmux window.
# Guardrail: if >1 project has a PROJECT_BINDING.toml under
# ~/.agents/tasks/*/PROJECT_BINDING.toml, demand an explicit scope.
# Single-project setups (legacy or greenfield) are unaffected.
# Escape hatch: CLAWSEAT_SEND_ALLOW_NO_PROJECT=1 restores the old behavior.
if [ -z "$PROJECT" ] && [ -n "${CLAWSEAT_PROJECT:-}" ]; then
  PROJECT="$CLAWSEAT_PROJECT"
fi
if [ -z "$PROJECT" ] && [ "${CLAWSEAT_SEND_ALLOW_NO_PROJECT:-0}" != "1" ]; then
  # ${HOME:-} keeps `set -u` from tripping when callers (e.g. tests that
  # scrub env) don't export HOME. Without a real or fake home, the
  # guardrail cannot enumerate projects and no-ops.
  TASKS_DIR="${CLAWSEAT_REAL_HOME:-${HOME:-}}/.agents/tasks"
  # Enumerate projects that declared themselves via PROJECT_BINDING.toml.
  # null-glob safe: if the pattern matches nothing, `set -- $pattern` expands
  # to the literal pattern; guard with a direct file existence check.
  project_count=0
  if [ -d "$TASKS_DIR" ]; then
    for binding in "$TASKS_DIR"/*/PROJECT_BINDING.toml; do
      [ -f "$binding" ] && project_count=$((project_count + 1))
    done
  fi
  if [ "$project_count" -gt 1 ]; then
    echo "send-and-verify: PROJECT_REQUIRED" >&2
    {
      echo "  reason: multi_project_mode_no_scope"
      echo "  tasks_dir: $TASKS_DIR"
      echo "  bindings_found: $project_count"
      echo "  session_requested: $SESSION"
      echo "  fix: rerun with --project <name>, set CLAWSEAT_PROJECT=<name>,"
      echo "       or set CLAWSEAT_SEND_ALLOW_NO_PROJECT=1 if you accept"
      echo "       cross-project session resolution (discouraged)"
    } >&2
    exit 3
  fi
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

# Resolve tmux-send — the compliant agent-launcher send entry point.
# tmux-send internally sets AGENT_LAUNCHER_TMUX_SEND_ACTIVE=1 and handles Enter,
# bypassing the tmux guard that blocks raw send-keys from subprocesses.
TMUX_SEND_BIN=""
_resolve_tmux_send() {
  local _c
  _c="$(command -v tmux-send 2>/dev/null || true)"
  if [ -n "$_c" ] && [ -x "$_c" ]; then TMUX_SEND_BIN="$_c"; return 0; fi
  _c="${AGENT_LAUNCHER_BIN:-${HOME:-}/.local/share/agent-launcher/bin}/tmux-send"
  if [ -x "$_c" ]; then TMUX_SEND_BIN="$_c"; return 0; fi
  return 1
}
_resolve_tmux_send || true

send_via_tmux_send() {
  "$TMUX_SEND_BIN" "$1" "$2"
}
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

if [ -n "$TMUX_SEND_BIN" ]; then
  # Delegate to tmux-send — compliant agent-launcher entry point.
  # Handles AGENT_LAUNCHER_TMUX_SEND_ACTIVE and Enter internally.
  send_via_tmux_send "$SESSION" "$MSG"
else
  # Fallback: raw tmux send-keys with guard-bypass env var.
  export AGENT_LAUNCHER_TMUX_SEND_ACTIVE=1
  env -u TMUX "$TMUX_BIN" send-keys -l -t "$SESSION" "$MSG"
  sleep 0.3
  for _ in 1 2 3; do env -u TMUX "$TMUX_BIN" send-keys -t "$SESSION" Enter; sleep 0.2; done
fi
echo "SENT: $SESSION"
exit 0
