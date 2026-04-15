#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from _common import (
    append_consumed_ack,
    broadcast_feishu_group_message,
    build_delegation_report_text,
    build_completion_message,
    load_json,
    load_profile,
    legacy_feishu_group_broadcast_enabled,
    notify,
    require_success,
    send_feishu_user_message,
    stable_dispatch_nonce,
    utc_now_iso,
    write_delivery,
    write_json,
    write_todo,
)


VALID_VERDICTS = {
    "APPROVED",
    "APPROVED_WITH_NITS",
    "CHANGES_REQUESTED",
    "BLOCKED",
    "DECISION_NEEDED",
}

VALID_FRONTSTAGE_DISPOSITIONS = {
    "AUTO_ADVANCE",
    "USER_DECISION_NEEDED",
}


def build_frontstage_objective(
    *,
    source: str,
    task_id: str,
    delivery_path: str,
    disposition: str,
    user_summary: str,
    next_action: str | None,
) -> str:
    lines = [
        f"Read {delivery_path}.",
        f"{source} returned {task_id} to frontstage.",
        f"FrontstageDisposition: {disposition}",
        f"UserSummary: {user_summary}",
        "Before replying to the user, review the delivery trail, consolidate the wrap-up, and update PROJECT.md / TASKS.md / STATUS.md when the stage closeout changes the project record.",
    ]
    if disposition == "AUTO_ADVANCE":
        lines.append("Summarize the result for the user in plain language and auto-advance the chain unless a real decision gate appears.")
    if next_action:
        lines.append(f"NextAction: {next_action}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Complete or consume a harness handoff.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--source", required=True, help="Source seat for the completion or ACK.")
    parser.add_argument("--target", default="planner", help="Target seat.")
    parser.add_argument("--task-id", required=True, help="Task id.")
    parser.add_argument("--title", help="Delivery title.")
    parser.add_argument("--summary", help="Delivery summary text.")
    parser.add_argument("--status", default="completed", help="Delivery status.")
    parser.add_argument("--verdict", help="Canonical review verdict.")
    parser.add_argument(
        "--frontstage-disposition",
        help="Canonical planner->frontstage outcome: AUTO_ADVANCE or USER_DECISION_NEEDED.",
    )
    parser.add_argument(
        "--user-summary",
        help="Short plain-language summary that frontstage can relay to the user.",
    )
    parser.add_argument(
        "--next-action",
        help="Short frontstage instruction, especially when a user decision is needed.",
    )
    parser.add_argument("--ack-only", action="store_true", help="Only append the durable Consumed ACK.")
    parser.add_argument("--skip-notify", action="store_true", help="Write delivery but skip tmux notification.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    receipt_path = profile.handoff_path(args.task_id, args.source, args.target)
    receipt = load_json(receipt_path) or {
        "kind": "completion",
        "task_id": args.task_id,
        "source": args.source,
        "target": args.target,
    }
    source_role = profile.seat_roles.get(args.source, "")
    target_role = profile.seat_roles.get(args.target, "")

    if args.ack_only:
        ack_line = append_consumed_ack(profile.todo_path(args.target), task_id=args.task_id, source=args.source)
        receipt["consumed_at"] = utc_now_iso()
        receipt["consumed_ack"] = ack_line
        write_json(receipt_path, receipt)
        print(ack_line)
        return 0

    if source_role == "reviewer" and args.verdict not in VALID_VERDICTS:
        raise SystemExit(
            f"{args.source} delivery requires --verdict with a canonical value "
            "because the source seat is a reviewer"
        )

    if args.frontstage_disposition and args.frontstage_disposition not in VALID_FRONTSTAGE_DISPOSITIONS:
        raise SystemExit("invalid --frontstage-disposition; use AUTO_ADVANCE or USER_DECISION_NEEDED")

    planner_to_frontstage = (
        args.source == profile.active_loop_owner
        and args.target == profile.heartbeat_owner
    )
    if planner_to_frontstage:
        if args.frontstage_disposition not in VALID_FRONTSTAGE_DISPOSITIONS:
            raise SystemExit(
                "planner delivery back to frontstage requires --frontstage-disposition "
                "with AUTO_ADVANCE or USER_DECISION_NEEDED"
            )
        if not args.user_summary:
            raise SystemExit("planner delivery back to frontstage requires --user-summary")
        if args.frontstage_disposition == "USER_DECISION_NEEDED" and not args.next_action:
            raise SystemExit(
                "planner delivery with USER_DECISION_NEEDED requires --next-action"
            )

    summary = args.summary or f"{args.task_id} completed by {args.source}."
    title = args.title or args.task_id
    delivery_path = profile.delivery_path(args.source)
    write_delivery(
        delivery_path,
        task_id=args.task_id,
        owner=args.source,
        target=args.target,
        title=title,
        summary=summary,
        status=args.status,
        verdict=args.verdict,
        frontstage_disposition=args.frontstage_disposition,
        user_summary=args.user_summary,
        next_action=args.next_action,
    )
    receipt["delivery_path"] = str(delivery_path)
    receipt["delivered_at"] = utc_now_iso()
    receipt["verdict"] = args.verdict
    receipt["frontstage_disposition"] = args.frontstage_disposition
    receipt["user_summary"] = args.user_summary
    receipt["next_action"] = args.next_action
    if planner_to_frontstage:
        frontstage_todo = profile.todo_path(args.target)
        write_todo(
            frontstage_todo,
            task_id=args.task_id,
            project=profile.project_name,
            owner=args.target,
            status="pending",
            title=title,
            objective=build_frontstage_objective(
                source=args.source,
                task_id=args.task_id,
                delivery_path=str(delivery_path),
                disposition=args.frontstage_disposition or "",
                user_summary=args.user_summary or "",
                next_action=args.next_action,
            ),
            source=args.source,
            reply_to=args.source,
        )
        receipt["todo_path"] = str(frontstage_todo)
        receipt["assigned_at"] = utc_now_iso()
    if not args.skip_notify:
        message = build_completion_message(
            args.task_id,
            delivery_path,
            source=args.source,
            target=args.target,
        )
        result = notify(profile, args.target, message)
        require_success(result, "completion notify")
        receipt["notified_at"] = utc_now_iso()
        receipt["notify_message"] = message
        should_broadcast = (
            source_role in {"planner", "planner-dispatcher"}
            or target_role in {"planner", "planner-dispatcher"}
            or args.source == profile.active_loop_owner
            or args.target == profile.active_loop_owner
        )
        if planner_to_frontstage:
            delegation_report = build_delegation_report_text(
                project=profile.project_name,
                lane="planning",
                task_id=args.task_id,
                dispatch_nonce=stable_dispatch_nonce(
                    profile.project_name,
                    "planning",
                    args.task_id,
                ),
                report_status=(
                    "done"
                    if args.frontstage_disposition == "AUTO_ADVANCE"
                    else "needs_decision"
                ),
                decision_hint=(
                    "proceed"
                    if args.frontstage_disposition == "AUTO_ADVANCE"
                    else "ask_user"
                ),
                user_gate=(
                    "none"
                    if args.frontstage_disposition == "AUTO_ADVANCE"
                    else "required"
                ),
                next_action=(
                    "consume_closeout"
                    if args.frontstage_disposition == "AUTO_ADVANCE"
                    else "ask_user"
                ),
                summary=args.user_summary or args.summary or args.title or args.task_id,
                human_summary=args.user_summary or args.summary or args.title,
            )
            broadcast = send_feishu_user_message(delegation_report)
            receipt["feishu_delegation_report"] = broadcast
            if broadcast.get("status") == "failed":
                print(
                    f"warn: feishu delegation report failed for {args.task_id}: "
                    f"{broadcast.get('stderr') or broadcast.get('stdout') or broadcast.get('reason', 'unknown')}",
                    file=sys.stderr,
                )
        elif should_broadcast and legacy_feishu_group_broadcast_enabled():
            if source_role in {"planner", "planner-dispatcher"} and target_role not in {
                "planner",
                "planner-dispatcher",
            }:
                broadcast_message = (
                    f"{profile.project_name} 项目 planner 阶段收尾 {args.task_id}："
                    f"{args.user_summary or args.summary or args.title or args.task_id}。"
                    f" FrontstageDisposition={args.frontstage_disposition or 'n/a'}."
                )
            elif target_role in {"planner", "planner-dispatcher"} and source_role not in {
                "planner",
                "planner-dispatcher",
            }:
                broadcast_message = (
                    f"{profile.project_name} 项目 planner 已收到回执 {args.task_id}，"
                    f"来自 {args.source}。{args.summary or args.title or ''}".strip()
                )
            else:
                broadcast_message = (
                    f"{profile.project_name} 项目 planner 完成任务流转 {args.task_id}："
                    f"{args.source} -> {args.target}。"
                )
            broadcast = broadcast_feishu_group_message(broadcast_message)
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
    write_json(receipt_path, receipt)
    print(f"completed {args.task_id} -> {args.target}")
    print(f"delivery: {delivery_path}")
    print(f"receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
