# ClawSeat 安装指南

## 快速安装（OpenClaw 用户）

告诉你的 OpenClaw agent：

```
克隆并安装 ClawSeat：
git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat
# Phase 0：安装 agent 无关的 skill 符号链接
CLAWSEAT_ROOT=~/.clawseat python3 ~/.clawseat/shells/openclaw-plugin/install_bundled_skills.py
# Phase 3 overlay 在 install flow 的 Phase 3 阶段由 agent 执行（需 --agent <name>）
然后读 ~/.openclaw/skills/clawseat-install/SKILL.md 继续
```

agent 会自动完成剩余步骤：init_koder → preflight → bootstrap → 配置 seat → 启动 planner。

---

## 环境依赖

| 依赖 | 版本 | 安装方式 | 必需？ |
|------|------|---------|--------|
| Python | ≥ 3.11 | `brew install python@3.12` 或 python.org | ✅ HARD_BLOCKED |
| tmux | 最新 | `brew install tmux` | ✅ HARD_BLOCKED |
| Node.js | ≥ 22 | `brew install node` | ✅ OpenClaw 需要 |
| OpenClaw | 最新 | `npm install -g openclaw` | ✅ 宿主运行时 |
| gstack | 最新 | 见下方 | ⚠️ specialist seats 需要 |
| Claude Code CLI | 最新 | `npm install -g @anthropic-ai/claude-code` | ⚠️ claude seats 需要 |
| Codex CLI | 最新 | `npm install -g @openai/codex` | ⚠️ codex seats 需要 |
| lark-cli | 最新 | `brew install larksuite/cli/lark-cli` | 可选（飞书桥接） |
| iTerm2 | 最新 | `brew install --cask iterm2` | 可选（窗口管理） |

### 安装 gstack

gstack 提供 builder、reviewer、qa、designer 的核心工作技能。没有它，specialist seats 可以启动但缺少关键能力。

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.gstack/repos/gstack
cd ~/.gstack/repos/gstack && ./setup
```

> `preflight` 会自动检测 gstack 是否安装，并给出安装命令。

### 没有 Homebrew？

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

## 安装路径

### 路径 A：OpenClaw 安装（推荐）

```bash
# 1. Clone
git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat
export CLAWSEAT_ROOT="$HOME/.clawseat"

# 2. Phase 0：安装 agent 无关的 skill 符号链接
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_bundled_skills.py"

# 3. 在 OpenClaw 里说 "安装 ClawSeat" 或读 clawseat-install skill
# agent 会自动执行 5 阶段流程：
#   Phase 1 memory seat → Phase 2 查询目标 agent → Phase 3 koder overlay → preflight → bootstrap → 配置 → 启动 planner
# Phase 3: python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_koder_overlay.py" --agent <name>
```

### 路径 B：本地 Claude Code / Codex

```bash
# 1. Clone
git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat
export CLAWSEAT_ROOT="$HOME/.clawseat"

# 2. 安装入口 skill
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"

# 3. 在 Claude Code 里输入
/cs
```

---

## 安装流程详解（OpenClaw 路径）

```
1a. install_bundled_skills.py  [Phase 0 — agent 无关]
    └── 创建 skill symlinks 到 ~/.openclaw/skills/
    └── 检查 gstack + lark-cli 外部依赖
    └── exit 0=全部成功, 2=外部依赖缺失

1b. install_koder_overlay.py --agent <name>  [Phase 3 — 按 agent 叠加]
    └── 将 koder 模板写入 ~/.openclaw/workspace-<name>/skills/
    └── --dry-run 预览; --openclaw-home 覆盖路径
    └── exit 2=缺少 --agent; exit 3=目标 workspace 不存在
    └── 在 Phase 2 通过 memory 确认 <name> 后执行

2. init_koder.py --workspace <koder工作区> --project install
   └── 写入 IDENTITY.md, SOUL.md, TOOLS.md, MEMORY.md, AGENTS.md
   └── 写入 WORKSPACE_CONTRACT.toml（含 feishu_group_id）
   └── 创建 koder skill symlinks

3. preflight.py install
   └── 检查 Python, tmux, repo integrity, profile, skills
   └── 自动修复: tmux server, dynamic profile, session dir

4. bootstrap_harness.py --profile <profile> --project-name install
   └── 验证 skill registry
   └── 创建 planner/builder/reviewer/qa/designer workspaces
   └── 写入 WORKSPACE_CONTRACT.toml, AGENTS.md, TODO.md

5. 用户配置每个 seat 的 tool/auth/provider

6. start_seat.py --seat planner --confirm-start
   └── 启动 tmux session
   └── 检测 onboarding 状态
   └── seed secrets

7. dispatch_task.py 派发任务给 planner
   └── 写 TODO.md + TASKS.md + handoff receipt
   └── send-and-verify.sh 通知 planner
```

---

## Profile 路径

Profile 持久化存储在 `~/.agents/profiles/{project}-profile-dynamic.toml`。

首次安装时自动从 `examples/starter/profiles/install.toml` 种子化。

Profile 中支持两种可移植占位符：
- `{CLAWSEAT_ROOT}` → ClawSeat 仓库根目录
- `~` → 用户主目录

---

## 更新后刷新

`git pull` 后必须刷新所有 seat 的 workspace 文件：

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py"
```

零参数，自动检测 project、profile、koder workspace、feishu group ID。

---

## Seat 启动顺序

```
koder（前台，OpenClaw agent）→ planner → specialist seats
```

- koder 不创建 tmux session（OpenClaw agent 就是 koder）
- planner 和 specialist seats 在 tmux 中运行
- 每个 seat 启动前必须由用户确认 tool/auth/provider

---

## 飞书桥接

1. 安装 lark-cli：`brew install larksuite/cli/lark-cli`
2. 配置认证：`lark-cli config init --new`（按提示完成）
3. 用户登录：`lark-cli auth login`
4. 安装时提供飞书群 ID（`oc_xxx` 格式）
5. planner 通过 `OC_DELEGATION_REPORT_V1` 协议以用户身份向群发送消息

---

## 常用命令

```bash
# 环境预检
python3 "$CLAWSEAT_ROOT/core/preflight.py" install

# Skill 验证
python3 "$CLAWSEAT_ROOT/core/scripts/skill_manager.py" check

# 查看团队状态
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/render_console.py" \
  --profile ~/.agents/profiles/install-profile-dynamic.toml

# 分发任务
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/dispatch_task.py" \
  --profile ~/.agents/profiles/install-profile-dynamic.toml \
  --source koder --target planner --task-id TASK-001 \
  --title "任务标题" --objective "任务目标"

# 刷新 workspace（git pull 后）
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py"

# 运行测试
python3 -m pytest tests/ -v
python3 core/skills/gstack-harness/scripts/selftest.py
python3 core/scripts/iterm_tmux_selftest.py
```

---

## Starter Profiles

| Profile | 用途 |
|---------|------|
| `examples/starter/profiles/install.toml` | canonical 安装项目（koder + planner + builder + reviewer） |
| `examples/starter/profiles/starter.toml` | 仅 koder 入口 |
| `examples/starter/profiles/full-team.toml` | 完整六人团队 |
