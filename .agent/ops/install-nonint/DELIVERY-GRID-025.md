task_id: GRID-025
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: Added a first-boot grid launcher and a tmuxp recovery template for the six-seat ClawSeat monitor.

## Subagent A — launch-grid.sh (内容摘要 + verification output)

- 新增 `scripts/launch-grid.sh`
- 参数：
  - `--project <name>`，默认 `clawseat`
  - `--clawseat-root <path>`，默认 `~/ClawSeat`
- 行为：
  - 幂等创建/复用 6 个 tmux seat session：
    - `<project>-ancestor` → `claude --dangerously-skip-permissions`
    - `<project>-planner|builder|reviewer|qa|designer` → `bash`
  - 通过 `python3` 内嵌调用 `core/scripts/agent_admin_window.py::build_monitor_layout()`，喂入最小 `project/sessions` 结构，创建 `<project>-monitor`
  - 不依赖 `project.toml`、project 注册或 Phase-A 之前的任何持久状态

Verification:

```text
test -x scripts/launch-grid.sh && echo "ok"
ok

bash -n scripts/launch-grid.sh && echo "syntax ok"
syntax ok

./scripts/launch-grid.sh --project grid025-local --clawseat-root /Users/ywf/ClawSeat
tmux attach -t grid025-local-monitor

./scripts/launch-grid.sh --project grid025-local --clawseat-root /Users/ywf/ClawSeat
agent_admin_window: rebuilding monitor session 'grid025-local-monitor' for grid025-local: killing existing session
tmux attach -t grid025-local-monitor

tmux list-sessions -F '#{session_name}' | rg '^grid025-local-(ancestor|planner|builder|reviewer|qa|designer|monitor)$' | sort
grid025-local-ancestor
grid025-local-builder
grid025-local-designer
grid025-local-monitor
grid025-local-planner
grid025-local-qa
grid025-local-reviewer
```

## Subagent B — clawseat-monitor.yaml (内容摘要 + yaml valid output)

- 新增 `templates/clawseat-monitor.yaml`
  - 单 session：`clawseat-monitor`
  - 单 window：`clawseat`
  - `layout: tiled`
  - 6 个 pane 分别尝试 `attach` 到：
    - `clawseat-ancestor`
    - `clawseat-planner`
    - `clawseat-builder`
    - `clawseat-reviewer`
    - `clawseat-qa`
    - `clawseat-designer`
  - 若 seat session 不存在，则回退到登录 shell
- 新增 `templates/README.md`
  - 说明首次拉起用 `scripts/launch-grid.sh`
  - 恢复场景用 `tmuxp load templates/clawseat-monitor.yaml`

Verification:

```text
test -f templates/clawseat-monitor.yaml && echo "ok"
ok

python3 - <<'PY'
import yaml
from pathlib import Path
p = Path("templates/clawseat-monitor.yaml")
data = yaml.safe_load(p.read_text())
print(f"yaml valid: session={data['session_name']} panes={len(data['windows'][0]['panes'])}")
PY
yaml valid: session=clawseat-monitor panes=6
```

## Notes

- `templates/` 目录此前不存在，本次已一并创建。
- `launch-grid.sh` 当前使用 `<project>-ancestor|planner|builder|reviewer|qa|designer` 这套简化 seat session 命名，以及 `<project>-monitor` monitor 命名。
- 我本地补跑了真实幂等烟测，并清理了 `grid025-local-*` 测试 session。
- 目前未提交 commit；工作树新增文件为：
  - `scripts/launch-grid.sh`
  - `templates/clawseat-monitor.yaml`
  - `templates/README.md`
