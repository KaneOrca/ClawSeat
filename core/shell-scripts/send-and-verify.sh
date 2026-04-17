#!/usr/bin/env bash
set -euo pipefail
# send-and-verify.sh — 发送指令并验证是否成功
# 用法: ./send-and-verify.sh [--project <project>] <session> "<message>"
#
# 发送后使用 OpenClaw 官方 wait-for-text.sh 等待 Claude 提示符重现（替代固定 sleep）。
# 无论 wait-for-text.sh 是否超时，都用 grep 二次确认消息未残留在输入区。
# 若 wait-for-text.sh 不可用，退回 sleep+grep 方式。

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
  echo "send-and-verify: iTerm-only hard-stop: fix PATH/tmux install, then retry."
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
  echo "send-and-verify: iTerm-only hard-stop: run project bootstrap/start to recreate this seat."
  exit 1
fi
SESSION="$RESOLVED_SESSION"

# OpenClaw 官方 wait-for-text.sh — 可通过环境变量覆盖路径
OC_WAIT_FOR_TEXT="${OC_WAIT_FOR_TEXT:-/opt/homebrew/lib/node_modules/openclaw/skills/tmux/scripts/wait-for-text.sh}"
PROMPT_PATTERN="❯"
WAIT_TIMEOUT=10   # seconds: max wait for prompt to reappear
WAIT_INTERVAL=0.5 # seconds: poll interval
WAIT_LINES=5      # inspect only last N lines (avoid scrollback false-positives)

run_tmux() {
  local command_name="$1"
  shift
  RESULT="$(env -u TMUX "$TMUX_BIN" "$@" 2>&1)"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "${SESSION}: ${command_name}_FAILED rc=$rc output=${RESULT:-no_output}" >&2
    echo "${SESSION}: HARD_BLOCK iTerm-only tmux execution failure" >&2
    return "$rc"
  fi
  LAST_TMUX_OUTPUT="$RESULT"
  return 0
}

capture_tail() {
  local LAST_TMUX_OUTPUT=""
  run_tmux "capture-pane" capture-pane -t "$SESSION" -p || return 1
  printf "%s\n" "$LAST_TMUX_OUTPUT" | tail -n 5
}

# Called when the post-send grep finds message still in input area.
# Retries up to 3 times with backoffs=(2 4 8) seconds. Exits 1 on failure.
retry_enter_and_check() {
  local backoffs=(2 4 8)
  local attempt
  for attempt in 1 2 3; do
    local sleep_s="${backoffs[$((attempt - 1))]}"
    echo "${SESSION}: RETRY_NEEDED attempt=${attempt}/3 — sending Enter Enter, backoff=${sleep_s}s"
    if ! run_tmux "retry-enter-1" send-keys -t "$SESSION" Enter; then
      echo "${SESSION}: RETRY_ENTER_FAILED attempt=${attempt}"
      exit 1
    fi
    if ! run_tmux "retry-enter-2" send-keys -t "$SESSION" Enter; then
      echo "${SESSION}: RETRY_ENTER_FAILED attempt=${attempt}"
      exit 1
    fi
    sleep "$sleep_s"
    local after
    after="$(capture_tail)" || {
      echo "${SESSION}: CAPTURE_AFTER_RETRY_FAILED attempt=${attempt}"
      echo "${SESSION}: HARD_BLOCK iTerm-only retry verification failed"
      exit 1
    }
    if ! printf "%s\n" "$after" | grep -qF "$MSG"; then
      echo "${SESSION}: OK (retry Enter, attempt=${attempt})"
      return 0
    fi
  done
  echo "${SESSION}: RETRY_FAILED attempts=3 backoffs=2s/4s/8s prior_pane_may_be_busy_or_modal"
  exit 1
}

# Liveness check before send
pre_send_tail=""
pre_send_tail="$(capture_tail)" || {
  echo "${SESSION}: CAPTURE_BEFORE_FAILED"
  echo "${SESSION}: HARD_BLOCK iTerm-only precheck failed before submit"
  exit 1
}
if printf "%s\n" "$pre_send_tail" | grep -Eq '[>❯][[:space:]]+[^[:space:]│╮╯╭─]'; then
  echo "${SESSION}: prior_stuck_input_detected_cleaned"
  if ! run_tmux "precheck-clean-enter" send-keys -t "$SESSION" Enter; then
    echo "${SESSION}: PRECHECK_CLEAN_FAILED"
    echo "${SESSION}: HARD_BLOCK iTerm-only pre-send cleanup failed"
    exit 1
  fi
  sleep 0.5
fi

send_and_verify_once() {
  local message="$1"
  if ! run_tmux "send-text" send-keys -l -t "$SESSION" "$message"; then
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
  echo "${SESSION}: HARD_BLOCK iTerm-only verify chain failed while sending"
  exit 1
fi

# — 验证阶段 —
if [ -x "$OC_WAIT_FOR_TEXT" ]; then
  # 等待 0.5s 让 Claude 进入处理状态、清除输入区，避免竞态：
  # 若 Enter 未注册，❯ 仍显示但消息残留在输入行；
  # 若 Enter 已注册，Claude 开始处理，❯ 消失。
  sleep 0.5
  wft_exit=0
  "$OC_WAIT_FOR_TEXT" \
      -t "$SESSION" \
      -p "$PROMPT_PATTERN" \
      -T "$WAIT_TIMEOUT" \
      -i "$WAIT_INTERVAL" \
      -l "$WAIT_LINES" \
      2>/dev/null || wft_exit=$?

  # 无论 wait-for-text 是否超时，均检查消息是否已被消费
  after="$(capture_tail)" || {
    echo "${SESSION}: CAPTURE_AFTER_FAILED"
    echo "${SESSION}: HARD_BLOCK iTerm-only verify chain failed after wait-for-text"
    exit 1
  }
  if printf "%s\n" "$after" | grep -qF "$MSG"; then
    # 消息仍在输入区（Enter 未注册）——补发
    retry_enter_and_check
  elif [ "$wft_exit" -eq 0 ]; then
    # 提示符已重现，消息已消费
    echo "${SESSION}: OK"
  else
    # 提示符未在 ${WAIT_TIMEOUT}s 内重现，但消息已消费 — Claude 正在处理长任务
    echo "${SESSION}: OK (processing)"
  fi
else
  # Fallback: OpenClaw wait-for-text.sh 不可用，退回 sleep+grep
  sleep 3
  after="$(capture_tail)" || {
    rc=$?
    echo "${SESSION}: CAPTURE_AFTER_FAILED rc=${rc}"
    echo "${SESSION}: HARD_BLOCK iTerm-only verify chain failed after send"
    exit 1
  }
  if printf "%s\n" "$after" | grep -qF "$MSG"; then
    retry_enter_and_check
  else
    echo "${SESSION}: OK"
  fi
fi
