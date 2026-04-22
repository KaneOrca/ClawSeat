task_id: GRIDHIST-028
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 可交互实现在 main/experimental 的 `iterm_panes_driver.py`（iTerm2 SDK），核心是 iTerm native panes + direct tmux attach，无嵌套 tmux。

## Subagent A — v0.4 TUI 源码（含 10-30 行关键代码摘录）

### Files added by 2a4ec71 (TUI 实现)
- `core/launchers/agent-launcher.sh` — unified launcher entrypoint
- `core/launchers/agent-launcher-common.sh` — shared AppleScript/TUI helpers
- `core/scripts/iterm_panes_driver.py` — **iTerm2 Python API N-panel driver（核心六宫格实现）**
- `core/scripts/agent_admin_window.py` — `build_monitor_layout` for nested-tmux N-panel with @seat labels
- `core/tui/install_wizard.py`, `ancestor_brief.py`, `machine_view.py`, `__init__.py`
- `core/skills/clawseat-ancestor/SKILL.md`
- 6 test files

### Files removed by f846625（被移除的 TUI）
- `core/tui/install_wizard.py`
- `core/scripts/install_complete.py`, `generate_ancestor_brief.py`
- `core/skills/clawseat-install/scripts/cs_init.py`, `resolve_auth_mode.py`
- `core/skills/clawseat-install/references/install-flow.md`, `ancestor-runbook.md`
- `docs/INSTALL_GUIDE.md`, `docs/install/gotchas-for-install-agents.md`, `docs/review/ancestor-phase2-review-packet.md`
- `examples/starter/install-config.toml.example`

### TUI launcher 核心代码（`iterm_panes_driver.py`）

**Primary mechanism: iTerm2 Python API (no nested tmux)**

```python
_LAYOUT_RECIPES = {
    6: [(0, True), (1, True), (0, False), (1, False), (2, False)],
    # splits: pane0 right, pane1 right, pane0 below, pane1 below, pane2 below → 2x3 grid
}

for step_idx, (parent_idx, vertical) in enumerate(_LAYOUT_RECIPES[n]):
    new_pane = await parent.async_split_pane(vertical=vertical)
    sessions.append(new_pane)

for session, spec in zip(sessions, panes):
    await session.async_send_text(command + "\n")  # e.g. "tmux attach -t =install-memory-claude\n"
```

**Secondary mechanism (nested tmux, 带 ergonomics 修复): `agent_admin_window.py`**

```python
# monitor_attach_command wraps attach so TMUX is unset:
def monitor_attach_command(session: str) -> str:
    return f"exec env -u TMUX tmux attach -t {shlex.quote(session)} || exec $SHELL -l"

# Outer prefix rebound to C-a so C-b reaches inner session directly:
tmux set-option -t <monitor> prefix C-a
tmux set-option -t <monitor> prefix2 None
tmux set-option -t <monitor> focus-events on
tmux set-window-option -t <monitor>:0 xterm-keys on
tmux set-option -t <monitor> pane-border-status top
tmux set-option -t <monitor> pane-border-format " #{?@seat,#{@seat},#{pane_title}} "
```

### How it achieved direct interactivity

**两种机制并存于同一 commit：**

1. **`iterm_panes_driver.py`（主路径）**：使用 iTerm2 Python SDK 的 `async_split_pane` 创建 N 个原生 iTerm panes，每个 pane 通过 `async_send_text` 发送 `tmux attach -t <session>\n`。**单层 attach** — iTerm pane 是直接 tmux client，无 tmux-in-tmux，无双层 multiplex。

2. **`agent_admin_window.py`（nested tmux 路径）**：创建外层 tmux monitor session，内嵌 N 个 pane，每个 pane 运行 `env -u TMUX tmux attach -t <inner>`。通过将外层 prefix 从 Ctrl+B 重绑定到 Ctrl+A，使 Ctrl+B 直达内层 session — 无需 double-prefix。

---

## Subagent B — 候选 branch 列表

### 结论：没有独立的"六宫格 branch"

可交互六宫格实现在 **main 和 experimental 共有的文件**中：

| 文件 | 位置 | 机制 |
|------|------|------|
| `iterm_panes_driver.py` | `core/scripts/` | iTerm2 Python SDK，原生 panes + direct tmux attach |
| `agent_admin_window.py` | `core/scripts/` | nested tmux with Ctrl+A prefix rebind |

### 跨 branch 扫描结果

| 关键词 | 匹配文件 |
|--------|---------|
| `split-window` | `core/scripts/agent_admin_window.py` (所有 branch) |
| `iTerm` / `iterm` | `core/scripts/iterm_panes_driver.py`, `iterm_tmux_selftest.py` (main + experimental) |
| `tiled` | `core/scripts/agent_admin_window.py` (line 434) |

**无任何 claude/* 分支包含独立的六宫格实现**。所有候选实现均在 main/experimental 的共享代码中。

---

## Subagent C — 当前实现 vs 历史实现对比 + 迁移建议

### 当前 `launch-grid.sh` 分析

**`launch-grid.sh` 在当前代码库中不存在**。六宫格 monitor 通过 `agent_admin_window.build_monitor_layout()` 构建，机制：
1. 通过 `tmux new-session` 创建 monitor session
2. 每个 pane 通过 `tmux send-keys` 注入 `exec env -u TMUX tmux attach -t <session> || exec $SHELL -l`
3. 这是 **nested tmux attach**：外层 tmux session 的每个 pane 运行一个 `tmux attach` 子进程连接到 engineer session

**broken 的具体原因**：
- **Prefix 冲突**：外层 monitor 重绑定 prefix 到 Ctrl+A，但内层 engineer session 使用默认 Ctrl+B，无法统一
- **Scrollback 隔离**：历史属于内层 client，外层 `capture-pane` 读不到内层 history
- **Mouse event routing**：`TMUX=...` 设置时 mouse 事件被外层 tmux server 消费，不转发给内层 client
- **Focus events**：`focus-events on` 在外层生效但事件被外层 server 消费，不传播到内层
- **PTY 不标准**：`exec env -u TMUX tmux attach` 继承非标准 PTY，导致 resize/pts 不匹配

### v0.4 TUI 的解决方式

使用 `core/scripts/iterm_panes_driver.py` — **iTerm2 原生 pane driver**：
- 用 iTerm2 Python SDK 的 `async_split_pane` 创建原生 iTerm splits
- 每个 pane 通过 `async_send_text` 发送 `tmux attach -t <session>\n` 到 pane 的**原生 PTY**
- **关键**：iTerm window 本身**不是 tmux**，只是普通 terminal emulator
- 每个 pane 的 `tmux attach` 是 engineer tmux server 的直接 client
- Prefix、mouse、scrollback、focus events 全部正常，因为每个 pane 有真实 PTY

Driver 自己**不调用任何 tmux 命令**（`test_iterm_panes_driver.py::test_driver_source_does_not_call_tmux` 验证）。

### 迁移建议（架构层面）

| 步骤 | 操作 |
|------|------|
| 1 | 将 `build_monitor_layout` 的 tmux-pane 布局输出转换为 `iterm_panes_driver` 的 JSON payload: `{"title": project.name, "panes": [{"label": engineer_id, "command": "tmux attach -t '<session>'"}]}` |
| 2 | 调用 `python3 core/scripts/iterm_panes_driver.py` 并 pipe JSON payload — Driver 处理 iTerm window 创建、split、label 命名和命令注入，全部通过 iTerm SDK |
| 3 | 保留 `agent_admin_window.py` 的 tmux session 管理（create/kill/list）— 这些仍需要 |
| 4 | 只把 **viewport/布局层** 从 nested tmux 切换到 iTerm native panes |
| 5 | 非 iTerm 环境 fallback：使用 `tmux new-window` + 直接运行 seat 进程（不用 nested attach），或用 `tmux link-window` 排列已有 windows |

**核心原则**：Terminal emulator（iTerm）拥有 pane/split 布局；tmux 只拥有 session 管理（create/attach/kill）。当前 v0.5 颠倒了这一点 — tmux 同时管理 session 和 layout。修复方向：tmux 管 session，iTerm 管 viewport。

---

## 最终推荐

**无需 cherry-pick — 实现在 main/experimental 共享代码中，直接可用。**

| 组件 | 路径 | 状态 |
|------|------|------|
| iTerm2 pane driver | `core/scripts/iterm_panes_driver.py` | 存在于 main 和 experimental，内容相同 |
| Nested tmux monitor (broken) | `core/scripts/agent_admin_window.py::build_monitor_layout` | 存在但有问题 |
| 已有测试 | `tests/test_iterm_panes_driver.py`, `tests/test_monitor_layout_n_panes.py` | 已有 |

**下一步**：将 `launch-grid.sh`（或等效的调用点）改为调用 `iterm_panes_driver.py`，传入 engineer sessions 列表作为 JSON payload，而不是走 `build_monitor_layout` 的 nested tmux 路径。
