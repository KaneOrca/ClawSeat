#!/bin/bash
# 激活 Claude Desktop 并点击输入框获取焦点
osascript -e 'tell application "Claude" to activate' 2>/dev/null || true
sleep 2
/tmp/mouseutil click 765 1241 2>/dev/null || true
