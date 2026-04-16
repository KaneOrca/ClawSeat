#!/bin/bash
# 点击输入框 + 写入剪贴板 + Edit→Paste 粘贴（通过菜单绕过输入法）
MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "Usage: msg_paste.sh \"message\""
  exit 1
fi
/tmp/mouseutil click 765 1241 2>/dev/null || true
sleep 0.5
printf '%s' "$MSG" | pbcopy
sleep 0.3
osascript << 'EOF' 2>/dev/null || true
tell application "System Events"
    tell process "Claude"
        click menu item "Paste" of menu "Edit" of menu bar 1
    end tell
end tell
EOF
