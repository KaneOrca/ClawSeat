#!/usr/bin/env python3
from __future__ import annotations

import argparse

from dynamic_common import (
    append_status_note,
    build_notify_message,
    load_profile,
    notify,
    preferred_planner_seat,
    require_success,
    utc_now_iso,
    write_json,
    write_todo,
    upsert_tasks_row,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch a task to a dynamic-roster seat.")
    parser.add_argument("--profile", required=True, help="Path to the dynamic profile TOML.")
    parser.add_argument("--source", help="Seat dispatching the task. Defaults to the resolved planner seat.")
    parser.add_argument("--target", required=True, help="Target seat.")
    parser.add_argument("--task-id", required=True, help="Task id.")
    parser.add_argument("--title", required=True, help="Task title.")
    parser.add_argument("--objective", required=True, help="Objective/body text for the TODO.")
    parser.add_argument("--reply-to", help="Seat that should receive completion back from the target.")
    parser.add_argument("--notes", default="dispatched via dynamic-roster harness", help="TASKS.md note.")
    parser.add_argument("--status-note", help="Optional STATUS.md note.")
    parser.add_argument("--skip-notify", action="store_true", help="Write docs but skip tmux notification.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    source = args.source or preferred_planner_seat(profile)
    todo_path = profile.todo_path(args.target)
    reply_to = args.reply_to or source
    write_todo(
        todo_path,
        task_id=args.task_id,
        project=profile.project_name,
        owner=args.target,
        status="pending",
        title=args.title,
        objective=args.objective,
        source=source,
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
        args.status_note or f"{source} dispatched {args.task_id} to {args.target}",
    )
    receipt = {
        "project": profile.project_name,
        "kind": "dispatch",
        "task_id": args.task_id,
        "source": source,
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
            profile.project_name,
            args.target,
            todo_path,
            args.task_id,
            source=source,
            reply_to=reply_to,
        )
        result = notify(profile, args.target, message)
        require_success(result, "dispatch notify")
        receipt["notified_at"] = utc_now_iso()
        receipt["notify_message"] = message
    receipt_path = profile.handoff_path(args.task_id, source, args.target)
    write_json(receipt_path, receipt)
    print(f"dispatched {args.task_id} -> {args.target}")
    print(f"todo: {todo_path}")
    print(f"receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
