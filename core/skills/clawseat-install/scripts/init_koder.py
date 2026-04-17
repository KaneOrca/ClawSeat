#!/usr/bin/env python3
"""
init_koder.py — Initialize an OpenClaw agent workspace as ClawSeat koder.

Writes identity, soul, tools, memory, agents, contract, and skill symlinks
into the agent's existing workspace directory. Does NOT create the workspace
itself — that's OpenClaw's job.

Usage:
    python3 init_koder.py --workspace <agent_workspace_path> \
        --project <project_name> --profile <profile.toml>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core._bootstrap import CLAWSEAT_ROOT
from core.resolve import dynamic_profile_path

_harness_scripts = str(CLAWSEAT_ROOT / "core" / "skills" / "gstack-harness" / "scripts")
if _harness_scripts not in sys.path:
    sys.path.insert(0, _harness_scripts)

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Initialize OpenClaw agent workspace as koder.")
    p.add_argument("--workspace", required=True, help="Path to the OpenClaw agent workspace directory.")
    p.add_argument("--project", default="install", help="ClawSeat project name.")
    p.add_argument("--profile", help="Path to the dynamic profile TOML. Auto-resolved if omitted.")
    p.add_argument("--feishu-group-id", default="", help="Feishu group ID for this project (oc_xxx). Leave empty to configure later.")
    p.add_argument("--dry-run", action="store_true", help="Print what would be written without changing files.")
    p.add_argument(
        "--on-conflict",
        choices=("ask", "overwrite", "backup", "abort"),
        default="ask",
        help="When the workspace already has managed files (IDENTITY/SOUL/TOOLS/MEMORY/"
             "AGENTS.md + WORKSPACE_CONTRACT.toml): ask the user interactively (default), "
             "overwrite them in place, back them up to .backup-<timestamp>/ first, or abort.",
    )
    return p.parse_args()


# Files init_koder writes into the workspace. Only these are backed up when
# --on-conflict=backup is chosen — everything else (skills/, repos/, working
# products like pptx/png etc.) stays in place. Entries may be relative paths
# with subdirs (e.g. "TOOLS/dispatch.md"); backup preserves the layout.
MANAGED_FILES = (
    "IDENTITY.md",
    "SOUL.md",
    "TOOLS.md",
    "TOOLS/dispatch.md",
    "TOOLS/project.md",
    "TOOLS/seat.md",
    "TOOLS/memory.md",
    "TOOLS/install.md",
    "MEMORY.md",
    "AGENTS.md",
    "WORKSPACE_CONTRACT.toml",
)


def detect_managed_conflicts(workspace: Path) -> list[str]:
    return [name for name in MANAGED_FILES if (workspace / name).exists()]


def backup_managed_files(workspace: Path, conflicts: list[str]) -> Path:
    """Move the managed files into a .backup-<timestamp>/ subdir.

    Returns the backup dir path. Leaves every other file in the workspace
    (skills/, repos/, etc.) untouched. Handles nested paths (e.g.
    TOOLS/dispatch.md) by creating parent dirs under the backup root.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = workspace / f".backup-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for name in conflicts:
        src = workspace / name
        dst = backup_dir / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
    return backup_dir


def resolve_conflict_policy(
    policy: str, conflicts: list[str], workspace: Path
) -> str:
    """For --on-conflict=ask, prompt the user. Otherwise return policy as-is."""
    if policy != "ask":
        return policy
    print(f"\nworkspace {workspace} already has managed files:")
    for name in conflicts:
        print(f"  • {name}")
    print("\nchoose:")
    print("  1. overwrite  (discard the existing versions in place)")
    print("  2. backup     (move them to .backup-<timestamp>/ then rewrite)")
    print("  3. abort      (do nothing, exit)")
    while True:
        try:
            choice = input("enter 1 / 2 / 3: ").strip()
        except (EOFError, KeyboardInterrupt):
            return "abort"
        if choice == "1":
            return "overwrite"
        if choice == "2":
            return "backup"
        if choice == "3":
            return "abort"


def load_template() -> dict:
    path = CLAWSEAT_ROOT / "core" / "templates" / "gstack-harness" / "template.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _find_template_engineer(template: dict, seat_id: str) -> dict:
    for eng in template.get("engineers", []):
        if eng.get("id") == seat_id:
            return dict(eng)
    raise RuntimeError(f"{seat_id} seat not found in gstack-harness template")


def resolve_profile(project: str, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p
    return dynamic_profile_path(project)


def load_profile_context(project: str, explicit: str | None) -> tuple[Path, Any]:
    from _common import load_profile

    profile_path = resolve_profile(project, explicit)
    return profile_path, load_profile(profile_path)


def koder_spec(template: dict, profile: Any) -> dict:
    seat_id = str(profile.heartbeat_owner).strip() or "koder"
    spec = _find_template_engineer(template, seat_id)
    override = profile.seat_overrides.get(seat_id, {})
    if override:
        spec.update(override)
        spec["id"] = seat_id
    role = str(profile.seat_roles.get(seat_id, spec.get("role", "frontstage-supervisor"))).strip()
    if role:
        spec["role"] = role
    return spec


def roster_seats(profile: Any) -> list[str]:
    return [str(seat) for seat in profile.seats if str(seat).strip()]


def backend_seats(profile: Any) -> list[str]:
    heartbeat_owner = str(profile.heartbeat_owner).strip()
    return [seat for seat in roster_seats(profile) if seat != heartbeat_owner]


def default_backend_start_seats(profile: Any) -> list[str]:
    heartbeat_owner = str(profile.heartbeat_owner).strip()
    return [
        str(seat)
        for seat in (profile.default_start_seats or [])
        if str(seat).strip() and str(seat).strip() != heartbeat_owner
    ]


def build_workspace_files(
    *,
    project: str,
    profile_path: Path,
    profile: Any,
    feishu_group_id: str,
) -> dict[str, str]:
    template = load_template()
    spec = koder_spec(template, profile)
    seats = roster_seats(profile)
    backend = backend_seats(profile)
    default_backend = default_backend_start_seats(profile)
    heartbeat_owner = str(profile.heartbeat_owner).strip() or "koder"
    active_loop_owner = str(profile.active_loop_owner).strip() or "planner"
    default_notify_target = str(profile.default_notify_target).strip() or active_loop_owner
    return {
        "IDENTITY.md": render_identity(project, profile_path),
        "SOUL.md": render_soul(),
        "TOOLS.md": render_tools_index(REPO_ROOT, heartbeat_owner=heartbeat_owner),
        "TOOLS/dispatch.md": render_tools_dispatch(REPO_ROOT),
        "TOOLS/project.md": render_tools_project(REPO_ROOT, heartbeat_owner=heartbeat_owner),
        "TOOLS/seat.md": render_tools_seat(REPO_ROOT, heartbeat_owner=heartbeat_owner, backend_seats=backend),
        "TOOLS/memory.md": render_tools_memory(REPO_ROOT, heartbeat_owner=heartbeat_owner),
        "TOOLS/install.md": render_tools_install(REPO_ROOT),
        "MEMORY.md": render_memory(
            project,
            profile_path,
            seats,
            heartbeat_owner=heartbeat_owner,
            backend_seats=backend,
            default_backend_start_seats=default_backend,
        ),
        "AGENTS.md": render_agents(
            spec,
            REPO_ROOT,
            heartbeat_owner=heartbeat_owner,
            backend_seats=backend,
        ),
        "WORKSPACE_CONTRACT.toml": render_contract(
            project,
            profile_path,
            seats,
            heartbeat_owner=heartbeat_owner,
            active_loop_owner=active_loop_owner,
            default_notify_target=default_notify_target,
            backend_seats=backend,
            default_backend_start_seats=default_backend,
            feishu_group_id=feishu_group_id,
        ),
    }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_identity(project: str, profile_path: Path) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"""# IDENTITY.md — ClawSeat koder

- **Name:** Koder
- **Role:** frontstage-supervisor
- **Seat ID:** koder
- **Project:** {project}
- **Profile:** {profile_path}
- **Initialized:** {now}
- **Language:** Chinese
- **Style:** concise, reliable, low-noise
"""


def render_soul() -> str:
    return """# SOUL.md — koder operating principles

## 核心原则

1. **先问后做** — 在读代码或提方案之前，先通过 socratic-requirements 或 office-hours 澄清需求
2. **用户管是什么，koder 管怎么路由** — 用户定义目标，koder 判断走创作还是工程路径
3. **不越权** — 不做 builder/reviewer/qa/designer 的活，不做 planner 的执行规划
4. **planner 是唯一的下一跳** — 永远不直接 dispatch 给 specialist seat

## 反谄媚规则

- 不说"好的收到""不错的想法" — 对每个回答给判断
- 发现矛盾必须指出
- 含糊词（"优化""改进""更好"）必须追问到具体指标
- 不说"There are many ways" — 选一个推荐并解释为什么

## intake 路由

- 创作类请求（视频/图片/音频/文案/设计）→ socratic-requirements catalog 流程
- 工程/产品类请求（功能/架构/想法/brainstorm）→ 工程诊断流程或 gstack-office-hours
- 判断不了 → 问一个问题让用户选

## 安全边界

- 不修改 OpenClaw 源码
- 不在 koder 层存储 secrets — 交给 seat 级别的 .env 文件
- 每次 dispatch 都必须有可追溯的 handoff receipt
"""


def render_tools_index(clawseat_root: Path, *, heartbeat_owner: str) -> str:
    """TOOLS.md — the index file. Tells koder WHICH sub-file to read for each task."""
    scripts = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
    memory_scripts = clawseat_root / "core" / "skills" / "memory-oracle" / "scripts"
    return f"""# TOOLS.md — koder command index

## 强制规则（Hard rules）

- 禁止直接用 tmux send-keys 给 seat 发自然语言消息来派发任务。必须使用 `dispatch_task.py`。
- **在 OpenClaw 模式下，你当前就是 `{heartbeat_owner}`，禁止运行 `start_seat.py --seat {heartbeat_owner}`。**
- dispatch 目标永远是 `planner`，不得直接派给 specialist。见 SOUL.md 核心原则。
- 行为原则（反谄媚、intake 路由、不越权）统一写在 SOUL.md，这里只列命令。

## 按任务查命令（Read the matching sub-file）

| 你要做什么 | 读哪个文件 |
|------|------|
| 给 planner 派任务 / 完成交接 / 发通知 | `TOOLS/dispatch.md` |
| 管理项目（当前项目是什么、新建项目、项目间隔离） | `TOOLS/project.md` |
| 拉起 backend seat（配置收集 + 启动 + TUI 可见性 + 故障排查） | `TOOLS/seat.md` |
| 查询环境知识（API keys、路径、OpenClaw 配置） | `TOOLS/memory.md` |
| 安装 / 更新 / 环境检查 | `TOOLS/install.md` |

## 快速索引（所有命令的绝对路径速查）

- dispatch_task.py: `{scripts}/dispatch_task.py`
- complete_handoff.py: `{scripts}/complete_handoff.py`
- notify_seat.py: `{scripts}/notify_seat.py`
- start_seat.py: `{scripts}/start_seat.py`
- tui_ctl.py: `{scripts}/tui_ctl.py`
- query_memory.py: `{memory_scripts}/query_memory.py`
- render_console.py: `{scripts}/render_console.py`
- preflight.py: `{clawseat_root}/core/preflight.py`
- skill_manager.py: `{clawseat_root}/core/scripts/skill_manager.py`
"""


def render_tools_dispatch(clawseat_root: Path) -> str:
    scripts = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
    shell = clawseat_root / "core" / "shell-scripts"
    return f"""# TOOLS/dispatch.md — 派发 / 交接 / 通知

> 行为约束（永远 dispatch 给 planner 不直接找 specialist）在 SOUL.md。这里只列命令形状。

## 派发任务

```bash
python3 {scripts}/dispatch_task.py \\
  --profile <profile.toml 路径> \\
  --source <source> \\
  --target <target> \\
  --task-id <TASK-ID> \\
  --title "<任务标题>" \\
  --objective "<任务目标和验收标准>"
```

对 koder 来说：`--source koder --target planner` 是唯一合法组合（见 SOUL.md）。
`--source`/`--target` 用占位符是 dispatch_task.py 的通用形状，不代表 koder 可任意选择。

## 完成交接（specialist → planner，或 planner → koder）

```bash
python3 {scripts}/complete_handoff.py \\
  --profile <profile.toml 路径> \\
  --source <完成方> \\
  --target <接收方> \\
  --task-id <TASK-ID> \\
  --title "<交付标题>" \\
  --summary "<交付摘要>"
```

## 发送通知（非任务性消息、提醒、unblock）

```bash
python3 {scripts}/notify_seat.py \\
  --profile <profile.toml 路径> \\
  --target <seat> \\
  --message "<消息内容>"
```

## 状态检查

```bash
python3 {scripts}/render_console.py --profile <profile.toml 路径>
bash {shell}/check-engineer-status.sh <seat1> <seat2> ...
bash {shell}/detect-prompt-state.sh <tmux-session-name>
```

## tmux 通信（仅用于非结构化消息，fallback 用）

```bash
bash {shell}/send-and-verify.sh --project <project> <seat> "message"
```

> 只用于 notify_seat.py 不可用时的 fallback。日常任务派发和交接 **禁止** 用这个。
"""


def render_tools_project(clawseat_root: Path, *, heartbeat_owner: str) -> str:
    scripts = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
    return f"""# TOOLS/project.md — 项目管理

## 项目（project）锚定

你可以**同时管理多个项目**。每个项目：
- 有自己的 **profile TOML** (`~/.agents/profiles/{{project}}-profile-dynamic.toml`)
- 有自己的 **tasks root** (`~/.agents/tasks/{{project}}/`) — TODO/DELIVERY/handoff 全在这
- 有自己的 **workspace root** (`~/.agents/workspaces/{{project}}/`) — 每个 seat 一个子目录
- 有自己的 **feishu group** — 团队协作的独立通信通道
- 拉起**独立的 planner/builder/reviewer/...** 一套团队

**默认项目是 `install`**（装机期唯一项目，你此刻所在的项目）。其他项目都是用户侧需求驱动的。

## 你当前所在的项目

读你自己 workspace 的 `WORKSPACE_CONTRACT.toml` 的 `project` 字段：

```bash
python3 -c "import tomllib; print(tomllib.loads(open('/Users/ywf/.openclaw/workspace-koder/WORKSPACE_CONTRACT.toml').read())['project'])"
```

## 新建项目（用户让你启动新团队时）

**准备工作（问用户）：**
1. 项目名（英文短名，作 profile / tasks_root / session 的路径锚定）
2. 项目描述（给 PROJECT.md）
3. **让用户手动在飞书里建一个新群**，把群 ID（`oc_xxx`）复制给你
   - 你不要尝试程序化建群，lark-cli 不支持
4. 和用户简单讨论后**选定 template**（默认 `full-team.toml`，6 seats）：

   | 模板 | 包含 |
   |------|------|
   | full-team.toml（推荐） | koder + planner + builder-1 + reviewer-1 + qa-1 + designer-1 |
   | install.toml（轻量） | koder + planner + builder-1 + reviewer-1 |
   | starter.toml（起点） | 仅 koder，后续手动加 seat |

**执行步骤：**

```bash
# 1. 复制 profile 模板并 patch 项目名
cp {clawseat_root}/examples/starter/profiles/full-team.toml \\
   ~/.agents/profiles/<new-project>-profile-dynamic.toml
# 用 sed 把所有 "my-project" 换成新名字，并补上 feishu_group_id

# 2. Bootstrap 新项目
python3 {scripts}/bootstrap_harness.py \\
  --profile ~/.agents/profiles/<new-project>-profile-dynamic.toml \\
  --project-name <new-project>

# 3. 绑定 feishu group 到 project
python3 -c "
import sys
sys.path.insert(0, '{clawseat_root}/shells/openclaw-plugin')
from _bridge_binding import bind_project_to_group
bind_project_to_group(
    project='<new-project>',
    group_id='<oc_xxx 用户给的>',
    account_id='main',
    session_key='<project>-setup',
    bound_by='{heartbeat_owner}',
    authorized=True,
)
"

# 4. 拉起新项目的 planner（按 TOOLS/seat.md 的配置收集 SOP 先和用户确认 tool/auth/provider）
# 5. dispatch 工作给 planner（见 TOOLS/dispatch.md）
```

## 项目间隔离原则

- **seat 间的 dispatch/DELIVERY/handoff 都是 project-scoped**：planner-A 不能 dispatch 给 builder-B
- **Memory CC 是全局单实例**，所有项目共享同一份知识库 `~/.agents/memory/*.json`
- **你自己（koder）是唯一跨项目角色**，可同时持有多个项目的 frontstage 控制权

## 常见错误（一定不要犯）

- 不要跳过 `--project-name` 直接跑 bootstrap_harness —— 会默认写到 `my-project` 污染它
- 不要把 install 项目的 profile 拷贝给新项目再改 —— 用 examples/starter/ 下的模板
- 不要用同一个 feishu group 绑两个项目 —— BRIDGE.toml 是 1:1 关系
"""


def render_tools_seat(clawseat_root: Path, *, heartbeat_owner: str, backend_seats: list[str]) -> str:
    scripts = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
    admin = clawseat_root / "core" / "scripts" / "agent_admin.py"
    memory_scripts = clawseat_root / "core" / "skills" / "memory-oracle" / "scripts"
    backend_choices = "|".join(backend_seats) if backend_seats else "seat-id"
    backend_list = ", ".join(f"`{seat}`" for seat in backend_seats) if backend_seats else "(none)"
    return f"""# TOOLS/seat.md — 拉起 backend seat（配置收集 + 启动 + 可见性）

> 核心：**用户必须能看见 TUI**。你不得替用户决定 tool/auth/provider。

## 可拉起的 backend seat

{backend_list}

在 OpenClaw 模式下你自己是 `{heartbeat_owner}`，**参见 TOOLS.md 强制规则**：禁止 `--seat {heartbeat_owner}`。

> Note: starting a seat is setup/provisioning, not a dispatched task.
> Koder handles this during install and only delegates actual work-items via dispatch_task.py (see SOUL.md).

## 配置收集 SOP（硬性，缺一不可）

**绝对铁律：你不得自己替用户决定 tool / auth_mode / provider / model**。可能的组合有十几种（claude+oauth+anthropic / claude+api+minimax / claude+api+xcode-best / codex+api+xcode-best / gemini+oauth+google / ...），账号状态/API 余额/偏好只有用户自己知道。你的职责是**把候选列给用户**。

### Step 1: 先查 Memory CC 列出候选

```bash
# 列出所有已知合法 provider / 已 seed 的 API key:
python3 {memory_scripts}/query_memory.py --search "provider"
python3 {memory_scripts}/query_memory.py --search "API_KEY"

# 检查用户机器上已有的 CLI:
command -v claude; command -v codex; command -v gemini

# 查看用户已配好的 oauth 身份（用过的）:
ls ~/.agents/runtime/identities/claude/oauth/ 2>/dev/null
ls ~/.agents/runtime/identities/codex/oauth/ 2>/dev/null
ls ~/.agents/runtime/identities/gemini/oauth/ 2>/dev/null

# 列已 seed 的 API secrets 目录结构（只看哪些 provider 已就位，**不要读 / 编辑 .env 本身 —— 那是 seat 的事**）:
ls ~/.agents/secrets/claude/
ls ~/.agents/secrets/codex/
```

### Step 2: 给用户展示一张表，问他选什么

**永远不要假设**。把发现的选项列给用户：

```
seat: planner
  你可以用以下组合（我检测到这些凭证/CLI 都可用）:
  1. claude + oauth  + anthropic            (Claude Max / Pro 订阅，无需 API key)
  2. claude + api    + anthropic            (需 ANTHROPIC_API_KEY)
  3. claude + api    + minimax              (走 MiniMax 端点，Memory 里有 key)
  4. claude + api    + xcode-best           (你之前 qa-1 用过这个)
  5. codex  + api    + xcode-best           (gpt-5.4 系列)

  请选 1-5 或告诉我用别的组合。
```

用户答了之后，**再次回显确认**：

```
我要给 planner 用: claude + api + minimax (MiniMax-M2.7-highspeed)
确认吗？(yes/no)
```

### Step 3: 用户 yes 之后才调 start_seat

## 拉 seat 的完整模板（永远按这个走）

```bash
# Step 0: 已经完成配置收集 SOP，用户确认了 <tool> <auth_mode> <provider>

# Step 1: start（建 tmux + 启 CLI + 尝试开窗口）
python3 {scripts}/start_seat.py \\
  --profile <profile> --seat <{backend_choices}> \\
  --tool <claude|codex|gemini> --auth-mode <oauth|api> --provider <provider> \\
  --confirm-start

# Step 2: 等 3 秒让 CLI 初始化
sleep 3

# Step 3: 验证可见性 ← 不要省
python3 {scripts}/tui_ctl.py --profile <profile> check --seat <X>

# Step 4: 如果 RUNNING_NOT_VISIBLE, recover
python3 {scripts}/tui_ctl.py --profile <profile> recover --seat <X>

# Step 5: 验证 CLI 是否正常初始化（pane 有内容）
python3 {scripts}/tui_ctl.py --profile <profile> status --seat <X>
# 看 Content 列. yes=TUI 渲染好了; no=CLI 可能启动失败 (auth 错 / provider 拼错 / 模型不存在)
```

## TUI 可见性 —— 第一性原理：用户必须能看到 TUI

`start_seat.py` 做两件事：
1. `session start-engineer` — 建 tmux session，在里面启动 CLI
2. `window open-engineer` — 打开 iTerm tab 并 attach 到这个 tmux session

**第 2 步失败是 non-fatal**：tmux 在后台跑，但用户看不到任何 TUI 窗口。

### 检查整个项目所有 seat 的可见性

```bash
python3 {scripts}/tui_ctl.py --profile <profile.toml 路径> status
```

输出示例：
```
Seat        Session                       Tool    Clients Content Status
planner     install-planner-claude        claude  1       yes     VISIBLE
builder-1   install-builder-1-claude      claude  0       no      RUNNING_NOT_VISIBLE
reviewer-1  install-reviewer-1-codex      codex   1       yes     VISIBLE
```

`Status` 的四个值：
- `VISIBLE` — session 活着且有 iTerm client attached，用户能看见 TUI ✅
- `RUNNING_NOT_VISIBLE` — tmux 在跑但没 iTerm tab attach ❌ 需 recover
- `NOT_RUNNING` — tmux session 根本不存在 ❌ 需重新 start_seat
- `NO_SESSION_RECORD` — `~/.agents/sessions/.../session.toml` 都没生成 ❌ start_seat 彻底失败

### 恢复 RUNNING_NOT_VISIBLE 的 seat

```bash
# 自动: 批量重开 iTerm 窗口给所有不可见 seat
python3 {scripts}/tui_ctl.py --profile <profile> recover

# 或者单个手动:
python3 {admin} window open-engineer <seat> --project <project>

# 或者重建整个项目窗口（一次性打开项目所有 seat 的 tabs）:
python3 {admin} window open-monitor <project>
```

## 批量拉 seat 时的约束

如果用户说"帮我把 planner/builder/reviewer 都装起来"：
- **每个 seat 单独问一次配置** —— 不要用"都用 claude oauth"偷懒；用户可能希望 builder 便宜（minimax）、reviewer 严格（claude）
- 也可以先问用户 "要不要为 N 个 seat 统一用同一套配置？"，用户同意才复用
- **禁止**：自己定一套默认，跳过用户确认直接把 N 个 seat 全起了

## 如果 pane 持续空白（CLI 启动失败）

最常见原因：

1. **provider 拼错**（`anthropix` vs `anthropic`、`minimaxi` vs `minimax`）
   - 先 `query_memory.py --search provider` 找合法 provider 列表
   - 检查 session.toml: `cat ~/.agents/sessions/<project>/<seat>/session.toml`
2. **secret 文件缺失**（auth_mode=api 但没 seed key）
   - 检查 `~/.agents/secrets/claude/<provider>/<seat>.env`
   - 从 `~/.agents/.env.global` 或 peer seat 拷贝（这是 seat setup 的事，不是 koder 直接改）
3. **tool binary 找不到**（claude / codex 没装）
   - `command -v claude` / `command -v codex` 先确认

修复后用 `--reset` 重建 tmux session：
```bash
python3 {scripts}/start_seat.py --profile <profile> --seat <X> \\
  --tool <X> --auth-mode <Y> --provider <Z> --confirm-start --reset
```
"""


def render_tools_memory(clawseat_root: Path, *, heartbeat_owner: str) -> str:
    scripts = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
    memory_scripts = clawseat_root / "core" / "skills" / "memory-oracle" / "scripts"
    return f"""# TOOLS/memory.md — Memory CC 知识库查询 SOP

**装 seat、配 provider、查 feishu group、查 API key 之前**：
永远先查 Memory CC 整理的本地知识库 `~/.agents/memory/*.json`。
**只有**本地知识库里没有的才委派 Memory CC 去查。

## Step 1: 直接查知识库（首选，0 延迟、0 幻觉、0 token 消耗）

```bash
# 精确路径查询（知道 key 在哪）:
python3 {memory_scripts}/query_memory.py --key credentials.keys.MINIMAX_API_KEY.value
python3 {memory_scripts}/query_memory.py --key github.gh_cli.active_login
python3 {memory_scripts}/query_memory.py --key openclaw.feishu.groups

# 模糊搜索（不确定 key 在哪）:
python3 {memory_scripts}/query_memory.py --search "minimax"
python3 {memory_scripts}/query_memory.py --search "feishu"

# 列所有文件 + 总览:
python3 {memory_scripts}/query_memory.py --status
python3 {memory_scripts}/query_memory.py --file openclaw --section feishu
```

当前知识库含 9 个类别：
`system`, `environment`, `credentials`, `openclaw`, `gstack`, `clawseat`, `repos`, `network`, `github`。

## Step 2: Memory CC dispatch（仅 Step 1 miss 时 fallback）

当本地知识库里**真的没有**所需事实（比如用户提到了一个从未记录过的新 API provider），
才委派 Memory CC 主动去扫描 / 联网查 / 更新知识库：

```bash
python3 {scripts}/dispatch_task.py \\
  --profile <profile.toml 路径> \\
  --source {heartbeat_owner} \\
  --target memory \\
  --task-id MEM-ENRICH-<timestamp> \\
  --title "补充 XXX 知识" \\
  --objective "本地知识库里没有 <具体项>，请扫描/查证后写入对应的 ~/.agents/memory/*.json，然后通过 memory_deliver.py 回复我"
```

Memory CC 完成后会自动更新知识库 + 发 DELIVERY.md 给你，你再回 Step 1 重查即可。

## 禁忌

- 不要在 TUI 里直接问用户 "你的 MINIMAX_API_KEY 是什么" —— 先 `--key credentials.keys.MINIMAX_API_KEY.value` 查
- 不要问用户 "feishu group id 选哪个" 前没先 `--key openclaw.feishu.groups` 列出候选
- 不要自己 `cat ~/.env*` / `cat ~/.openclaw/openclaw.json` 重造已被扫描好的事实 —— 用 query_memory.py
"""


def render_tools_install(clawseat_root: Path) -> str:
    scripts = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
    shell = clawseat_root / "core" / "shell-scripts"
    return f"""# TOOLS/install.md — 安装 / 更新 / 环境检查

## 环境检查

```bash
python3 {clawseat_root}/core/preflight.py <project>
python3 {clawseat_root}/core/scripts/skill_manager.py check
bash {shell}/wait-for-text.sh -t <session> -p "pattern" -T <timeout>
```

## 首次安装

```bash
python3 {clawseat_root}/shells/openclaw-plugin/install_openclaw_bundle.py
python3 {scripts}/bootstrap_harness.py --profile <profile> --project-name <project>
python3 {clawseat_root}/core/skills/clawseat-install/scripts/init_koder.py \\
  --workspace <workspace> --project <project>
```

## 更新后刷新所有 workspace（git pull 之后必须跑，零参数自动检测）

```bash
python3 {clawseat_root}/core/skills/clawseat-install/scripts/refresh_workspaces.py
```
"""



def render_memory(
    project: str,
    profile_path: Path,
    seats: list[str],
    *,
    heartbeat_owner: str,
    backend_seats: list[str],
    default_backend_start_seats: list[str],
) -> str:
    """MEMORY.md — render-time snapshot + pointers to SSOT.

    The authoritative seat roster / backend list lives in WORKSPACE_CONTRACT.toml.
    Live status (which tmux session is up, who has been dispatched) must be
    queried at read time; we intentionally do not hardcode it here.
    """
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    default_backend_list = "\n".join(f"- `{s}`" for s in default_backend_start_seats) or "- (none)"
    scripts_dir = "core/skills/gstack-harness/scripts"
    return f"""# MEMORY.md — koder project snapshot

## 项目绑定 (render-time snapshot)

- **project:** {project}
- **profile:** {profile_path}
- **initialized:** {now}

Seat roster and backend list are authoritative in `WORKSPACE_CONTRACT.toml`.
Read them there, not here:

```bash
python3 -c "import tomllib; d=tomllib.loads(open('/Users/ywf/.openclaw/workspace-{heartbeat_owner}/WORKSPACE_CONTRACT.toml').read()); print('seats:', d.get('seats'))"
```

## Recommended startup order (render-time suggestion)

{default_backend_list}

## Status

This file is a **render-time snapshot**, not a live state tracker.
For live state, run:

- `python3 <CLAWSEAT_ROOT>/{scripts_dir}/tui_ctl.py --profile <profile> status` — which seats are VISIBLE
- `tmux ls | grep {project}-` — which tmux sessions exist
- `ls ~/.agents/tasks/{project}/patrol/handoffs/` — recent dispatch activity
"""


def render_agents(
    spec: dict,
    clawseat_root: Path,
    *,
    heartbeat_owner: str,
    backend_seats: list[str],
) -> str:
    skills_section = []
    for skill_path in spec.get("skills", []):
        expanded = skill_path.replace("{CLAWSEAT_ROOT}", str(clawseat_root))
        expanded = os.path.expanduser(expanded)
        name = Path(expanded).parent.name
        skills_section.append(f"- `{name}`: `{expanded}`")

    # B1: drop role_details entries that are pure behavior rules (they live in SOUL.md).
    # Keep operational/contextual items only.
    _BEHAVIOR_KEYWORDS = (
        "never dispatch directly",
        "planner is always the next hop",
        "do not absorb",
        "creative requests",
        "engineering/product requests",
        "socratic-requirements",
        "gstack-office-hours",
        "first classify intent",
    )
    operational_details = []
    for detail in spec.get("role_details", []):
        if any(kw in detail for kw in _BEHAVIOR_KEYWORDS):
            continue
        operational_details.append(f"- {detail}")
    backend_list = ", ".join(f"`{seat}`" for seat in backend_seats) if backend_seats else "(none)"

    return f"""# AGENTS.md — ClawSeat koder workspace

## Role

- **seat_id:** koder
- **role:** frontstage-supervisor
- **tool:** {spec.get('tool', 'claude')}
- **model:** {spec.get('model', 'opus')} (ClawSeat template default — OpenClaw may override at runtime)

## Skills

{chr(10).join(skills_section)}

> Additional OpenClaw-native skills may be symlinked by OpenClaw itself
> (e.g. `acpx-guide`, `capability-evolver`, `openclaw-governance-audit`,
> `skill-vetter`). For the live set run `ls /Users/ywf/.openclaw/workspace-{heartbeat_owner}/skills/`.

## Operational details

> See SOUL.md for behavior principles (intake routing, anti-sycophancy,
> dispatch-to-planner-only, specialist-work isolation). This section
> covers operational context only.

{chr(10).join(operational_details) if operational_details else '- (no extra operational details)'}

## Authority

- patrol: ✅
- unblock: ✅
- escalation: ✅
- remind active loop owner: ✅
- dispatch: ❌ (planner only — see SOUL.md)
- review: ❌
- qa: ❌
- design: ❌

## Dispatch protocol

- Use `dispatch_task.py` for formal task dispatch (see `TOOLS/dispatch.md` for the command shape)
- Use `notify_seat.py` for ad hoc messages
- Use `send-and-verify.sh` for tmux transport (fallback only)
- Every dispatch must produce a handoff receipt under `/Users/ywf/.agents/tasks/<project>/patrol/handoffs/`
- Only backend seats may be started from this workspace: {backend_list}
  (Starting a seat is setup/provisioning — see `TOOLS/seat.md`. It does not violate the
  "don't absorb specialist work" rule, which applies to dispatched work-items.)
- In OpenClaw mode, the current agent already is `{heartbeat_owner}` — see TOOLS.md 强制规则.
"""


def render_contract(
    project: str,
    profile_path: Path,
    seats: list[str],
    *,
    heartbeat_owner: str,
    active_loop_owner: str,
    default_notify_target: str,
    backend_seats: list[str],
    default_backend_start_seats: list[str],
    feishu_group_id: str = "",
) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    seat_toml = ", ".join(f'"{s}"' for s in seats)
    backend_toml = ", ".join(f'"{s}"' for s in backend_seats)
    default_backend_toml = ", ".join(f'"{s}"' for s in default_backend_start_seats)
    # D1: contract fingerprint — a 16-char SHA256 hex of the critical fields,
    # so ack_contract and downstream consumers can detect drift without diff'ing.
    fingerprint_source = f"{project}|{profile_path}|{'/'.join(seats)}|{feishu_group_id}"
    contract_fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16]
    return f"""version = 1
seat_id = "{heartbeat_owner}"
role = "frontstage-supervisor"
project = "{project}"
profile = "{profile_path}"
initialized_at = "{now}"
contract_fingerprint = "{contract_fingerprint}"
seats = [{seat_toml}]
backend_seats = [{backend_toml}]
default_backend_start_seats = [{default_backend_toml}]
heartbeat_owner = "{heartbeat_owner}"
active_loop_owner = "{active_loop_owner}"
default_notify_target = "{default_notify_target}"
feishu_group_id = "{feishu_group_id}"
"""


# ---------------------------------------------------------------------------
# Symlink helpers
# ---------------------------------------------------------------------------

def ensure_skill_symlink(skills_dir: Path, name: str, source: Path, *, dry_run: bool) -> None:
    dest = skills_dir / name
    if dest.is_symlink():
        if dest.resolve() == source.resolve():
            return  # already correct
        if not dry_run:
            dest.unlink()
    elif dest.exists():
        print(f"  skip: {dest} exists as non-symlink", file=sys.stderr)
        return
    if dry_run:
        print(f"  would_link: {dest} -> {source}")
        return
    dest.symlink_to(source)


def install_koder_skills(skills_dir: Path, clawseat_root: Path, *, dry_run: bool) -> None:
    """Symlink koder's ClawSeat skills into the workspace skills/ dir."""
    skills_dir.mkdir(parents=True, exist_ok=True)
    koder_skills = {
        "gstack-harness": clawseat_root / "core" / "skills" / "gstack-harness",
        "clawseat-install": clawseat_root / "core" / "skills" / "clawseat-install",
        "clawseat-koder-frontstage": clawseat_root / "core" / "skills" / "clawseat-koder-frontstage",
        "socratic-requirements": clawseat_root / "core" / "skills" / "socratic-requirements",
        "agent-monitor": clawseat_root / "core" / "skills" / "agent-monitor",
        "tmux-basics": clawseat_root / "core" / "skills" / "tmux-basics",
    }
    for name, source in koder_skills.items():
        ensure_skill_symlink(skills_dir, name, source, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()

    if not workspace.exists():
        print(f"error: workspace does not exist: {workspace}", file=sys.stderr)
        return 1

    # Conflict handling: check for the 6 files init_koder will overwrite.
    conflicts = detect_managed_conflicts(workspace)
    if conflicts and not args.dry_run:
        policy = resolve_conflict_policy(args.on_conflict, conflicts, workspace)
        if policy == "abort":
            print("aborted: workspace untouched.", file=sys.stderr)
            return 2
        if policy == "backup":
            backup_dir = backup_managed_files(workspace, conflicts)
            print(f"backed up {len(conflicts)} file(s) to {backup_dir}")
        elif policy == "overwrite":
            print(f"overwriting {len(conflicts)} file(s) in place")

    profile_path, profile = load_profile_context(args.project, args.profile)
    files = build_workspace_files(
        project=args.project,
        profile_path=profile_path,
        profile=profile,
        feishu_group_id=args.feishu_group_id,
    )

    for filename, content in files.items():
        target = workspace / filename
        if args.dry_run:
            print(f"would_write: {target} ({len(content)} bytes)")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"wrote: {target}")

    # Install skill symlinks
    if not args.dry_run:
        print("installing koder skills...")
    install_koder_skills(workspace / "skills", REPO_ROOT, dry_run=args.dry_run)

    if not args.dry_run:
        print(f"\nkoder initialized for project '{args.project}' at {workspace}")
        print("next: run bootstrap, then start planner")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
