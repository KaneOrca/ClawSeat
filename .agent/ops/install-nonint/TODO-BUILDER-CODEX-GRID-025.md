# TODO — GRID-025 (六宫格拉起脚本 + tmuxp 模板)

```
task_id: GRID-025
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental worktree)
branch: experimental
priority: P0
subagent-mode: REQUIRED — spawn 2 parallel subagents (A=launch script, B=tmuxp template)
```

## Context

目标：用户装好 tmux + iTerm2 后，一条命令拉起六宫格，ancestor 格子里 CC 直接启动，
其余 5 格等 ancestor Phase-A 来填。这是新简化安装流程的第一步。

现有基础设施（不要重造）：
- `core/scripts/agent_admin_window.py` → `build_monitor_layout(project, sessions)`
  需要各 seat session 已存在才能建网格
- 监控 session 命名约定：`<project>-monitor`（见 agent_admin_config.py:128）
- 各 seat session 命名约定：`<project>-<engineer>-<tool>`（见现有 cartooner 会话命名）

---

## Subagent A — scripts/launch-grid.sh

写 `scripts/launch-grid.sh`，功能：

1. 接受参数 `--project <name>`（默认 `clawseat`）和 `--clawseat-root <path>`（默认 `~/ClawSeat`）
2. 创建 6 个独立 tmux session（如果不存在）：
   - `<project>-ancestor` — 在此 session 里运行 `claude --dangerously-skip-permissions`
   - `<project>-planner` — 运行 `bash`（占位，等 ancestor 拉起）
   - `<project>-builder` — 运行 `bash`
   - `<project>-reviewer` — 运行 `bash`
   - `<project>-qa` — 运行 `bash`
   - `<project>-designer` — 运行 `bash`
3. 调用 `build_monitor_layout()` 建六宫格 monitor session `<project>-monitor`
   - 通过 `python3 -c "..."` 或直接调用 agent_admin.py window 命令
   - 传入正确的 project/sessions 结构
4. 打印 attach 命令：`tmux attach -t <project>-monitor`

约束：
- 脚本要幂等（重复执行不报错，已存在的 session 直接复用）
- `set -euo pipefail`
- 不依赖 project.toml 或已注册的 project（project 注册是 ancestor Phase-A 的事）
- 行数 ≤ 80 行

---

## Subagent B — templates/clawseat-monitor.yaml (tmuxp 模板)

写 `templates/clawseat-monitor.yaml`，用于 **恢复场景**（tmux server 重启后快速恢复）。

tmuxp 的限制：它只管 session+window+pane，不能跨 session attach。
所以这个模板的策略：创建一个单 session 六宫格，每格 attach 到对应的 seat session
（若 seat session 已存在），或运行占位命令（若不存在）。

```yaml
session_name: clawseat-monitor
start_directory: "~/ClawSeat"
windows:
  - window_name: clawseat
    layout: tiled
    panes:
      - shell_command: "exec env -u TMUX tmux attach -t clawseat-ancestor 2>/dev/null || exec $SHELL -l"
      - shell_command: "exec env -u TMUX tmux attach -t clawseat-planner 2>/dev/null || exec $SHELL -l"
      - shell_command: "exec env -u TMUX tmux attach -t clawseat-builder 2>/dev/null || exec $SHELL -l"
      - shell_command: "exec env -u TMUX tmux attach -t clawseat-reviewer 2>/dev/null || exec $SHELL -l"
      - shell_command: "exec env -u TMUX tmux attach -t clawseat-qa 2>/dev/null || exec $SHELL -l"
      - shell_command: "exec env -u TMUX tmux attach -t clawseat-designer 2>/dev/null || exec $SHELL -l"
```

同时写 `templates/README.md`（5 行以内），说明：
- `launch-grid.sh` = 首次拉起（创建 session + 建网格）
- `tmuxp load templates/clawseat-monitor.yaml` = 恢复（server 重启后）

---

## Verification

```bash
cd /Users/ywf/ClawSeat

# 脚本存在且可执行
test -x scripts/launch-grid.sh && echo "ok"

# 模板存在
test -f templates/clawseat-monitor.yaml && echo "ok"

# tmuxp 能解析模板（dry-run）
tmuxp debug-info 2>/dev/null || true
python3 -c "import yaml; yaml.safe_load(open('templates/clawseat-monitor.yaml'))" && echo "yaml valid"

# 脚本语法检查
bash -n scripts/launch-grid.sh && echo "syntax ok"
```

---

## Deliverable

Write `DELIVERY-GRID-025.md` in `/Users/ywf/ClawSeat/.agent/ops/install-nonint/`:

```
task_id: GRID-025
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <one line>

## Subagent A — launch-grid.sh (内容摘要 + verification output)
## Subagent B — clawseat-monitor.yaml (内容摘要 + yaml valid output)
## Notes
```

Notify planner: "DELIVERY-GRID-025 ready".
