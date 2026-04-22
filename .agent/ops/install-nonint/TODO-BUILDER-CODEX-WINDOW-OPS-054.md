# TODO — WINDOW-OPS-054 (agent_admin window open-grid / open-memory)

```
task_id: WINDOW-OPS-054
source: planner
reply_to: planner
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P2
subagent-mode: OPTIONAL (单 agent)
scope: 补齐"恢复/重开 project iTerm 布局"的 canonical 命令
queued: 在 FEISHU-AUTH-053 之后
```

## Context

smoke02 暴露了架构 gap：项目 iTerm 六宫格窗口**只在 install.sh Step 7 首次创建**，后续窗口丢失（operator 关窗 / iTerm 崩溃 / 机器重启）后**没有 canonical 命令 recover**。smoke01-ancestor 手动拼 iterm_panes_driver.py payload 代工，是一次性 hack。

FEISHU-AUTH-053 R1 已扩展为 generic `seed_user_tool_dirs()` 把 iTerm2 socket / plist symlink 进 sandbox HOME，sandbox 里跑 iterm2 Python API 就能 work，但**缺 canonical CLI**。

## 修复

### 新增 `agent_admin window open-grid <project>`

`core/scripts/agent_admin.py` + `agent_admin_commands.py` + `agent_admin_window.py` 新增命令：

```
agent_admin window open-grid <project>
  [--recover]           # 已有 clawseat-<project> 窗口就 focus，不重开
  [--open-memory]       # 顺便开 machine-memory-claude 独立窗口（如未开）
```

**行为**：
1. 读 project record（`~/.agents/projects/<project>/project.toml`）拿 seat roster
2. 拼 iterm_panes_driver.py payload：
   - pane 1 = `ancestor`: `tmux attach -t '=<project>-ancestor'`（或 session-name resolved）
   - pane 2-6 = 每个非 ancestor seat: `bash scripts/wait-for-seat.sh <project>-<seat>`（SPAWN-049 4e prefix match）
3. `--recover` 模式：先 osascript 查 `clawseat-<project>` 窗口是否在，在就 focus 不重开
4. `--open-memory`：额外拼 memory_payload + 单独调 iterm_panes_driver 开独立窗口
5. stdout 打印 new window_id（osascript 返回值）或 "reused"

**payload 生成**：复用 install.sh 的 grid_payload 逻辑 + wait-for-seat 占位，但**按 project seat roster 动态**（不写死 6 seat 顺序）。

### ancestor 可用性

`core/templates/ancestor-brief.template.md` B2 / B3.5 / Phase-B P2 段加一行提示：
"如果 iTerm 六宫格窗口丢失（operator 关窗等），跑 `agent_admin window open-grid <project> --recover` 重开。"

ancestor 遇到"pane 不存在"场景知道用这个命令，不用拼 payload hack。

### `core/skills/clawseat-ancestor/SKILL.md` §4（项目 Bootstrap / Use）

加一段 "window ops"：列 `open-grid` / `open-monitor` / `open-dashboard` 的差异和典型用法。

### 测试

`tests/test_window_open_grid.py`:

1. mock iterm_panes_driver.py → 验证 payload 含正确 seat 数 + wait-for-seat.sh 命令
2. `--recover` + 模拟已有窗口 → 不调用 driver
3. `--open-memory` 额外生成 memory payload
4. project 不存在 → error "project not registered"
5. seat roster 为空 → warn + fallback 只有 ancestor pane

## 约束

- 不改 install.sh（install.sh Step 7 继续调自己的 open_iterm_window，这是 bootstrap 路径）
- 不改 iterm_panes_driver.py 本身
- 等 FEISHU-AUTH-053 R1 完成后，此命令在 sandbox ancestor 里调也能 work（不需要 HOME override）

## Deliverable

`.agent/ops/install-nonint/DELIVERY-WINDOW-OPS-054.md`：

```
## 改动清单
- core/scripts/agent_admin.py (new parser)
- core/scripts/agent_admin_commands.py (new handler)
- core/scripts/agent_admin_window.py (open-grid helper)
- core/templates/ancestor-brief.template.md (指向 open-grid)
- core/skills/clawseat-ancestor/SKILL.md §4 (window ops cheat sheet)
- tests/test_window_open_grid.py
```

**不 commit**。
