#!/usr/bin/env python3
"""Koder patrol supervisor for cartooner.

This helper turns patrol output into reminder recommendations for engineer-b.
It does not dispatch downstream work; it only decides whether engineer-b
should be nudged to consume deliveries or resolve stalled seats.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


CLAWSEAT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONSUMER_REPO_ROOT = Path.home() / "coding" / "cartooner"
CONSUMER_REPO_ROOT = Path(
    os.environ.get("CARTOONER_REPO_ROOT", str(DEFAULT_CONSUMER_REPO_ROOT))
).expanduser()
TASKS_ROOT = CONSUMER_REPO_ROOT / ".tasks"
PATROL_DIR = TASKS_ROOT / "patrol"
STATE_FILE = PATROL_DIR / "koder_reminder_state.json"
TASKS_MD = TASKS_ROOT / "TASKS.md"
CHECK_SCRIPT = CLAWSEAT_ROOT / "adapters" / "cartooner" / "scripts" / "check-cartooner-status.sh"
SEND_SCRIPT = CLAWSEAT_ROOT / ".scripts" / "send-and-verify.sh"

STATUS_RE = re.compile(r"^(engineer-[a-z]):\s+([A-Z_]+)(?:\s+\((.*)\))?$")
TASK_ROW_RE = re.compile(r"^\|\s*(FE-\d+)\s*\|")


@dataclass
class SeatSnapshot:
    seat: str
    status: str
    detail: str
    todo_id: Optional[str]
    delivery_id: Optional[str]
    todo_path: Path
    delivery_path: Path


@dataclass
class Reminder:
    seat: str
    task_id: str
    status: str
    message: str
    age_minutes: int


@dataclass
class Note:
    seat: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect cartooner patrol state and suggest or send reminders to engineer-b."
        )
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send the composed reminder to engineer-b via send-and-verify.sh.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cooldown suppression for identical reminder payloads.",
    )
    parser.add_argument(
        "--delivered-threshold-minutes",
        type=int,
        default=30,
        help="Minimum delivery age before reminding engineer-b to consume it.",
    )
    parser.add_argument(
        "--stalled-threshold-minutes",
        type=int,
        default=20,
        help="Minimum TODO age before reminding engineer-b about stalled downstream work.",
    )
    parser.add_argument(
        "--cooldown-minutes",
        type=int,
        default=60,
        help="Cooldown window for identical reminder payloads.",
    )
    parser.add_argument(
        "--session",
        default="engineer-b",
        help="Target session name for reminder delivery.",
    )
    return parser.parse_args()


def read_task_id(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("task_id:"):
            _, value = line.split(":", 1)
            task_id = value.strip()
            return task_id or None
    return None


def file_age_minutes(path: Path) -> int:
    if not path.exists():
        return 0
    age_seconds = max(0, time.time() - path.stat().st_mtime)
    return int(age_seconds // 60)


def load_task_statuses() -> Dict[str, str]:
    statuses: Dict[str, str] = {}
    if not TASKS_MD.exists():
        return statuses

    for line in TASKS_MD.read_text(encoding="utf-8").splitlines():
        if not TASK_ROW_RE.match(line):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 4:
            continue
        task_id, _, _, status = parts[:4]
        statuses[task_id] = status.lower()
    return statuses


def run_patrol() -> List[str]:
    result = subprocess.run(
        [str(CHECK_SCRIPT)],
        cwd=str(CLAWSEAT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Patrol script failed with code {result.returncode}: {result.stderr.strip()}"
        )
    return [line for line in result.stdout.splitlines() if line.strip()]


def parse_patrol(lines: List[str]) -> Dict[str, SeatSnapshot]:
    snapshots: Dict[str, SeatSnapshot] = {}
    for line in lines:
        match = STATUS_RE.match(line.strip())
        if not match:
            continue
        seat, status, detail = match.groups()
        todo_path = TASKS_ROOT / seat / "TODO.md"
        delivery_path = TASKS_ROOT / seat / "DELIVERY.md"
        snapshots[seat] = SeatSnapshot(
            seat=seat,
            status=status,
            detail=detail or "",
            todo_id=read_task_id(todo_path),
            delivery_id=read_task_id(delivery_path),
            todo_path=todo_path,
            delivery_path=delivery_path,
        )
    return snapshots


def should_ignore(task_id: Optional[str], task_statuses: Dict[str, str]) -> bool:
    if not task_id:
        return True
    return task_statuses.get(task_id) == "completed"


def build_reminders(
    snapshots: Dict[str, SeatSnapshot],
    task_statuses: Dict[str, str],
    delivered_threshold: int,
    stalled_threshold: int,
) -> tuple[List[Reminder], List[Note]]:
    reminders: List[Reminder] = []
    notes: List[Note] = []

    for seat, snapshot in snapshots.items():
        if seat == "engineer-b":
            if should_ignore(snapshot.todo_id, task_statuses):
                if snapshot.todo_id and snapshot.status not in {"IDLE", "DELIVERED"}:
                    notes.append(
                        Note(
                            seat=seat,
                            message=(
                                f"- {seat} 仍显示 {snapshot.status}，但 TODO={snapshot.todo_id} 在 TASKS.md 中已是 completed；"
                                "更像链路清理/文档漂移，不再触发提醒。"
                            ),
                        )
                    )
                continue
            todo_age = file_age_minutes(snapshot.todo_path)
            if snapshot.status in {"STALLED", "BLOCKED", "DECISION_NEEDED", "DRIFT", "CRASHED"}:
                if snapshot.status in {"BLOCKED", "DECISION_NEEDED", "CRASHED"} or todo_age >= stalled_threshold:
                    task_id = snapshot.todo_id or "unknown-task"
                    reminders.append(
                        Reminder(
                            seat=seat,
                            task_id=task_id,
                            status=snapshot.status,
                            age_minutes=todo_age,
                            message=(
                                f"- {seat} 当前为 {snapshot.status}，active TODO={task_id}，"
                                f"已挂起约 {todo_age} 分钟。请先消费当前链路并写出下一跳。"
                            ),
                        )
                    )
            continue

        if (
            snapshot.status == "DELIVERED"
            and snapshot.todo_id
            and snapshot.todo_id == snapshot.delivery_id
            and not should_ignore(snapshot.todo_id, task_statuses)
        ):
            delivery_age = file_age_minutes(snapshot.delivery_path)
            if delivery_age >= delivered_threshold:
                reminders.append(
                    Reminder(
                        seat=seat,
                        task_id=snapshot.delivery_id or snapshot.todo_id,
                        status=snapshot.status,
                        age_minutes=delivery_age,
                        message=(
                            f"- {seat} 已交付 {snapshot.delivery_id}，但该交付仍未见 engineer-b 消费，"
                            f"已等待约 {delivery_age} 分钟。请阅读 DELIVERY.md 并决定下一跳。"
                        ),
                    )
                )
            continue

        if snapshot.status == "DELIVERED" and should_ignore(snapshot.delivery_id, task_statuses):
            if snapshot.delivery_id:
                notes.append(
                    Note(
                        seat=seat,
                        message=(
                            f"- {seat} 的 delivery={snapshot.delivery_id} 在 TASKS.md 中已是 completed；"
                            "视为历史完成态，不再提醒 engineer-b。"
                        ),
                    )
                )
            continue

        if snapshot.status in {"STALLED", "DRIFT", "BLOCKED", "DECISION_NEEDED"}:
            if should_ignore(snapshot.todo_id, task_statuses):
                continue
            todo_age = file_age_minutes(snapshot.todo_path)
            if snapshot.status in {"BLOCKED", "DECISION_NEEDED"} or todo_age >= stalled_threshold:
                task_id = snapshot.todo_id or "unknown-task"
                reminders.append(
                    Reminder(
                        seat=seat,
                        task_id=task_id,
                        status=snapshot.status,
                        age_minutes=todo_age,
                        message=(
                            f"- {seat} 当前为 {snapshot.status}，TODO={task_id} 已挂起约 {todo_age} 分钟。"
                            "请确认是否需要重发提醒、修正 transport，或改派。"
                        ),
                    )
                )
    return reminders, notes


def load_state() -> Dict[str, float]:
    if not STATE_FILE.exists():
        return {}
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_state(state: Dict[str, float]) -> None:
    PATROL_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def build_fingerprint(reminders: List[Reminder]) -> str:
    parts = sorted(
        f"{item.seat}:{item.task_id}:{item.status}:{item.age_minutes // 10}"
        for item in reminders
    )
    return "|".join(parts)


def compose_message(reminders: List[Reminder]) -> str:
    lines = [
        "监督提醒：当前 cartooner active loop 检测到停滞/待消费迹象。",
        "",
        "请优先：",
        "1. 阅读相关 DELIVERY.md / TODO.md",
        "2. 判断下一跳",
        "3. 更新 TASKS.md / STATUS.md / 下游 TODO.md",
        "",
        "当前触发点：",
    ]
    lines.extend(item.message for item in reminders)
    return "\n".join(lines)


def maybe_send(session: str, message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SEND_SCRIPT), session, message],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    args = parse_args()
    patrol_lines = run_patrol()
    task_statuses = load_task_statuses()
    snapshots = parse_patrol(patrol_lines)
    reminders, notes = build_reminders(
        snapshots,
        task_statuses,
        delivered_threshold=args.delivered_threshold_minutes,
        stalled_threshold=args.stalled_threshold_minutes,
    )

    print("Cartooner patrol supervisor")
    print(f"- branch root: {REPO_ROOT}")
    print("- patrol snapshot:")
    for line in patrol_lines:
        print(f"  {line}")
    if notes:
        print("- notes:")
        for item in notes:
            print(f"  {item.message}")

    if not reminders:
        print("- verdict: no reminder needed")
        return 0

    fingerprint = build_fingerprint(reminders)
    state = load_state()
    last_sent_at = state.get(fingerprint, 0.0)
    cooldown_seconds = args.cooldown_minutes * 60
    now = time.time()
    suppressed = bool(
        last_sent_at and not args.force and (now - last_sent_at) < cooldown_seconds
    )

    print("- verdict: reminder recommended")
    for item in reminders:
        print(f"  {item.message}")

    message = compose_message(reminders)
    if suppressed:
        remaining = int((cooldown_seconds - (now - last_sent_at)) // 60)
        print(f"- action: suppressed by cooldown ({remaining} min remaining)")
        print("- composed reminder:")
        print(message)
        return 0

    if not args.send:
        print("- action: dry-run only (use --send to notify engineer-b)")
        print("- composed reminder:")
        print(message)
        return 0

    result = maybe_send(args.session, message)
    if result.returncode != 0:
        print("- action: send failed")
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        return result.returncode

    state[fingerprint] = now
    save_state(state)
    print("- action: reminder sent")
    if result.stdout.strip():
        print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
