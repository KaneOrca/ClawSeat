#!/bin/bash
set -euo pipefail
# send-and-verify.sh — 发送指令并验证是否成功
# 用法: ./send-and-verify.sh [--project <project>] <session> "<message>"
#
# 发送后等 3 秒检查快照，如果指令还卡在输入框（未提交），自动补发 Enter。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT=""
if [ "${1:-}" = "--project" ]; then
  PROJECT="${2:-}"
  shift 2
fi

SESSION="${1:-}"
MSG="${2:-}"

if [ -z "$SESSION" ] || [ -z "$MSG" ]; then
  echo "Usage: send-and-verify.sh [--project <project>] <session> \"<message>\""
  exit 1
fi

resolve_tmux_bin() {
  if command -v tmux >/dev/null 2>&1; then
    command -v tmux
    return 0
  fi
  for candidate in /opt/homebrew/bin/tmux /usr/local/bin/tmux /usr/bin/tmux /bin/tmux; do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

TMUX_BIN="$(resolve_tmux_bin || true)"
if [ -z "$TMUX_BIN" ]; then
  echo "send-and-verify: TMUX_MISSING - cannot resolve tmux binary"
  exit 1
fi

AGENTCTL="$REPO_ROOT/core/shell-scripts/agentctl.sh"
if [ -n "$PROJECT" ]; then
  RESOLVED_SESSION="$("$AGENTCTL" session-name "$SESSION" --project "$PROJECT")"
else
  RESOLVED_SESSION="$("$AGENTCTL" session-name "$SESSION")"
fi

if [ -z "$RESOLVED_SESSION" ]; then
  echo "send-and-verify: SESSION_NOT_FOUND project=$PROJECT seat=$SESSION"
  exit 1
fi
SESSION="$RESOLVED_SESSION"

run_tmux() {
  local command_name="$1"
  shift
  if ! RESULT="$(env -u TMUX "$TMUX_BIN" "$@" 2>&1)"; then
    local rc=$?
    echo "${SESSION}: ${command_name}_FAILED rc=$rc output=${RESULT:-no_output}" >&2
    return "$rc"
  fi
  LAST_TMUX_OUTPUT="$RESULT"
  return 0
}

capture_tail() {
  run_tmux "capture-pane" capture-pane -t "$SESSION" -p || return 1
  printf "%s\n" "$LAST_TMUX_OUTPUT" | tail -n 5
}

before="$(capture_tail)" || {
  rc=$?
  echo "${SESSION}: CAPTURE_BEFORE_FAILED rc=${rc}"
  exit 1
}

send_and_verify_once() {
  local message="$1"
  if ! run_tmux "send-text" send-keys -t "$SESSION" "$message"; then
    return 1
  fi
  sleep 1
  if ! run_tmux "send-enter" send-keys -t "$SESSION" Enter; then
    return 1
  fi
  return 0
}

if ! send_and_verify_once "$MSG"; then
  echo "${SESSION}: SEND_FAILED (iterm-only flow)"
  exit 1
fi

sleep 3
after="$(capture_tail)" || {
  rc=$?
  echo "${SESSION}: CAPTURE_AFTER_FAILED rc=${rc}"
  exit 1
}

if printf "%s\n" "$after" | grep -qF "$MSG"; then
  echo "${SESSION}: RETRY_NEEDED - message still visible; attempting Enter retry"
  if ! run_tmux "retry-enter" send-keys -t "$SESSION" Enter; then
    echo "${SESSION}: RETRY_ENTER_FAILED"
    exit 1
  fi
  sleep 2
  after2="$(capture_tail)" || {
    rc=$?
    echo "${SESSION}: CAPTURE_AFTER_RETRY_FAILED rc=${rc}"
    exit 1
  }
  if printf "%s\n" "$after2" | grep -qF "$MSG"; then
    echo "${SESSION}: RETRY_FAILED - message may not be received by pane process"
    exit 1
  fi
  echo "${SESSION}: OK (retry Enter)"
else
  echo "${SESSION}: OK"
fi
