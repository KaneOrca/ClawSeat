---
name: agent-monitor
description: 观察、联络、解阻电脑上正在运行的其他 ClawSeat seat（工程师、planner、koder）。适用于：查看各 seat 当前在做什么，向工程师 / planner 发消息，向 Claude Desktop 架构师发消息并截图确认。非适用：业务编码、任务分配、交付审查、修改项目源码。
---

# Agent Monitor

## 目标

统一三类能力：
- **observe**：观察 seat 当前状态
- **contact**：联络工程师、planner、架构师
- **unblock**：解除明确阻塞

## 外部依赖

### 状态识别脚本（ClawSeat 内置）

```bash
# 查看全部 seat 状态
${CLAWSEAT_ROOT}/core/shell-scripts/check-engineer-status.sh

# 指定会话
${CLAWSEAT_ROOT}/core/shell-scripts/check-engineer-status.sh <session-1> <session-2> ...
```

> `CLAWSEAT_ROOT` 由 ClawSeat 安装时写入环境变量。若未设置，运行 `clawseat env` 查看。

## skill 自带脚本

位于 `${CLAWSEAT_ROOT}/core/skills/agent-monitor/script/`：
- `send-and-verify.sh` — 发送指令并验证 tmux 已接收
- `tmux-send-delayed.sh` — 带延迟的 tmux 发送（适合 TUI 较慢的 seat）
- `msg_focus.sh` — 聚焦 Claude Desktop 输入框
- `msg_paste.sh` — 粘贴消息文本
- `msg_send.sh` — 提交消息
- `screenshot-to-feishu.sh` — 截图上传飞书

## 默认工作流

### 1. observe

```bash
${CLAWSEAT_ROOT}/core/shell-scripts/check-engineer-status.sh
```

当脚本结果不够时，再手动查看 tmux pane。

### 2. contact_tmux

向工程师或 planner 发消息时，优先使用：

```bash
DIR=${CLAWSEAT_ROOT}/core/skills/agent-monitor/script
bash $DIR/send-and-verify.sh <session> "message"
```

次选（TUI 较慢时）：

```bash
bash $DIR/tmux-send-delayed.sh <session> "message"
```

### 3. contact_architect

向 Claude Desktop 架构师发消息：

```bash
DIR=${CLAWSEAT_ROOT}/core/skills/agent-monitor/script
bash $DIR/msg_focus.sh && sleep 0.5 && bash $DIR/msg_paste.sh "[W] message" && sleep 0.5 && bash $DIR/msg_send.sh && sleep 1 && bash $DIR/screenshot-to-feishu.sh
```

规则：
- 必须 `[W]` 前缀
- 只发英文
- 发完必须截图确认给用户

### 4. unblock

在明确阻塞时，可执行：
- 补 Enter
- 发送确认或补充说明
- 转联络架构师或 planner

## 边界

这个 skill 不负责：
- 定义工程师职责
- 任务分配
- 审查交付
- 修改业务代码
- 维护 `check-engineer-status.sh` 本身

## 目录结构

```text
agent-monitor/
├── SKILL.md
└── script/
    ├── send-and-verify.sh
    ├── tmux-send-delayed.sh
    ├── msg_focus.sh
    ├── msg_paste.sh
    ├── msg_send.sh
    └── screenshot-to-feishu.sh
```
