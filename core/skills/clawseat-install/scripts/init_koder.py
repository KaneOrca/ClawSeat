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
# products like pptx/png etc.) stays in place.
MANAGED_FILES = (
    "IDENTITY.md",
    "SOUL.md",
    "TOOLS.md",
    "MEMORY.md",
    "AGENTS.md",
    "WORKSPACE_CONTRACT.toml",
)


def detect_managed_conflicts(workspace: Path) -> list[str]:
    return [name for name in MANAGED_FILES if (workspace / name).exists()]


def backup_managed_files(workspace: Path, conflicts: list[str]) -> Path:
    """Move the 6 managed files into a .backup-<timestamp>/ subdir.

    Returns the backup dir path. Leaves every other file in the workspace
    (skills/, repos/, etc.) untouched.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = workspace / f".backup-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for name in conflicts:
        src = workspace / name
        dst = backup_dir / name
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
        "TOOLS.md": render_tools(
            REPO_ROOT,
            heartbeat_owner=heartbeat_owner,
            backend_seats=backend,
            default_backend_start_seats=default_backend,
        ),
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


def render_tools(
    clawseat_root: Path,
    *,
    heartbeat_owner: str,
    backend_seats: list[str],
    default_backend_start_seats: list[str],
) -> str:
    scripts = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
    shell = clawseat_root / "core" / "shell-scripts"
    backend_choices = "|".join(backend_seats) if backend_seats else "seat-id"
    backend_list = ", ".join(f"`{seat}`" for seat in backend_seats) if backend_seats else "(none)"
    default_backend = (
        ", ".join(f"`{seat}`" for seat in default_backend_start_seats)
        if default_backend_start_seats
        else "(none)"
    )
    return f"""# TOOLS.md — koder available commands

## 强制规则

**禁止直接用 tmux send-keys 给 seat 发自然语言消息来派发任务。**
**必须使用 dispatch_task.py 来派发，使用 notify_seat.py 来发通知。**
**在 OpenClaw 模式下，你当前就是 `{heartbeat_owner}`，禁止运行 `start_seat.py --seat {heartbeat_owner}`。**

每次向 seat 派发任务或完成交接时，必须使用下表中的脚本。
这些脚本会自动写入 TODO.md、更新 TASKS.md/STATUS.md、创建 handoff receipt、
并通过 send-and-verify.sh 通知目标 seat。
直接发消息会跳过所有这些持久化步骤，导致链路不可追踪。

## 调度脚本（必须使用）

**派发任务**（koder → planner，或任意 source → target）:
```bash
python3 {scripts}/dispatch_task.py \\
  --profile <profile.toml 路径> \\
  --source koder \\
  --target planner \\
  --task-id <TASK-ID> \\
  --title "<任务标题>" \\
  --objective "<任务目标和验收标准>"
```

**完成交接**（specialist → planner，或 planner → koder）:
```bash
python3 {scripts}/complete_handoff.py \\
  --profile <profile.toml 路径> \\
  --source <完成方> \\
  --target <接收方> \\
  --task-id <TASK-ID> \\
  --title "<交付标题>" \\
  --summary "<交付摘要>"
```

**发送通知**（非任务性消息、提醒、unblock）:
```bash
python3 {scripts}/notify_seat.py \\
  --profile <profile.toml 路径> \\
  --target <seat> \\
  --message "<消息内容>"
```

**启动后端 seat**:
```bash
python3 {scripts}/start_seat.py \\
  --profile <profile.toml 路径> \\
  --seat <{backend_choices}> \\
  --tool <claude|codex|gemini> \\
  --auth-mode <oauth|api> \\
  --provider <provider> \\
  --confirm-start
```

- 可由 frontstage 拉起的 backend seats: {backend_list}
- 推荐优先启动: {default_backend}
- 当前 OpenClaw agent 已经占据 `{heartbeat_owner}` frontstage，不要再为它创建 tmux session

## 状态检查

```bash
python3 {scripts}/render_console.py --profile <profile.toml 路径>
bash {shell}/check-engineer-status.sh <seat1> <seat2> ...
bash {shell}/detect-prompt-state.sh <tmux-session-name>
```

## tmux 通信（仅用于非结构化消息）

```bash
bash {shell}/send-and-verify.sh --project <project> <seat> "message"
```

> 只用于 notify_seat.py 不可用时的 fallback，或需要直接在 seat 的 TUI 里输入命令的场景。
> 日常任务派发和交接**禁止**用这个。

## 环境检查

```bash
python3 {clawseat_root}/core/preflight.py <project>
python3 {clawseat_root}/core/scripts/skill_manager.py check
bash {shell}/wait-for-text.sh -t <session> -p "pattern" -T <timeout>
```

## 项目 (project) —— 每次拉 seat 之前必须锚定

你可以**同时管理多个项目**。每个项目：
- 有自己的 **profile TOML** (`~/.agents/profiles/{{project}}-profile-dynamic.toml`)
- 有自己的 **tasks root** (`~/.agents/tasks/{{project}}/`) — TODO/DELIVERY/handoff 全在这
- 有自己的 **workspace root** (`~/.agents/workspaces/{{project}}/`) — 每个 seat 一个子目录
- 有自己的 **feishu group** — 团队协作的独立通信通道
- 拉起**独立的 planner/builder/reviewer/...** 一套团队

**默认项目是 `install`**（装机期唯一项目，你此刻所在的项目）。其他项目都是用户侧需求驱动的。

### 你当前所在的项目

读你自己的 `WORKSPACE_CONTRACT.toml` 的 `project` 字段，或者：
```bash
python3 -c "import tomllib; print(tomllib.loads(open('/Users/ywf/.openclaw/workspace-koder/WORKSPACE_CONTRACT.toml').read())['project'])"
```

### 新建项目（用户让你启动新团队时）

**准备工作（问用户）：**
1. 项目名（英文短名，作 profile / tasks_root / session 的路径锚定）
2. 项目描述（给 PROJECT.md）
3. **让用户手动在飞书里建一个新群**，把群 ID（`oc_xxx`）复制给你
   - 你不要尝试程序化建群，lark-cli 不支持
4. 和用户简单讨论后**选定 template**（默认 `full-team.toml`，6 seats）：
   ```bash
   # 推荐:  full-team       (koder+planner+builder-1+reviewer-1+qa-1+designer-1)
   # 轻量:  install         (koder+planner+builder-1+reviewer-1)
   # 起点:  starter         (仅 koder, 后续手动加 seat)
   ```

**执行步骤：**
```bash
# 1. 复制 profile 模板并 patch 项目名
cp {clawseat_root}/examples/starter/profiles/full-team.toml \
   ~/.agents/profiles/<new-project>-profile-dynamic.toml
# 用 sed 把所有 "my-project" 换成新名字, 以及补上 feishu_group_id

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
    account_id='main',  # 或用户指定
    session_key='<project>-setup',
    bound_by='{heartbeat_owner}',
    authorized=True,
)
"

# 4. 拉起新项目的 planner（在问 memory DB 拿 provider 配置之后）
python3 {scripts}/start_seat.py \\
  --profile ~/.agents/profiles/<new-project>-profile-dynamic.toml \\
  --seat planner \\
  --tool <X> --auth-mode <Y> --provider <Z> \\
  --confirm-start

# 5. dispatch 工作给 planner
python3 {scripts}/dispatch_task.py \\
  --profile ~/.agents/profiles/<new-project>-profile-dynamic.toml \\
  --source {heartbeat_owner} --target planner \\
  --task-id PROJECT-KICKOFF \\
  --title "<项目启动>" \\
  --objective "<用户要的东西>"
```

### 项目间隔离原则

- **seat 间的 dispatch/DELIVERY/handoff 都是 project-scoped**：planner-A 不能 dispatch 给 builder-B
- **Memory CC 是全局单实例**，所有项目共享同一份知识库 `~/.agents/memory/*.json`
- **你自己（koder）是唯一跨项目角色**，可以同时持有多个项目的 frontstage 控制权

### 常见错误（一定不要犯）

- 不要跳过 `--project-name` 直接跑 bootstrap_harness —— 会默认写到 `my-project` 污染它
- 不要把 install 项目的 profile 拷贝给新项目再改 —— 用 examples/starter/ 下的模板
- 不要用同一个 feishu group 绑两个项目 —— BRIDGE.toml 是 1:1 关系

## 拉 seat 之后的 TUI 可见性 —— 第一性原理：用户必须能看到 TUI

`start_seat.py` 做两件事：
1. `session start-engineer` — 建 tmux session，在里面启动 CLI（claude/codex/gemini）
2. `window open-engineer` — 打开 iTerm tab 并 attach 到这个 tmux session

**第 2 步失败是 non-fatal**：tmux 在后台跑，但用户看不到任何 TUI 窗口。这时你必须：

### 拉 seat 后**立即**验证可见性

```bash
# 检查整个项目所有 seat 的可见性（0=全部可见, 1=有不可见）
python3 {scripts}/tui_ctl.py \\
  --profile <profile.toml 路径> \\
  status

# 输出示例:
#   Seat        Session                       Tool    Clients Content Status
#   planner     install-planner-claude        claude  1       yes     VISIBLE
#   builder-1   install-builder-1-claude      claude  0       no      RUNNING_NOT_VISIBLE
#   reviewer-1  install-reviewer-1-codex      codex   1       yes     VISIBLE
```

`Status` 的三个值：
- `VISIBLE` — session 活着且有 iTerm client attached，用户能看见 TUI ✅
- `RUNNING_NOT_VISIBLE` — tmux session 在跑但没 iTerm tab attach ❌ 需要 recover
- `NOT_RUNNING` — tmux session 根本不存在 ❌ 需要重新 start_seat
- `NO_SESSION_RECORD` — ~/.agents/sessions/.../session.toml 都没生成 ❌ start_seat 彻底失败

### 恢复 RUNNING_NOT_VISIBLE 的 seat

```bash
# 自动: 批量重开 iTerm 窗口给所有不可见 seat
python3 {scripts}/tui_ctl.py \\
  --profile <profile.toml 路径> \\
  recover

# 或者单个手动:
python3 {clawseat_root}/core/scripts/agent_admin.py window open-engineer <seat> --project <project>

# 或者重建整个项目窗口 (一次性打开项目所有 seat 的 tabs):
python3 {clawseat_root}/core/scripts/agent_admin.py window open-monitor <project>
```

### 拉 seat 的**完整模板**（永远按这个走）

```bash
# Step 1: start (建 tmux + 启 CLI + 尝试开窗口)
python3 {scripts}/start_seat.py \\
  --profile <profile> --seat <X> \\
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

### 如果 pane 持续空白（CLI 启动失败）

最常见原因：
1. **provider 拼错**（`anthropix` vs `anthropic`、`minimaxi` vs `minimax`）
   - 先 `query_memory.py --search provider` 找合法 provider 列表
   - 检查 session.toml: `cat ~/.agents/sessions/<project>/<seat>/session.toml`
2. **secret 文件缺失**（auth_mode=api 但没 seed key）
   - 检查 `~/.agents/secrets/claude/<provider>/<seat>.env`
   - 从 `~/.agents/.env.global` 或 peer seat 拷贝
3. **tool binary 找不到**（claude / codex 没装）
   - `command -v claude` / `command -v codex` 先确认

修复后用 `--reset` 重建 tmux session：
```bash
python3 {scripts}/start_seat.py --profile <profile> --seat <X> \\
  --tool <X> --auth-mode <Y> --provider <Z> --confirm-start --reset
```

## 获取环境知识 (API keys, 路径, OpenClaw 配置) —— 硬性 SOP

**装 seat、配 provider、查 feishu group、查 API key 之前**：
永远先查 Memory CC 整理的本地知识库 `~/.agents/memory/*.json`。
**只有**本地知识库里没有的才委派 Memory CC 去查。

### Step 1: 直接查知识库（首选，0 延迟、0 幻觉、0 token 消耗）

```bash
# 精确路径查询（知道 key 在哪）：
python3 {clawseat_root}/core/skills/memory-oracle/scripts/query_memory.py --key credentials.keys.MINIMAX_API_KEY.value
python3 {clawseat_root}/core/skills/memory-oracle/scripts/query_memory.py --key github.gh_cli.active_login
python3 {clawseat_root}/core/skills/memory-oracle/scripts/query_memory.py --key openclaw.feishu.groups

# 模糊搜索（不确定 key 在哪）：
python3 {clawseat_root}/core/skills/memory-oracle/scripts/query_memory.py --search "minimax"
python3 {clawseat_root}/core/skills/memory-oracle/scripts/query_memory.py --search "feishu"

# 列所有文件 + 总览：
python3 {clawseat_root}/core/skills/memory-oracle/scripts/query_memory.py --status
python3 {clawseat_root}/core/skills/memory-oracle/scripts/query_memory.py --file openclaw --section feishu
```

当前知识库含 9 个类别：
`system`, `environment`, `credentials`, `openclaw`, `gstack`, `clawseat`, `repos`, `network`, `github`。

### Step 2: Memory CC dispatch（仅 Step 1 miss 时 fallback）

当本地知识库里**真的没有**所需事实（比如用户提到了一个从没记录过的新 API provider），
才委派 Memory CC 主动去扫描 / 联网查 / 更新知识库：

```bash
python3 {scripts}/dispatch_task.py \\
  --profile <profile.toml 路径> \\
  --source {heartbeat_owner} \\
  --target memory \\
  --task-id MEM-ENRICH-<timestamp> \\
  --title "补充 XXX 知识" \\
  --objective "本地知识库里没有 <具体项>, 请扫描/查证后写入对应的 ~/.agents/memory/*.json, 然后通过 memory_deliver.py 回复我"
```

Memory CC 完成后会自动更新知识库 + 发 DELIVERY.md 给你，你再回 Step 1 重查即可。

### 禁忌

- 不要在 TUI 里直接问用户 "你的 MINIMAX_API_KEY 是什么" —— 先 `--key credentials.keys.MINIMAX_API_KEY.value` 查
- 不要问用户 "feishu group id 选哪个" 前没先 `--key openclaw.feishu.groups` 列出候选
- 不要自己 `cat ~/.env*` / `cat ~/.openclaw/openclaw.json` 重造已被扫描好的事实 —— 用 query_memory.py

## 安装与更新

```bash
# 首次安装
python3 {clawseat_root}/shells/openclaw-plugin/install_openclaw_bundle.py
python3 {scripts}/bootstrap_harness.py --profile <profile> --project-name <project>
python3 {clawseat_root}/core/skills/clawseat-install/scripts/init_koder.py --workspace <workspace> --project <project>

# 更新后刷新所有 workspace（git pull ��后必须跑，零参数自动检测）
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
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    seat_list = "\n".join(f"- `{s}`" for s in seats)
    backend_list = "\n".join(f"- `{s}`" for s in backend_seats) or "- (none)"
    default_backend_list = "\n".join(f"- `{s}`" for s in default_backend_start_seats) or "- (none)"
    return f"""# MEMORY.md — koder project memory

## 项目绑定

- **project:** {project}
- **profile:** {profile_path}
- **initialized:** {now}

## Seat roster

{seat_list}

## Backend seats you may start

- frontstage owner: `{heartbeat_owner}` (already live in OpenClaw; never self-start)
{backend_list}

## Recommended startup order

{default_backend_list}

## 状态

- bootstrap: pending
- planner: not started
- feishu bridge: not configured
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

    role_details = []
    for detail in spec.get("role_details", []):
        role_details.append(f"- {detail}")
    backend_list = ", ".join(f"`{seat}`" for seat in backend_seats) if backend_seats else "(none)"

    return f"""# AGENTS.md — ClawSeat koder workspace

## Role

- **seat_id:** koder
- **role:** frontstage-supervisor
- **tool:** {spec.get('tool', 'claude')}
- **model:** {spec.get('model', 'opus')}

## Skills

{chr(10).join(skills_section)}

## Role details

{chr(10).join(role_details)}

## Authority

- patrol: ✅
- unblock: ✅
- escalation: ✅
- remind active loop owner: ✅
- dispatch: ❌ (planner only)
- review: ❌
- qa: ❌
- design: ❌

## Dispatch protocol

- **Always dispatch to planner** — never directly to specialist seats
- Use `dispatch_task.py` for formal task dispatch
- Use `notify_seat.py` for ad hoc messages
- Use `send-and-verify.sh` for tmux transport
- Every dispatch must produce a handoff receipt in `.tasks/patrol/handoffs/`
- In OpenClaw mode, the current agent already is `{heartbeat_owner}` — never run `start_seat.py --seat {heartbeat_owner}`
- Only backend seats may be started from this workspace: {backend_list}
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
    return f"""version = 1
seat_id = "{heartbeat_owner}"
role = "frontstage-supervisor"
project = "{project}"
profile = "{profile_path}"
initialized_at = "{now}"
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
