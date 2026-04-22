task_id: PRECHECK-026
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: Option A (fake SimpleNamespace project) works; DRAFT-INSTALL-026.md written at 175 lines.

## Subagent A — build_monitor_layout() feasibility

### build_monitor_layout signature

```python
def build_monitor_layout(project: Any, sessions: dict[str, Any]) -> None
```

`project` fields actually accessed:

| Field | Type | Required |
|--------|------|----------|
| `project.monitor_session` | `str` | yes — tmux session name; killed/recreated |
| `project.name` | `str` | yes — error messages, rename-window |
| `project.repo_root` | `str` | yes — `-c` arg on new-session/split-window |
| `project.monitor_engineers` | `list[str]` | yes — enumerated to build layout |
| `project.monitor_max_panes` | `int` | yes — `max(1, ...)` to slice visible engineers |
| `project.window_mode` | `str` | yes — controls tiled vs tabs path |
| `project.engineers` | `list[str]` | fallback when `monitor_engineers` is falsy |

`sessions` is `dict[str, Any]` mapping `engineer_id -> {engineer_id, session, workspace}`.

### agent_admin.py window subcommand construction

`window_open_monitor` (`agent_admin_commands.py:210`):
1. Calls `load_project_or_current(args.project)` — **hard requirement on registered project** (reads from `~/.agents/projects/<name>/project.toml`)
2. Validates `project.monitor_engineers` is non-empty
3. If `window_mode != "tabs-1up"`, calls `session_service.start_project(..., ensure_monitor=True)`
4. Calls `open_monitor_window(project, load_project_sessions(project.name), ...)`

**The `window` subcommand requires a registered project.toml.** But `build_monitor_layout()` itself does not.

### Can project be faked without project.toml?

**Yes.** The existing test suite proves it. `_make_project()` in `test_monitor_layout_n_panes.py` uses only `SimpleNamespace`:

```python
SimpleNamespace(
    name="demo",
    repo_root="/tmp/demo-repo",
    monitor_session="project-demo-monitor",
    monitor_engineers=engineer_ids,
    engineers=engineer_ids,
    monitor_max_panes=n,
    window_mode=mode,  # "project-monitor" | "tabs-1up"
)
```

No method calls, no database, no registration — pure attribute access.

### Recommended approach for launch-grid.sh

**Option A: fake project with SimpleNamespace** — lowest coupling, no registration, no modification to `build_monitor_layout`.

### Minimal code

```python
from types import SimpleNamespace
import sys
sys.path.insert(0, "/Users/ywf/ClawSeat/core/scripts")
import agent_admin_window

def make_fake_project(
    name="grid",
    repo_root="/Users/ywf/ClawSeat",
    monitor_session="grid-monitor",
    monitor_engineers=None,
    engineers=None,
    monitor_max_panes=6,
    window_mode="project-monitor",
):
    monitor_engineers = monitor_engineers or engineers or []
    engineers = engineers or monitor_engineers
    return SimpleNamespace(
        name=name,
        repo_root=repo_root,
        monitor_session=monitor_session,
        monitor_engineers=monitor_engineers,
        engineers=engineers,
        monitor_max_panes=monitor_max_panes,
        window_mode=window_mode,
    )

sessions = {
    eid: SimpleNamespace(engineer_id=eid, session=f"grid-{eid}", workspace=f"/Users/ywf/ClawSeat/engineers/{eid}")
    for eid in ["seat0", "seat1", "seat2"]
}

agent_admin_window.build_monitor_layout(make_fake_project(), sessions)
```

**Prerequisite**: the engineer sessions in `sessions` must already exist in tmux (`tmux has-session -t grid-seat0` must return 0). `build_monitor_layout` will kill and recreate the monitor session named `project.monitor_session`.

**Conclusion**: launch-grid.sh can bypass project.toml entirely using Option A. No changes to `build_monitor_layout` needed.

---

## Subagent B — 新 INSTALL.md 草稿

### 写入路径
`/Users/ywf/ClawSeat/.agent/ops/install-nonint/DRAFT-INSTALL-026.md` (175 lines, under 200-line limit)

### 关键设计决策

| 决策 | 说明 |
|------|------|
| Agent-first 读者 | 面向 Claude Code 执行者，不是人类；每个 Step 包含 Verify/Failure 块 |
| Phase-A 全由 ancestor 完成 | Step 2 用户只负责 attach；所有注册/env scan/runtime 选择由 ancestor 自动完成 |
| 3-Enter flush 协议 | launch-grid.sh 启动后，ancestor 格子里需要 3 次 Enter 确认 bypass 生效 |
| 失败恢复 | 7 种失败代码 + 对应恢复动作；Resume 部分支持 re-run 或 attach 现有 session |
| tmux attach 指令 | 显式告知 `tmux attach -t clawseat-monitor` 进入网格（而不是 `tmux attach` 混用） |

### 草稿结构
```
Prerequisites
  → git clone, auto-dep install (tmux/iTerm2/Python 3.11), claude binary prompt

Step 1: 拉起六宫格
  → launch-grid.sh, bypass 启动, 3-Enter flush, operator 通知

Step 2: 用户 attach
  → attach, ancestor Phase-A (B1-B7 checklist 表格)

Step 3: 验收
  → STATUS.md phase=ready + Feishu smoke report

Failure Modes (7 codes)
Resume
```

---

## Overall: install readiness verdict

**OPTION A APPROVED** — launch-grid.sh can call `build_monitor_layout()` with a faked SimpleNamespace project, no project.toml required. The 6-pane grid can be constructed entirely from tmux session names and engineer IDs known at runtime.

DRAFT-INSTALL-026.md ready for review at the draft path.
