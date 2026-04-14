# ClawSeat 安装指南

ClawSeat 不依赖 cartooner 即可运行。用户只需 OpenClaw + Claude Code CLI + python3.11+ / tmux / 可选 iTerm2。

如果你是在让 agent 自动帮忙安装 ClawSeat，优先加载 `clawseat-install` skill；它会按这份指南的标准流程执行 preflight、bootstrap 和首次启动。

## 用户与 Agent 交互模式

- agent 默认自动执行：环境检查、preflight、starter profile 准备、bootstrap、console 校验
- agent 必须明确告知：当前是在 `preflight`、`bootstrap`、`koder` 启动，还是等待首次 onboarding
- agent 必须停下来交给用户的步骤：
  - Claude OAuth / `claude --auth`
  - workspace trust
  - permissions / bypass prompts
  - 当前宿主环境不支持 PTY/tmux，需要换到真实终端继续
- 安装阶段默认只拉起 `koder`；`planner` 和其他 specialist seat 仍需按 frontstage 规则显式确认

---

## 环境依赖

| 依赖 | 版本 | 说明 |
|------|------|------|
| python3 | ≥ 3.11 | 内置 `tomllib` 标准库 |
| tmux | 最新版 | session 管理 |
| OpenClaw | 最新版 | 主控入口 |
| Claude Code CLI | 最新版 | Agent runtime |
| iTerm2 | 可选 | 终端仿真器，提供更丰富的 tmux 集成体验 |

> **注意**：ClawSeat 使用 `tomllib`（Python 3.11+ 内置），不依赖 `tomli`。如果使用 Python < 3.11，preflight 检查会报告 HARD_BLOCKED。

---

## iTerm-only 启动前检查

默认 `clawseat` 运行链路走 iTerm-only。请在首次启动前先确认：

1) iTerm 可脚本化

```bash
osascript -e 'tell application "iTerm2" to get name of windows'
```

若弹出 AppleScript 授权提示，请在「系统设置」→「隐私与安全性」→「自动化」里允许该客户端控制 iTerm。

2) `tmux` 二进制可被路径查找到

```bash
command -v tmux
tmux -V
tmux list-sessions
```

3) iTerm 与 clawseat 的最小权限路径可用

```bash
python3 "$CLAWSEAT_ROOT/core/preflight.py"
```

4) 典型阻断修复

```bash
# iTerm 无法被 AppleScript 识别
osascript -e 'tell application "iTerm2" to activate'

# tmux 命令不存在
brew install tmux

# tmux socket 被占用或短暂异常
tmux list-sessions
```

`send-and-verify` 与 `check-engineer-status` 会在无法解析 `tmux` 时给出明确错误（如 `TMUX_MISSING` / `TMUX_CAPTURE_FAILED`），并在 iTerm-only 环境下优先建议恢复终端路径与 AppleScript 授权。

---

## 安装步骤

### 1. 确认 ClawSeat 路径

```bash
export CLAWSEAT_ROOT=/path/to/ClawSeat
# 示例：
export CLAWSEAT_ROOT="$HOME/coding/ClawSeat"
```

路径约定：
- `{CLAWSEAT_ROOT}`：ClawSeat 仓库根目录
- `~`：当前用户主目录

### 2. 获取 starter profile

ClawSeat 提供通用 starter profile，位于：

```
{CLAWSEAT_ROOT}/examples/starter/profiles/starter.toml
```

该 profile：
- 仅定义 `koder`（前台入口）
- 不依赖 cartooner
- 可直接被 `bootstrap_harness.py` 使用

将 starter profile 复制到项目目录：

```bash
PROJECT_NAME=my-project
mkdir -p ~/.agents/tasks/$PROJECT_NAME
cp $CLAWSEAT_ROOT/examples/starter/profiles/starter.toml /tmp/$PROJECT_NAME-profile-dynamic.toml
```

> `ensure_clawseat_profile()` 默认查找 `/tmp/{project}-profile-dynamic.toml`。如需其他位置，传入 `--profile` 参数。

### 3. 替换 profile 中的占位符

编辑 `/tmp/my-project-profile-dynamic.toml`，将所有 `my-project` 替换为实际项目名：

```bash
sed -i '' 's/my-project/YOUR_PROJECT_NAME/g' /tmp/my-project-profile-dynamic.toml
```

关键占位符：
- `project_name`：项目标识
- `tasks_root`：`~/.agents/tasks/{project}`
- `workspace_root`：`~/.agents/workspaces/{project}`
- `heartbeat_receipt`：`~/.agents/workspaces/{project}/koder/HEARTBEAT_RECEIPT.toml`
- `planner_brief_path`：PLANNER_BRIEF.md 位置

### 4. 创建项目任务目录

```bash
PROJECT=YOUR_PROJECT_NAME
mkdir -p ~/.agents/tasks/$PROJECT
mkdir -p ~/.agents/tasks/$PROJECT/patrol
mkdir -p ~/.agents/tasks/$PROJECT/planner
mkdir -p ~/.agents/sessions/$PROJECT
mkdir -p ~/.agents/workspaces/$PROJECT
touch ~/.agents/tasks/$PROJECT/PROJECT.md
touch ~/.agents/tasks/$PROJECT/TASKS.md
touch ~/.agents/tasks/$PROJECT/STATUS.md
```

### 5. 运行 preflight 检查

```bash
python3 $CLAWSEAT_ROOT/core/preflight.py
```

预期输出：`[PASS]` 表示所有检查通过；`[HARD_BLOCKED]` 需先修复对应问题。

常见 HARD_BLOCKED 及修复：

| 检查项 | 原因 | 修复 |
|--------|------|------|
| CLAWSEAT_ROOT | 环境变量未设置 | `export CLAWSEAT_ROOT=$HOME/coding/ClawSeat` |
| python3 | 版本 < 3.11 | `brew install python3` |
| tomllib | Python < 3.11 | 升级 Python 至 3.11+ |
| tmux | 未安装 | `brew install tmux` |
| tmux_server | tmux 未运行 | `tmux new-session -d` |
| repo_integrity | 缺少核心文件 | 确认 CLAWSEAT_ROOT 指向正确目录 |

### 6. Bootstrap

```bash
python3 $CLAWSEAT_ROOT/shells/openclaw-plugin/openclaw_bootstrap.py
```

或使用 bootstrap_harness.py（需要先准备 profile）：

```bash
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --project-name my-project \
  --start
```

`--start` 参数：启动 koder（前台）seat 并打开项目窗口。

---

## 首次 Onboarding

ClawSeat seat 首次启动时需要人工完成以下步骤：

### OAuth 登录

Claude Code CLI 会提示 OAuth 流程。按屏幕指示完成授权。

### Workspace Trust

首次在新 workspace 中运行 Claude Code 时，需确认 workspace 信任：

```
Do you trust this workspace? [y/N]
```

输入 `y` 确认。

### Bypass Permissions

如果 CLI 提示权限不足：

```
Authorization required. Run: claude --auth
```

按提示完成认证。

完成上述步骤后，operator（koder）接管后续流程：heartbeat 配置、dispatch、patrol 等。

---

## OpenClaw 接入方式

ClawSeat 通过 OpenClaw 的 koder seat 与用户交互。确保 OpenClaw 已安装并配置了 `koder` agent：

```bash
# 确认 OpenClaw 可用
openclaw --version

# koder workspace 已包含 clawseat-koder-frontstage skill
ls ~/.openclaw/workspace-koder/skills/clawseat-koder-frontstage/
```

OpenClaw 启动后，koder seat 即为用户可见的前台入口。

---

## Seat 启动顺序

ClawSeat 多 seat 采用渐进式启动：

```
koder（前台）→ planner（规划）→ specialist（专家）
```

### 仅启动 koder（前台）

```bash
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --seat koder
```

### 启动 planner

```bash
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --seat planner
```

> 首次启动 planner 前，koder 会显示确认信息（harness/profile、目标 seat 和角色、工具/认证方式），需用户批准后才会实际启动。

### 添加 builder / reviewer

在 profile 的 `[seat_roles]` 中添加 `builder-1`/`reviewer-1` 等，并在需要时启动：

```bash
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --seat builder-1
```

---

## 常用命令

```bash
# 环境预检
python3 $CLAWSEAT_ROOT/core/preflight.py

# Bootstrap
python3 $CLAWSEAT_ROOT/shells/openclaw-plugin/openclaw_bootstrap.py

# 启动 seat
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py \
  --profile /tmp/my-project-profile-dynamic.toml --seat koder

# 查看团队状态
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/render_console.py \
  --profile /tmp/my-project-profile-dynamic.toml

# 分发任务
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/dispatch_task.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --source koder --target planner --task-id TASK-001 --title "任务标题" --objective "任务目标"

# 完成任务
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/complete_handoff.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --source planner --target koder --task-id TASK-001 --title "完成" --summary "摘要"
```

---

## Profile 路径约定

Profile 中的路径支持两种可移植占位符：

- `{CLAWSEAT_ROOT}`：展开为 ClawSeat 仓库根目录（由 `_common.py` 的 profile loader 处理）
- `~`：通过 `Path.expanduser()` 展开为主目录

示例：

```toml
repo_root = "{CLAWSEAT_ROOT}"
workspace_root = "~/.agents/workspaces/my-project"
agent_admin = "{CLAWSEAT_ROOT}/core/scripts/agent_admin.py"
```

这使 profile 文件在不同机器间可移植，无需硬编码绝对路径。
