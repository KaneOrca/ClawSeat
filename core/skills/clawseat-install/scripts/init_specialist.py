#!/usr/bin/env python3
"""
init_specialist.py — systemic IDENTITY / SOUL / MEMORY scaffolding for
non-koder specialist seats (planner / builder / reviewer / qa / designer /
memory-oracle).

Why this exists
---------------
`agent_admin engineer create` materializes a specialist workspace with
AGENTS.md, WORKSPACE_CONTRACT.toml, WORKSPACE.md, TOOLS/protocol.md,
and TOOLS/memory.md (see core/scripts/agent_admin_workspace.py and
core/scripts/agent_admin_template.py). It does **not** write the role
charter trio — IDENTITY.md / SOUL.md / MEMORY.md — which every specialist
seat needs so its operating rules (reviewer: canonical verdicts; builder:
no raw tmux send-keys; memory: context is ephemeral) are visible at workspace
open time, not buried in a skill file.

Historically those three files were produced ad-hoc per seat during install
sweeps, or not at all. This script makes the bootstrap reproducible.

Scope
-----
* IN:  IDENTITY.md, SOUL.md, MEMORY.md
* OUT: AGENTS.md, WORKSPACE_CONTRACT.toml, TOOLS/*, HEARTBEAT_* — those are
       owned by agent_admin / init_koder respectively. This script deliberately
       does NOT touch them. Running both scripts in sequence is safe.

Usage
-----
    python3 init_specialist.py \\
        --profile /path/to/profile.toml \\
        --seat <seat-id> \\
        [--on-conflict ask|overwrite|backup|abort] \\
        [--force] \\
        [--dry-run]

``--force`` is a shortcut for ``--on-conflict overwrite`` so operators can
re-bootstrap a seat non-interactively.

The script refuses to bootstrap the profile's ``heartbeat_owner`` — that's
koder's job and belongs to init_koder.py.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core._bootstrap import CLAWSEAT_ROOT  # noqa: E402
from core.resolve import dynamic_profile_path  # noqa: E402

_harness_scripts = str(CLAWSEAT_ROOT / "core" / "skills" / "gstack-harness" / "scripts")
if _harness_scripts not in sys.path:
    sys.path.insert(0, _harness_scripts)

# real-home resolver bypasses sandbox HOME so `workspace_root = "~/…"` in the
# profile expands to the operator's real ~, not a runtime identity sandbox
# that never holds seat workspaces.
_core_lib = str(CLAWSEAT_ROOT / "core" / "lib")
if _core_lib not in sys.path:
    sys.path.insert(0, _core_lib)
from real_home import real_user_home  # noqa: E402

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from _seat_bootstrap import (  # noqa: E402
    backup_managed_files,
    detect_managed_conflicts,
    resolve_conflict_policy,
)

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore


MANAGED_FILES = (
    "IDENTITY.md",
    "SOUL.md",
    "MEMORY.md",
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scaffold IDENTITY/SOUL/MEMORY for a specialist seat.")
    p.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    p.add_argument("--seat", required=True, help="Specialist seat id (planner / builder-1 / reviewer-1 / qa-1 / designer-1 / memory).")
    p.add_argument(
        "--workspace",
        default="",
        help="Optional workspace override; defaults to <workspace_root>/<seat>/ from the profile.",
    )
    p.add_argument("--dry-run", action="store_true", help="Print intended writes without touching disk.")
    p.add_argument("--force", action="store_true", help="Shortcut for --on-conflict overwrite (non-interactive re-bootstrap).")
    p.add_argument(
        "--on-conflict",
        choices=("ask", "overwrite", "backup", "abort"),
        default="backup",
        help="When IDENTITY/SOUL/MEMORY already exist: back them up to .backup-<ts>/ (default), overwrite in place, ask interactively, or abort.",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Profile / template loading
# ---------------------------------------------------------------------------

def _resolve_profile_path(explicit: str) -> Path:
    p = Path(explicit).expanduser()
    if p.exists():
        return p
    raise FileNotFoundError(f"profile not found: {explicit}")


def _load_profile(profile_path: Path) -> dict[str, Any]:
    return tomllib.loads(profile_path.read_text(encoding="utf-8"))


def _load_template() -> dict[str, Any]:
    path = CLAWSEAT_ROOT / "core" / "templates" / "gstack-harness" / "template.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _find_engineer_spec(template: dict[str, Any], seat_id: str) -> dict[str, Any]:
    for eng in template.get("engineers", []):
        if eng.get("id") == seat_id:
            return dict(eng)
    raise RuntimeError(
        f"seat '{seat_id}' not found in gstack-harness template. "
        "Check core/templates/gstack-harness/template.toml for valid seat ids."
    )


def _apply_seat_override(spec: dict[str, Any], profile: dict[str, Any], seat_id: str) -> dict[str, Any]:
    """Layer the profile's [seat_overrides.<seat>] block on top of the template spec."""
    overrides = profile.get("seat_overrides", {}) or {}
    block = overrides.get(seat_id) or {}
    if not block:
        return spec
    merged = dict(spec)
    for key, value in block.items():
        merged[key] = value
    merged["id"] = seat_id
    return merged


def _resolve_workspace(
    profile: dict[str, Any], seat_id: str, explicit: str
) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    workspace_root = str(profile.get("workspace_root", "")).strip()
    if not workspace_root:
        raise RuntimeError(
            "profile missing workspace_root; cannot resolve seat workspace. "
            "Pass --workspace explicitly or fix the profile."
        )
    # Profile values may include "~" — expand via real_user_home() so sandbox
    # seats (isolated $HOME) resolve to the operator's real workspace tree.
    if workspace_root.startswith("~/") or workspace_root == "~":
        workspace_root = str(real_user_home()) + workspace_root[1:]
    return Path(workspace_root).expanduser().resolve() / seat_id


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_identity(*, seat_id: str, spec: dict[str, Any], project: str, profile_path: Path) -> str:
    role = str(spec.get("role", "specialist")).strip() or "specialist"
    tool = str(spec.get("tool", "-")).strip() or "-"
    auth_mode = str(spec.get("auth_mode", "-")).strip() or "-"
    provider = str(spec.get("provider", "-")).strip() or "-"
    model = str(spec.get("model", "-")).strip() or "-"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"""# IDENTITY.md — ClawSeat {seat_id}

- **Seat ID:** {seat_id}
- **Role:** {role}
- **Tool:** {tool}
- **Auth Mode:** {auth_mode}
- **Provider:** {provider}
- **Model:** {model}
- **Project:** {project}
- **Profile:** {profile_path}
- **Initialized:** {now}

## Mandate

See AGENTS.md for role specifics and the current skills loadout. See SOUL.md
for operating rules. Live seat status is in WORKSPACE_CONTRACT.toml —
do not duplicate it here.
"""


# Role-specific SOUL stanzas. Keep each short; the reusable spine lives at the
# top of render_soul() and applies to every specialist seat.
_ROLE_SPECIFIC_SOUL: dict[str, list[str]] = {
    "builder": [
        "实现代码 / 脚本 / 配置 / 模板 / 文档变更。",
        "完成后用 `complete_handoff.py` 把交付物返回 planner；不要自己闭环。",
        "测试要跑完整才能声称 pass；遇到 flaky 或 env-specific 失败，单独标注给 planner。",
        "需要破坏性命令（rm -rf / force push / DROP TABLE / kubectl delete …）时，先走 gstack-careful。",
    ],
    "reviewer": [
        "审查 builder 的交付物，发 canonical verdict：APPROVED / APPROVED_WITH_NITS / CHANGES_REQUESTED / BLOCKED / DECISION_NEEDED。",
        "Verdict 只发给 planner，不直接闭环给 koder/frontstage；planner 是路由决策点。",
        "审代码时顺带审 bash 调用日志和 PR diff 里的 `tmux send-keys`：specialist 给非自己 seat 发送即 protocol violation，verdict = CHANGES_REQUESTED。",
        "质量第一：不放过最后的 1% 缺陷；但也不为造分堆 nit。",
    ],
    "qa": [
        "smoke / 回归 / 验证 lane；读规格跑脚本，不改实现代码。",
        "完成后 `complete_handoff.py` 回 planner，附结构化结果（通过 / 失败 / 待决策）。",
        "不存储明文 secrets：验证 key / URL / provider 可用性，不做长期 owner。",
    ],
    "designer": [
        "视觉 / UX / 设计系统 lane。用 gstack-design-review 做 visual QA；用 gstack-design-shotgun 做多方案探索。",
        "交付物回 planner；不直接 push 代码仓。",
    ],
    "planner-dispatcher": [
        "接 koder 的任务，拆解成 specialist 子任务，逐跳 dispatch。",
        "decision-gate / 收尾通过 `send_delegation_report.py --report-status` 回到 Feishu 群；不在 tmux pane 里等人类输入。",
        "自己不执行实现 / 审查 / QA / 设计；只做路由、协调、收敛。",
        "运行 `send_delegation_report.py --check-auth` 确认 lark-cli 可用；auth 过期时提示 operator 跑 `lark-cli auth login`。",
    ],
    "planner": [
        "接 koder 的任务，拆解成 specialist 子任务，逐跳 dispatch。",
        "decision-gate / 收尾通过 `send_delegation_report.py --report-status` 回到 Feishu 群；不在 tmux pane 里等人类输入。",
        "自己不执行实现 / 审查 / QA / 设计；只做路由、协调、收敛。",
    ],
    "memory-oracle": [
        "只做 query / scan：用 `scan_environment.py` 扫机器，写 `~/.agents/memory/machine/*.json`。",
        "你不接 TODO.md 派发的任务 — 上游走 notify_seat.py --kind learning。",
        "context is ephemeral：每个对话从零开始，靠磁盘上的 JSON 库保持知识；完成后 /clear。",
    ],
}


def render_soul(seat_id: str, role: str) -> str:
    role_lines = _ROLE_SPECIFIC_SOUL.get(role, [
        f"未定义的角色 `{role}`。默认按 specialist 行事：按 TODO 做事，完成后 complete_handoff 回 planner。",
    ])
    role_block = "\n".join(f"- {line}" for line in role_lines)
    return f"""# SOUL.md — {seat_id} operating principles

## 核心原则

1. **你是 specialist seat，不是 koder / planner** — 永远从 planner 收到 TODO，完成后用 `complete_handoff.py` 返回 planner。
2. **单一角色边界** — 不跨界做别的 specialist 的活；需要别的角色时由 planner 拉起对应 seat。
3. **文档是事实来源** — TODO.md / DELIVERY.md / WORKSPACE_CONTRACT.toml 是 SSOT；tmux pane 是通知通道，不是事实数据库。
4. **禁止 raw tmux send-keys 给 peer seats** — 所有 seat 间消息只走 `complete_handoff.py` / `notify_seat.py` / `send-and-verify.sh`（fallback only）。
5. **在 SOUL / WORKSPACE_CONTRACT / AGENTS 里读完角色边界再动手** — 不靠记忆，不靠猜。

## 角色特化规则（`role = {role}`）

{role_block}

## 反谄媚

- 不说"好的收到""不错的想法"——对每个回答给判断
- 发现矛盾必须指出
- 含糊词（"优化""改进""更好"）必须追问到具体指标
- 不说"There are many ways"——选一个推荐并解释为什么

## 安全边界

- 不修改 OpenClaw 源码
- 不在 specialist 层长期存储 secrets；需要时读 `.env` 文件并用完即弃
- 每次 complete_handoff 都必须有可追溯的 receipt 落盘到 `~/.agents/tasks/<project>/patrol/handoffs/`
"""


def render_memory(*, seat_id: str, role: str, project: str, profile_path: Path) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"""# MEMORY.md — {seat_id} project snapshot

## 项目绑定 (render-time snapshot)

- **project:** {project}
- **seat_id:** {seat_id}
- **role:** {role}
- **profile:** {profile_path}
- **initialized:** {now}

## Authoritative state

Seat roster, runtime transport, and contract fingerprint live in
`WORKSPACE_CONTRACT.toml`. Read them there, not here:

```bash
python3 -c "import pathlib,tomllib; d=tomllib.loads((pathlib.Path.cwd() / 'WORKSPACE_CONTRACT.toml').read_text()); print(d)"
```

## Status

This file is a **render-time snapshot**, not a live state tracker.
For live state:

- `cat ~/.agents/tasks/{project}/{seat_id}/TODO.md` — your task inbox
- `cat ~/.agents/tasks/{project}/{seat_id}/DELIVERY.md` — your last delivery
- `ls ~/.agents/tasks/{project}/patrol/handoffs/` — recent dispatch activity
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_managed_files(
    *,
    seat_id: str,
    spec: dict[str, Any],
    project: str,
    profile_path: Path,
) -> dict[str, str]:
    role = str(spec.get("role", "specialist")).strip() or "specialist"
    return {
        "IDENTITY.md": render_identity(
            seat_id=seat_id, spec=spec, project=project, profile_path=profile_path
        ),
        "SOUL.md": render_soul(seat_id=seat_id, role=role),
        "MEMORY.md": render_memory(
            seat_id=seat_id, role=role, project=project, profile_path=profile_path
        ),
    }


def main() -> int:
    args = parse_args()

    profile_path = _resolve_profile_path(args.profile)
    profile = _load_profile(profile_path)
    project = str(profile.get("project_name", "")).strip() or "unknown"

    heartbeat_owner = str(profile.get("heartbeat_owner", "")).strip()
    if args.seat == heartbeat_owner:
        print(
            f"error: seat '{args.seat}' is the profile's heartbeat_owner; "
            "use init_koder.py for frontstage bootstrap.",
            file=sys.stderr,
        )
        return 2

    template = _load_template()
    try:
        template_spec = _find_engineer_spec(template, args.seat)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    spec = _apply_seat_override(template_spec, profile, args.seat)

    workspace = _resolve_workspace(profile, args.seat, args.workspace)
    if not workspace.exists():
        print(
            f"error: workspace does not exist: {workspace}. "
            "Run `agent_admin engineer create` or `start_seat.py` first so "
            "the seat directory is materialized.",
            file=sys.stderr,
        )
        return 1

    policy = "overwrite" if args.force else args.on_conflict

    conflicts = detect_managed_conflicts(workspace, MANAGED_FILES)
    if conflicts and not args.dry_run:
        policy = resolve_conflict_policy(policy, conflicts, workspace)
        if policy == "abort":
            print("aborted: workspace untouched.", file=sys.stderr)
            return 2
        if policy == "backup":
            backup_dir = backup_managed_files(workspace, conflicts)
            print(f"backed up {len(conflicts)} file(s) to {backup_dir}")
        elif policy == "overwrite":
            print(f"overwriting {len(conflicts)} file(s) in place")

    files = build_managed_files(
        seat_id=args.seat,
        spec=spec,
        project=project,
        profile_path=profile_path,
    )

    for filename, content in files.items():
        target = workspace / filename
        if args.dry_run:
            print(f"would_write: {target} ({len(content)} bytes)")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"wrote: {target}")

    if not args.dry_run:
        print(f"\n{args.seat} IDENTITY/SOUL/MEMORY scaffolded at {workspace}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
