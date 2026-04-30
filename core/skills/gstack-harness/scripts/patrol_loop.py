#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from _common import executable_command, load_profile, materialize_profile_runtime, require_success, run_command


MAX_REWAKES_PER_CYCLE = 5
REWAKE_COOLDOWN_SECONDS = 30 * 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the patrol loop for a project profile.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--send", action="store_true", help="Allow reminders to be sent.")
    return parser.parse_args()


def run_auto_supersede(profile, *, age_days: int = 3) -> None:
    cmd = [
        sys.executable,
        str(profile.agent_admin),
        "task",
        "auto-supersede",
        "--project",
        profile.project_name,
        "--age-days",
        str(age_days),
    ]
    result = run_command(cmd, cwd=profile.repo_root)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        stderr = result.stderr.strip()
        suffix = f": {stderr}" if stderr else ""
        print(f"warn: task auto-supersede failed{suffix}", file=sys.stderr)


def _tasks_root() -> Path:
    return Path.home() / ".agents" / "tasks"


def _rewake_log_path() -> Path:
    return Path.home() / ".agents" / "logs" / "stale-handoff-rewake.log"


def detect_stale_handoffs(project: str, threshold_hours: int = 2) -> list[dict[str, Any]]:
    handoffs_dir = _tasks_root() / project / "patrol" / "handoffs"
    if not handoffs_dir.is_dir():
        return []

    now = time.time()
    cutoff = now - threshold_hours * 3600
    stale: list[dict[str, Any]] = []
    for json_path in sorted(handoffs_dir.glob("*__*__*.json")):
        if json_path.name.endswith(".consumed") or json_path.with_suffix(".json.consumed").exists():
            continue
        try:
            stat = json_path.stat()
        except OSError:
            continue
        if stat.st_mtime >= cutoff:
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        age_hours = int((now - stat.st_mtime) / 3600)
        stale.append(
            {
                "task_id": data.get("task_id") or json_path.name.split("__", 1)[0],
                "source": data.get("source") or "<unknown>",
                "target": data.get("target") or "<unknown>",
                "age_hours": age_hours,
                "json_path": str(json_path),
            }
        )
    return stale


def _recent_rewake_keys(log_path: Path, *, now: float, cooldown_seconds: int) -> set[str]:
    if not log_path.exists():
        return set()
    recent: set[str] = set()
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        try:
            ts = float(parts[0])
        except ValueError:
            continue
        if now - ts <= cooldown_seconds:
            recent.add(parts[3])
    return recent


def _append_rewake_log(log_path: Path, *, project: str, handoff: dict[str, Any], now: float) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = "\t".join(
        [
            f"{now:.3f}",
            project,
            str(handoff.get("target", "<unknown>")),
            str(handoff.get("json_path", "")),
            str(handoff.get("task_id", "<unknown>")),
        ]
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _is_codex_busy(target: str) -> bool:
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", target, "-p"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False

    lines = result.stdout.splitlines()
    tail = "\n".join(lines[-3:])
    return (
        "Working" in tail
        or "Thinking" in tail
        or "• " in tail
        or "background terminal running" in tail
    )


def re_wake_stale_handoffs(project: str, threshold_hours: int = 2) -> int:
    stale = detect_stale_handoffs(project, threshold_hours=threshold_hours)
    if not stale:
        return 0
    now = time.time()
    log_path = _rewake_log_path()
    recent = _recent_rewake_keys(log_path, now=now, cooldown_seconds=REWAKE_COOLDOWN_SECONDS)
    send_script = Path.home() / "ClawSeat" / "core" / "shell-scripts" / "send-and-verify.sh"

    sent = 0
    for handoff in stale:
        if sent >= MAX_REWAKES_PER_CYCLE:
            break
        json_path = str(handoff.get("json_path", ""))
        if json_path in recent:
            continue
        target = str(handoff.get("target") or "")
        if not target or target == "<unknown>":
            continue
        if _is_codex_busy(target):
            continue
        msg = (
            f"[TASK-QUEUE] 你有未处理的 handoff: {handoff['task_id']}(已 {handoff['age_hours']}h)。\n"
            "请读 TODO.md 头部处理。"
        )
        subprocess.run(
            ["bash", str(send_script), "--project", project, target, msg],
            check=False,
        )
        _append_rewake_log(log_path, project=project, handoff=handoff, now=now)
        sent += 1
    return sent


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    materialize_profile_runtime(profile)
    cmd = executable_command(profile.patrol_script)
    if args.send:
        cmd.append("--send")
    result = run_command(cmd, cwd=profile.repo_root)
    require_success(result, "patrol_loop")
    if result.stdout.strip():
        print(result.stdout.strip())
    run_auto_supersede(profile)
    rewake_count = re_wake_stale_handoffs(profile.project_name)
    if rewake_count:
        print(f"[STALE-HANDOFF-REWAKE:project={profile.project_name},count={rewake_count}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
