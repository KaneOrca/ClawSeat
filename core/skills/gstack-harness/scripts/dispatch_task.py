#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from _common import (
    append_status_note,
    broadcast_feishu_group_message,
    build_notify_message,
    load_profile,
    legacy_feishu_group_broadcast_enabled,
    notify,
    require_success,
    upsert_tasks_row,
    utc_now_iso,
    write_json,
    write_todo,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch a task to a target seat.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--source", default="planner", help="Seat dispatching the task.")
    parser.add_argument("--target", required=True, help="Target seat.")
    parser.add_argument("--task-id", required=True, help="Task id.")
    parser.add_argument("--title", required=True, help="Task title.")
    parser.add_argument("--objective", required=True, help="Objective/body text for the TODO.")
    parser.add_argument("--reply-to", help="Seat that should receive completion back from the target.")
    parser.add_argument("--notes", default="dispatched via gstack-harness", help="TASKS.md note.")
    parser.add_argument("--status-note", help="Optional STATUS.md note.")
    parser.add_argument("--skip-notify", action="store_true", help="Write docs but skip tmux notification.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    todo_path = profile.todo_path(args.target)
    reply_to = args.reply_to or args.source
    source_role = profile.seat_roles.get(args.source, "")
    target_role = profile.seat_roles.get(args.target, "")
    write_todo(
        todo_path,
        task_id=args.task_id,
        project=profile.project_name,
        owner=args.target,
        status="pending",
        title=args.title,
        objective=args.objective,
        source=args.source,
        reply_to=reply_to,
    )
    upsert_tasks_row(
        profile.tasks_doc,
        task_id=args.task_id,
        title=args.title,
        owner=args.target,
        status="pending",
        notes=args.notes,
    )
    append_status_note(
        profile.status_doc,
        args.status_note or f"{args.source} dispatched {args.task_id} to {args.target}",
    )
    receipt = {
        "kind": "dispatch",
        "task_id": args.task_id,
        "source": args.source,
        "target": args.target,
        "title": args.title,
        "todo_path": str(todo_path),
        "reply_to": reply_to,
        "assigned_at": utc_now_iso(),
        "notified_at": None,
        "notify_message": None,
    }
    if not args.skip_notify:
        message = build_notify_message(
            args.target,
            todo_path,
            args.task_id,
            source=args.source,
            reply_to=reply_to,
        )
        result = notify(profile, args.target, message)
        require_success(result, "dispatch notify")
        receipt["notified_at"] = utc_now_iso()
        receipt["notify_message"] = message
        should_broadcast = (
            source_role in {"planner", "planner-dispatcher"}
            or target_role in {"planner", "planner-dispatcher"}
            or args.source == profile.active_loop_owner
            or args.target == profile.active_loop_owner
        )
        if should_broadcast and legacy_feishu_group_broadcast_enabled():
            if source_role in {"planner", "planner-dispatcher"} and target_role not in {
                "planner",
                "planner-dispatcher",
            }:
                group_message = (
                    f"{profile.project_name} 项目 planner 已向 {args.target} 发布任务 {args.task_id}："
                    f"{args.title}. 回复链路 {reply_to}."
                )
            elif target_role in {"planner", "planner-dispatcher"} and source_role not in {
                "planner",
                "planner-dispatcher",
            }:
                group_message = (
                    f"{profile.project_name} 项目 planner 已收到任务 {args.task_id}，"
                    f"来自 {args.source}：{args.title}. 回复链路 {reply_to}."
                )
            else:
                group_message = (
                    f"{profile.project_name} 项目 planner 任务流转 {args.task_id}："
                    f"{args.source} -> {args.target}，{args.title}."
                )
            broadcast = broadcast_feishu_group_message(group_message)
            receipt["feishu_group_broadcast"] = broadcast
            if broadcast.get("status") == "failed":
                print(
                    f"warn: feishu group broadcast failed for {args.task_id}: "
                    f"{broadcast.get('stderr') or broadcast.get('stdout') or broadcast.get('reason', 'unknown')}",
                    file=sys.stderr,
                )
        elif should_broadcast:
            receipt["feishu_group_broadcast"] = {
                "status": "skipped",
                "reason": "legacy_group_broadcast_disabled",
            }
    receipt_path = profile.handoff_path(args.task_id, args.source, args.target)
    write_json(receipt_path, receipt)
    print(f"dispatched {args.task_id} -> {args.target}")
    print(f"todo: {todo_path}")
    print(f"receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
