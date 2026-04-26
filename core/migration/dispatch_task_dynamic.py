#!/usr/bin/env python3
# DEPRECATED (2026-04-22): transitional dynamic-roster compatibility shim.
# Keep until every live profile has `[dynamic_roster].enabled = true` and the
# router-level migration cleanup can delete the last legacy/static caller.
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path so core.lib.state is importable.
_REPO_ROOT_DYN = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_DYN) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_DYN))

from dynamic_common import (
    add_notify_args,
    append_status_note,
    assert_target_not_memory,
    build_notify_message,
    load_profile,
    notify,
    preferred_planner_seat,
    require_success,
    resolve_notify,
    utc_now_iso,
    write_json,
    write_todo,
    upsert_tasks_row,
)


def _write_dispatch_to_ledger(
    *,
    task_id: str,
    project: str,
    source: str,
    target: str,
    role_hint: str | None,
    title: str,
    correlation_id: str | None = None,
) -> None:
    """Write task + task.dispatched event to state.db. Defensive: never fails dispatch."""
    try:
        from datetime import datetime, timezone as _tz
        from core.lib.state import open_db, record_task_dispatched, record_event, Task
        task = Task(
            id=task_id,
            project=project,
            source=source,
            target=target,
            role_hint=role_hint,
            status="dispatched",
            title=title,
            correlation_id=correlation_id,
            opened_at=datetime.now(_tz.utc).isoformat(timespec="seconds"),
        )
        with open_db() as conn:
            record_task_dispatched(conn, task)
            record_event(conn, "task.dispatched", project,
                         task_id=task_id, source=source, target=target)
    except Exception as exc:
        print(f"warn: state.db unavailable, skipping ledger write: {exc}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch a task to a dynamic-roster seat.")
    parser.add_argument("--profile", required=True, help="Path to the dynamic profile TOML.")
    parser.add_argument("--source", help="Seat dispatching the task. Defaults to the resolved planner seat.")
    _target_group = parser.add_mutually_exclusive_group(required=True)
    _target_group.add_argument("--target", help="Target seat (explicit seat id).")
    _target_group.add_argument(
        "--target-role",
        metavar="ROLE",
        help="Pick least-busy live seat with this role from state.db.",
    )
    parser.add_argument("--task-id", required=True, help="Task id.")
    parser.add_argument("--title", required=True, help="Task title.")
    parser.add_argument("--objective", required=True, help="Objective/body text for the TODO.")
    parser.add_argument(
        "--test-policy",
        required=True,
        choices=["UPDATE", "FREEZE", "EXTEND", "N/A"],
        help=(
            "UPDATE: tests must follow code changes; "
            "FREEZE: do not touch tests; "
            "EXTEND: add new tests only; "
            "N/A: doc/config only, no testable code"
        ),
    )
    parser.add_argument("--reply-to", help="Seat that should receive completion back from the target.")
    parser.add_argument("--notes", default="dispatched via dynamic-roster harness", help="TASKS.md note.")
    parser.add_argument("--status-note", help="Optional STATUS.md note.")
    add_notify_args(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    do_notify = resolve_notify(args)
    role_hint: str | None = getattr(args, "target_role", None)

    # Resolve --target-role via state.db (requires project_name from profile).
    profile = None
    if role_hint:
        profile = load_profile(args.profile)
        try:
            from core.lib.state import open_db, pick_least_busy_seat
            with open_db() as conn:
                picked = pick_least_busy_seat(conn, profile.project_name, role_hint)
        except Exception as exc:
            print(f"warn: state.db unavailable for role resolution: {exc}", file=sys.stderr)
            picked = None
        if picked is None:
            print(
                f"seat_needed: no live seat with role={role_hint!r} in "
                f"project={profile.project_name!r}. "
                "Launch one or specify --target explicitly.",
                file=sys.stderr,
            )
            return 3
        args.target = picked.seat_id
        print(f"target-role resolved: {role_hint} -> {args.target}", file=sys.stderr)

    # T9: block dispatch to memory before profile load — memory is a
    # synchronous oracle, never a task worker. See _common.py guard docstring.
    assert_target_not_memory(args.target, "dispatch_task_dynamic.py")
    if profile is None:
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
        test_policy=args.test_policy,
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
        args.status_note or f"{source} dispatched {args.task_id} to {args.target} test_policy={args.test_policy}",
    )
    receipt = {
        "project": profile.project_name,
        "kind": "dispatch",
        "task_id": args.task_id,
        "source": source,
        "target": args.target,
        "title": args.title,
        "test_policy": args.test_policy,
        "todo_path": str(todo_path),
        "reply_to": reply_to,
        "assigned_at": utc_now_iso(),
        "notified_at": None,
        "notify_message": None,
    }
    if do_notify:
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
    _write_dispatch_to_ledger(
        task_id=args.task_id,
        project=profile.project_name,
        source=source,
        target=args.target,
        role_hint=role_hint,
        title=args.title,
    )
    print(f"dispatched {args.task_id} -> {args.target}")
    print(f"todo: {todo_path}")
    print(f"receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
