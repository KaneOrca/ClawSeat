# TODO — PRECHECK-026 (grid 拉起可行性 + 新 INSTALL.md 草稿)

```
task_id: PRECHECK-026
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental worktree)
priority: P0
subagent-mode: REQUIRED — spawn 2 parallel subagents (A/B)
do-not-modify: Subagent A read-only; Subagent B may write draft only
```

## Context

Codex 正在写 `scripts/launch-grid.sh`，它需要在没有 project.toml 的情况下调用
`build_monitor_layout()`。我们需要提前验证这条路是否走得通，同时起草新的简化
INSTALL.md。

新安装流程已确认方向：
1. 自动装 tmux + iTerm2
2. `scripts/launch-grid.sh` → 六宫格打开，ancestor 格子里 CC bypass 启动
3. 用户 attach，ancestor 接管，自己跑 Phase-A（注册 project、拉其余 seat）

---

## Subagent A — build_monitor_layout() 无 project.toml 可行性

Read-only 分析：

1. 读 `core/scripts/agent_admin_window.py` 的 `build_monitor_layout(project, sessions)`
   - `project` 对象需要哪些字段？（`monitor_session`, `monitor_engineers`,
     `monitor_max_panes`, `repo_root`, `window_mode`, `name`）
   - 这些字段能不能用 Python dataclass/SimpleNamespace 伪造，不依赖 project.toml？

2. 读 `core/scripts/agent_admin.py` 的 `window` 子命令
   - 它是怎么构造 project/sessions 传给 `build_monitor_layout()` 的？
   - 是否必须先有注册的 project？

3. 给出结论：
   - **方案一**：launch-grid.sh 可以绕过 project.toml，直接 Python 伪造 project 对象调用
     `build_monitor_layout()` — 说明伪造的最小字段集
   - **方案二**：必须先 `agent_admin project create`，但可以在 launch-grid.sh 里自动做
   - **方案三**：完全不用 `build_monitor_layout()`，launch-grid.sh 自己用 tmux 命令
     手写分割逻辑（附最简 6 格分割命令）

---

## Subagent B — 新 INSTALL.md 草稿

基于以下已确认方向，起草新的 `docs/INSTALL.md`（覆盖现有文件的草稿，不要直接写入）：

**新流程**：
```
Prerequisites:
  P1. git clone ClawSeat → ~/ClawSeat
  P2. 自动检测并安装缺失依赖：
      - tmux（brew install tmux / apt install tmux）
      - iTerm2（仅 macOS，brew install --cask iterm2）
      - python3 ≥ 3.11
      - claude binary（提示用户装，不自动装）

Step 1: 拉起六宫格
  - 运行 scripts/launch-grid.sh（创建 6 个 session + monitor 网格）
  - ancestor 格子里 claude --dangerously-skip-permissions 自动启动
  - 告知用户：tmux attach -t clawseat-monitor 进入网格

Step 2: 用户 attach 进入 ancestor
  - ancestor 读取 CLAWSEAT_ANCESTOR_BRIEF 运行 Phase-A
  - Phase-A 包括：project 注册、env scan、runtime 选择、memory 启动、其余 seat 拉起

Step 3: 验收
  - ancestor 在 Feishu/CLI 发送 smoke report
  - STATUS.md phase=ready
```

草稿要求：
- 面向 agent 读者（执行者是 Claude Code，不是人类）
- 保持与现有文件风格一致（命令块 + Verify + Failure 格式）
- 覆盖 Prerequisites + Step 1~3 + Failure Modes + Resume
- 不超过 200 行
- 写到 `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DRAFT-INSTALL-026.md`（草稿位置，不覆盖正式文件）

---

## Deliverable

Write `DELIVERY-PRECHECK-026.md` in `/Users/ywf/ClawSeat/.agent/ops/install-nonint/`:

```
task_id: PRECHECK-026
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <one line>

## Subagent A — build_monitor_layout 可行性
<结论 + 推荐方案 + 最小代码片段>

## Subagent B — 新 INSTALL.md 草稿
<写入路径确认 + 关键设计决策说明>
```

Notify planner: "DELIVERY-PRECHECK-026 ready".
