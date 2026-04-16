#!/bin/bash
# send-and-verify.sh — 发送指令并验证是否成功
# 用法: ./send-and-verify.sh <session> "<message>"
#
# 发送后等 3 秒检查快照，如果指令还卡在输入框（未提交），自动补发 Enter

SESSION="$1"
MSG="$2"
TMUX_BIN=/opt/homebrew/bin/tmux

if [ -z "$SESSION" ] || [ -z "$MSG" ]; then
  echo "Usage: send-and-verify.sh <session> \"<message>\""
  exit 1
fi

# 1. 发送前快照
BEFORE=$(env -u TMUX "$TMUX_BIN" capture-pane -t "$SESSION" -p 2>/dev/null | tail -5)

# 2. 发送文本
env -u TMUX "$TMUX_BIN" send-keys -t "$SESSION" "$MSG"
sleep 1
env -u TMUX "$TMUX_BIN" send-keys -t "$SESSION" Enter
sleep 3

# 3. 发送后快照
AFTER=$(env -u TMUX "$TMUX_BIN" capture-pane -t "$SESSION" -p 2>/dev/null | tail -5)

# 4. 验证：如果消息还在输入行（未被处理），补发 Enter
if echo "$AFTER" | grep -qF "$MSG"; then
  # 消息还在屏幕上的输入区域——可能没提交
  # 再发一次 Enter
  sleep 1
  env -u TMUX "$TMUX_BIN" send-keys -t "$SESSION" Enter
  sleep 2

  # 第二次检查
  AFTER2=$(env -u TMUX "$TMUX_BIN" capture-pane -t "$SESSION" -p 2>/dev/null | tail -5)
  if echo "$AFTER2" | grep -qF "$MSG"; then
    echo "$SESSION: RETRY_FAILED — message may not have been received"
    exit 1
  else
    echo "$SESSION: OK (retry Enter)"
  fi
else
  echo "$SESSION: OK"
fi
