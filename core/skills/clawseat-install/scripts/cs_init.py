#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
_core_path = str(REPO_ROOT / "core")
if _core_path not in sys.path:
    sys.path.insert(0, _core_path)
from resolve import dynamic_profile_path as _dpp
from lib.real_home import real_user_home

PROJECT = "install"
# install-with-memory.toml declares the `memory` seat required by the
# canonical install flow (Phase 1). install.toml (legacy) omits memory
# and is incompatible with the 6-phase overlay flow.
PROFILE_TEMPLATE = REPO_ROOT / "examples" / "starter" / "profiles" / "install-with-memory.toml"
DYNAMIC_PROFILE = _dpp(PROJECT)
AGENT_ADMIN = REPO_ROOT / "core" / "scripts" / "agent_admin.py"
PRECHECK = REPO_ROOT / "core" / "preflight.py"
BOOTSTRAP = REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "bootstrap_harness.py"
START_SEAT = REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "start_seat.py"
RENDER_CONSOLE = REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "render_console.py"
TASKS_ROOT = real_user_home() / ".agents" / "tasks" / PROJECT
WORKSPACE_ROOT = real_user_home() / ".agents" / "workspaces" / PROJECT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap or resume the canonical ClawSeat install project."
    )
    parser.add_argument(
        "--refresh-profile",
        action="store_true",
        help="Rewrite /tmp/install-profile-dynamic.toml from the shipped install profile.",
    )
    parser.add_argument(
        "--skip-planner",
        action="store_true",
        help="Only prepare the install project and koder without launching planner.",
    )
    return parser.parse_args()


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "CLAWSEAT_ROOT": os.environ.get("CLAWSEAT_ROOT", str(REPO_ROOT))},
    )
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}")
    if result.stdout.strip():
        print(result.stdout.strip())
    return result


def ensure_profile(*, refresh: bool) -> Path:
    if refresh or not DYNAMIC_PROFILE.exists():
        DYNAMIC_PROFILE.write_text(PROFILE_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"profile_ready: {DYNAMIC_PROFILE} (source={PROFILE_TEMPLATE})")
    else:
        print(f"profile_reused: {DYNAMIC_PROFILE}")
    return DYNAMIC_PROFILE


def parse_session_states() -> dict[str, str]:
    result = subprocess.run(
        ["python3", str(AGENT_ADMIN), "session", "status", "--project", PROJECT],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {}
    states: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            states[parts[0]] = parts[-1]
    return states


def seat_running(states: dict[str, str], seat: str) -> bool:
    prefix = f"{PROJECT}-{seat}-"
    return any(name.startswith(prefix) and state == "running" for name, state in states.items())


def main() -> int:
    args = parse_args()
    profile_path = ensure_profile(refresh=args.refresh_profile)
    run_command(["python3", str(PRECHECK), PROJECT])

    planner_workspace = WORKSPACE_ROOT / "planner"
    koder_workspace = WORKSPACE_ROOT / "koder"
    needs_bootstrap = (
        not TASKS_ROOT.exists() or not koder_workspace.exists() or not planner_workspace.exists()
    )
    if needs_bootstrap:
        print("bootstrap_mode: fresh_or_repair")
        run_command(
            [
                "python3",
                str(BOOTSTRAP),
                "--profile",
                str(profile_path),
                "--project-name",
                PROJECT,
                "--start",
            ]
        )
    else:
        print("bootstrap_mode: resume_existing")

    states = parse_session_states()
    if not seat_running(states, "koder"):
        print("koder_state: starting")
        run_command(
            [
                "python3",
                str(START_SEAT),
                "--profile",
                str(profile_path),
                "--seat",
                "koder",
            ]
        )
        states = parse_session_states()
    else:
        print("koder_state: already_running")

    if args.skip_planner:
        print("planner_state: skipped")
    elif seat_running(states, "planner"):
        print("planner_state: already_running")
    else:
        print("planner_state: starting")
        run_command(
            [
                "python3",
                str(START_SEAT),
                "--profile",
                str(profile_path),
                "--seat",
                "planner",
                "--confirm-start",
            ]
        )

    run_command(
        [
            "python3",
            str(RENDER_CONSOLE),
            "--profile",
            str(profile_path),
        ]
    )
    print("feishu_followup_required:")
    print(
        f"- planner live 后，frontstage 应主动让用户把 main agent 拉进飞书群，并回报 group ID（无需 open_id）。"
    )
    print(
        "- main agent 在群里保持 requireMention=true；项目面向前台的 koder 账号在群里默认设置 requireMention=false；只有显式部署的系统 seat（如 warden）才需要额外放开。"
    )
    print(
        f"- 可用 `python3 {REPO_ROOT / 'core' / 'skills' / 'clawseat-install' / 'scripts' / 'find_feishu_group_ids.py'}` 查找已有 group ID。"
    )
    print(
        "- 一旦用户提供 group ID，frontstage 必须先确认这是绑定当前项目、切换到已有项目，还是用于创建新项目。"
    )
    print(
        "- 项目绑定确认后，frontstage 应立刻委派 planner 做群联调测试，提示用户“收到测试消息即可回复希望完成什么任务”，并并行拉起 reviewer。"
    )
    print(
        "- 如果当前链路是测试、验证、smoke 或回归重任务，frontstage 应让 planner 额外拉起 qa-1；qa-1 不属于 /cs 首启固定名单。"
    )
    print(
        "- 之后 planner 的 decision gate 与 closeout 应通过 `send_delegation_report.py` / `OC_DELEGATION_REPORT_V1` 回到同一个群；koder 在看到阶段收尾结果后，要先梳理 delivery trail 再更新项目文档。"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
