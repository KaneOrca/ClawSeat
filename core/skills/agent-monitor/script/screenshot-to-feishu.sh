#!/bin/bash
# screenshot-to-feishu.sh
# 截取屏幕区域并发送到飞书 DM
#
# 用法:
#   ./screenshot-to-feishu.sh [消息文字]
#
# 默认输出: ${OPENCLAW_HOME:-$HOME/.openclaw}/workspace-warden/media/screenshot.jpg
# 截取区域: x=50, 从屏幕顶部到当前鼠标 Y 坐标, 宽=1300
#
# 依赖: cliclick (brew install cliclick)

# 固定截图区域参数
# x=400, y=0, 宽=850, 高=固定值
MOUSE_Y=1300

if [ -z "$MOUSE_Y" ]; then
    echo "无法获取鼠标位置，使用默认值 1250"
    MOUSE_Y=1250
fi

echo "鼠标 Y 坐标: $MOUSE_Y"

OUTPUT="${OPENCLAW_HOME:-$HOME/.openclaw}/workspace-warden/media/screenshot.jpg"
MSG="${1:-截图}"

# 确保目录存在
mkdir -p "$(dirname "$OUTPUT")"

# 截取屏幕: x=400, y=0, 宽=850, 高=MOUSE_Y (减少两侧干扰)
/usr/sbin/screencapture -x -D1 -R400,0,850,$MOUSE_Y -t jpg "$OUTPUT" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "截图已保存: $OUTPUT"
else
    echo "截图失败"
    exit 1
fi
