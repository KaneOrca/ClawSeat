# ClawSeat 安装指南

ClawSeat 不依赖 cartooner 即可运行。用户只需 OpenClaw + Claude Code CLI + python3.11+ / tmux / 可选 iTerm2。

如果你是在让 agent 自动帮忙安装 ClawSeat，优先加载 `clawseat-install` skill；它会按这份指南的标准流程执行 preflight、bootstrap、入口 skill 安装和首次启动。

## 安装后第一条指令：`/cs`

ClawSeat 安装完成后，推荐用户执行的第一条指令就是 `/cs`。

先在 shell 里把入口 skill 安装到本机 runtime：

```bash
export CLAWSEAT_ROOT="$HOME/coding/ClawSeat"
python3 $CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py
```

然后在 Claude Code 里输入：

```text
/cs
```

如果当前 runtime 以技能名而不是 slash command 形式调用，就使用 `$cs`。

`/cs` 会默认做这几件事：

- 创建或复用 canonical 项目 `install`
- 使用 `{CLAWSEAT_ROOT}/examples/starter/profiles/install.toml`
- 初始化 `koder / planner / builder-1 / reviewer-1` 工作区
- 自动恢复或拉起 `koder`
- 直接拉起 `planner`，让它接任后续安装链
- `qa-1` 不属于 `/cs` 首启固定拉起名单；只有当当前链路明确是 smoke / regression / 审批前复测时，才由 `planner` 拉起 `qa-1`
- planner 就绪后，frontstage 会继续要求用户提供飞书群 `group ID`；无需 `open_id`
- frontstage 在拿到 `group ID` 后，必须先确认这个群是绑定当前项目、切换到已有项目，还是用于创建新项目；不要把新群自动当成新项目
- 安装阶段结束后，应进入配置阶段：补齐项目绑定、Feishu 群绑定、provider 选择、API key、base URL / endpoint URL 等运行所需配置
- 一旦项目群绑定完成，planner 会优先使用 `OC_DELEGATION_REPORT_V1` 的 user-identity 回执作为主链路；旧的自动群广播只作为显式 opt-in 的兼容路径

这条入口不替代 `clawseat-install`；它只是把默认安装路径压缩成一条稳定的第一指令。

## 用户与 Agent 交互模式

- agent 默认自动执行：环境检查、preflight、starter profile 准备、bootstrap、console 校验
- agent 必须明确告知：当前是在 `preflight`、`bootstrap`、`koder` 启动，还是等待首次 onboarding
- agent 必须停下来交给用户的步骤：
  - Claude OAuth / `claude --auth`
  - workspace trust
  - permissions / bypass prompts
  - 当前宿主环境不支持 PTY/tmux，需要换到真实终端继续
- 手工安装阶段默认只拉起 `koder`；`planner` 和其他 specialist seat 仍需按 frontstage 规则显式确认
- `/cs` 是唯一例外：它本身就视为用户已明确要求创建 `install` 项目并拉起 `planner`
- 当链路明确是测试、验证、smoke 或回归时，frontstage 应让 `planner` 额外拉起 `qa-1`；`qa-1` 默认不跟随 `/cs` 首启自动启动
- 配置阶段分两段：先做配置录入（项目/群/API key/URL/provider），再做配置验证
- `qa-1` 介入的是配置验证，不是明文 secret 录入；涉及 Feishu bridge、新 API key、key rotation、base URL / endpoint 修改、auth_mode / provider 切换时，默认应让 `planner` 视风险拉起 `qa-1`
- 当用户给出 Feishu `group ID` 时，frontstage 必须先完成“项目绑定确认”：绑定当前项目、切换到已有项目，或创建新项目；未确认前不要直接开始 planner 执行链
- 当阶段收尾返回前台时，koder 需要先读 linked delivery trail，再更新 `PROJECT.md` / `TASKS.md` / `STATUS.md`，然后再向用户总结结果

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
osascript -e 'tell application "iTerm" to get name of windows'
```

若弹出 AppleScript 授权提示，请在「系统设置」→「隐私与安全性」→「自动化」里允许该客户端控制 iTerm。

> 说明：ClawSeat 已兼容 `iTerm` 与 `iTerm2` 两种 AppleScript 应用名；若你安装的是旧别名，`iTerm2` 也可用。优先确认 `iTerm` 可用。

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
osascript -e 'tell application "iTerm" to activate'

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

### 2. 选择 starter profile

ClawSeat 现在提供三种通用 starter profile：

| Profile | 用途 |
|---------|------|
| `{CLAWSEAT_ROOT}/examples/starter/profiles/starter.toml` | 仅初始化 `koder`，适合先搭前台入口 |
| `{CLAWSEAT_ROOT}/examples/starter/profiles/install.toml` | canonical `/cs` 安装项目：创建 `koder / planner / builder-1 / reviewer-1` 工作区 |
| `{CLAWSEAT_ROOT}/examples/starter/profiles/full-team.toml` | 一次性创建 `koder / planner / builder-1 / reviewer-1 / qa-1 / designer-1` 六个个人工作区 |

两者都不依赖 cartooner，都可以直接被 `bootstrap_harness.py` 使用。

复制你要的 profile：

```bash
PROJECT_NAME=my-project
PROFILE_TEMPLATE=$CLAWSEAT_ROOT/examples/starter/profiles/starter.toml
# canonical /cs install 项目时改成：
# PROFILE_TEMPLATE=$CLAWSEAT_ROOT/examples/starter/profiles/install.toml
# 六席初始化时改成：
# PROFILE_TEMPLATE=$CLAWSEAT_ROOT/examples/starter/profiles/full-team.toml

mkdir -p ~/.agents/tasks/$PROJECT_NAME
cp $PROFILE_TEMPLATE /tmp/$PROJECT_NAME-profile-dynamic.toml
```

> `ensure_clawseat_profile()` 默认查找 `/tmp/{project}-profile-dynamic.toml`。如需其他位置，传入 `--profile` 参数。

### 3. 替换 profile 中的占位符

编辑 `/tmp/my-project-profile-dynamic.toml`，将所有 `my-project` 替换为实际项目名：

```bash
sed -i '' 's/my-project/YOUR_PROJECT_NAME/g' /tmp/my-project-profile-dynamic.toml
```

> `install.toml` 是固定给 canonical `install` 项目用的，通常不需要替换项目名；`/cs` 会直接复用它生成 `/tmp/install-profile-dynamic.toml`。

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
python3 $CLAWSEAT_ROOT/core/preflight.py $PROJECT
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

`--start` 参数：启动 `koder`（前台）seat 并打开项目窗口。

如果 profile 使用的是 `install.toml`：
- bootstrap 会创建 `koder / planner / builder-1 / reviewer-1` 四个工作区
- `--start` 仍只自动启动 `koder`
- bootstrap 阶段就应为这些 seat 生成完整模板：workspace guide、`WORKSPACE_CONTRACT.toml`、`repos/` 软链接、空 `TODO.md`
- `/cs` 会在 bootstrap 之后继续显式启动 `planner`

如果 profile 使用的是 `full-team.toml`：
- bootstrap 会一次性创建六个 seat 的个人工作区
- 但仍只自动启动 `koder`
- 六个 seat 的 workspace 模板与空 inbox 也应在 bootstrap 阶段全部就绪，而不是等第一次派发任务时才补
- `planner` 和其他 specialist seat 需要后续显式启动

### `install` 项目快速初始化

如果你的目标是直接进入默认安装链，最短路径就是：

```bash
export CLAWSEAT_ROOT="$HOME/coding/ClawSeat"
python3 $CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py
```

随后在 Claude Code 中输入：

```text
/cs
```

这会复用或创建 canonical `install` 项目，并直接拉起 `planner`。

### 六人工位快速初始化

如果你的目标就是“快速准备完整团队工作区”，最短路径是直接用 `full-team.toml`：

```bash
PROJECT=my-project
PROFILE=/tmp/$PROJECT-profile-dynamic.toml

cp $CLAWSEAT_ROOT/examples/starter/profiles/full-team.toml $PROFILE
sed -i '' "s/my-project/$PROJECT/g" $PROFILE

python3 $CLAWSEAT_ROOT/core/preflight.py $PROJECT
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py \
  --profile $PROFILE \
  --project-name $PROJECT \
  --start
```

完成后会生成：
- `~/.agents/workspaces/$PROJECT/koder`
- `~/.agents/workspaces/$PROJECT/planner`
- `~/.agents/workspaces/$PROJECT/builder-1`
- `~/.agents/workspaces/$PROJECT/reviewer-1`
- `~/.agents/workspaces/$PROJECT/qa-1`
- `~/.agents/workspaces/$PROJECT/designer-1`

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

OpenClaw 启动后，koder seat 即为用户可见的前台入口。若当前环境已经装好 `cs` 入口 skill，仍推荐先让用户执行 `/cs` 来初始化 canonical `install` 项目。

---

## Seat 启动顺序

ClawSeat 多 seat 采用渐进式启动：

```
koder（前台）→ planner（规划）→ specialist（专家）
```

canonical `/cs` 路径等价于：先确保 `koder` 可用，再直接推进到 `planner`。

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

python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --seat planner \
  --confirm-start
```

> 第一次执行会先输出 launch summary；确认后，需要带 `--confirm-start` 再执行一次才会真正启动。

### 启动 builder / reviewer / qa / designer

如果使用的是 `full-team.toml`，这些 seat 已经预置；如果使用的是 `starter.toml`，先在 profile 里补齐 `seats` 和 `[seat_roles]`。

启动时同样遵循“先 review launch summary，再 confirm”：

```bash
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --seat builder-1

python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py \
  --profile /tmp/my-project-profile-dynamic.toml \
  --seat builder-1 \
  --confirm-start
```

---

## 常用命令

```bash
# 环境预检
python3 $CLAWSEAT_ROOT/core/preflight.py my-project

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
