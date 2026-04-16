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

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]  # clawseat-install/scripts/ → core/skills/ → core/ → ClawSeat
_core = str(REPO_ROOT / "core")
if _core not in sys.path:
    sys.path.insert(0, _core)

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Initialize OpenClaw agent workspace as koder.")
    p.add_argument("--workspace", required=True, help="Path to the OpenClaw agent workspace directory.")
    p.add_argument("--project", default="install", help="ClawSeat project name.")
    p.add_argument("--profile", help="Path to the dynamic profile TOML. Auto-resolved if omitted.")
    p.add_argument("--dry-run", action="store_true", help="Print what would be written without changing files.")
    return p.parse_args()


def load_template() -> dict:
    path = REPO_ROOT / "core" / "templates" / "gstack-harness" / "template.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def koder_spec(template: dict) -> dict:
    for eng in template.get("engineers", []):
        if eng.get("id") == "koder":
            return eng
    raise RuntimeError("koder seat not found in gstack-harness template")


def resolve_profile(project: str, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p
    from resolve import dynamic_profile_path
    return dynamic_profile_path(project)


def all_seats(template: dict) -> list[str]:
    return [eng["id"] for eng in template.get("engineers", []) if eng.get("id")]


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


def render_tools(clawseat_root: Path) -> str:
    scripts = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
    shell = clawseat_root / "core" / "shell-scripts"
    return f"""# TOOLS.md — koder available commands

## ClawSeat 调度脚本

| 命令 | 用途 |
|------|------|
| `python3 {scripts}/dispatch_task.py --profile <profile> --source koder --target <seat> ...` | 派发任务给 seat |
| `python3 {scripts}/complete_handoff.py --profile <profile> ...` | 完成交接 |
| `python3 {scripts}/notify_seat.py --profile <profile> --target <seat> --message "..."` | 发送通知 |
| `python3 {scripts}/render_console.py --profile <profile>` | 渲染控制台状态 |
| `python3 {scripts}/start_seat.py --profile <profile> --seat <id> --confirm-start` | 启动后端 seat |
| `python3 {scripts}/send_delegation_report.py --profile <profile> --check-auth` | 检查飞书认证 |

## Shell 工具

| 命令 | 用途 |
|------|------|
| `bash {shell}/send-and-verify.sh --project <project> <seat> "message"` | 发送 tmux 消息并验证 |
| `bash {shell}/check-engineer-status.sh <seat1> <seat2> ...` | 检查 seat 状态 |
| `bash {shell}/detect-prompt-state.sh <session>` | 检测 seat 提示状态 |
| `bash {shell}/wait-for-text.sh -t <session> -p "pattern" -T <timeout>` | 等待 pane 输出 |

## Preflight

| 命令 | 用途 |
|------|------|
| `python3 {clawseat_root}/core/preflight.py <project>` | 环境预检 |
| `python3 {clawseat_root}/core/scripts/skill_manager.py check` | 技能注册表验证 |

## 安装

| 命令 | 用途 |
|------|------|
| `python3 {clawseat_root}/shells/openclaw-plugin/install_openclaw_bundle.py` | 安装/更新 skill symlinks |
| `python3 {scripts}/bootstrap_harness.py --profile <profile> --project-name <project>` | 项目 bootstrap |
"""


def render_memory(project: str, profile_path: Path, seats: list[str]) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    seat_list = "\n".join(f"- `{s}`" for s in seats)
    return f"""# MEMORY.md — koder project memory

## 项目绑定

- **project:** {project}
- **profile:** {profile_path}
- **initialized:** {now}

## Seat roster

{seat_list}

## 状态

- bootstrap: pending
- planner: not started
- feishu bridge: not configured
"""


def render_agents(spec: dict, clawseat_root: Path) -> str:
    skills_section = []
    for skill_path in spec.get("skills", []):
        expanded = skill_path.replace("{CLAWSEAT_ROOT}", str(clawseat_root))
        expanded = os.path.expanduser(expanded)
        name = Path(expanded).parent.name
        skills_section.append(f"- `{name}`: `{expanded}`")

    role_details = []
    for detail in spec.get("role_details", []):
        role_details.append(f"- {detail}")

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
"""


def render_contract(project: str, profile_path: Path, seats: list[str]) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    seat_toml = ", ".join(f'"{s}"' for s in seats)
    return f"""version = 1
seat_id = "koder"
role = "frontstage-supervisor"
project = "{project}"
profile = "{profile_path}"
initialized_at = "{now}"
seats = [{seat_toml}]
heartbeat_owner = "koder"
active_loop_owner = "planner"
default_notify_target = "planner"
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

    profile_path = resolve_profile(args.project, args.profile)
    template = load_template()
    spec = koder_spec(template)
    seats = all_seats(template)

    files = {
        "IDENTITY.md": render_identity(args.project, profile_path),
        "SOUL.md": render_soul(),
        "TOOLS.md": render_tools(REPO_ROOT),
        "MEMORY.md": render_memory(args.project, profile_path, seats),
        "AGENTS.md": render_agents(spec, REPO_ROOT),
        "WORKSPACE_CONTRACT.toml": render_contract(args.project, profile_path, seats),
    }

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
