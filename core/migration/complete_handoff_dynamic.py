#!/usr/bin/env python3
# DEPRECATED (2026-04-22): transitional dynamic-roster compatibility shim.
# Keep until every live profile has `[dynamic_roster].enabled = true` and the
# router-level migration cleanup can delete the last legacy/static caller.
from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Ensure repo root is on sys.path so core.lib.state is importable.
_REPO_ROOT_DYN = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_DYN) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_DYN))

from dynamic_common import (
    add_notify_args,
    append_consumed_ack,
    build_completion_message,
    load_json,
    load_profile,
    notify,
    preferred_planner_seat,
    require_success,
    resolve_notify,
    utc_now_iso,
    write_delivery,
    write_json,
    write_todo,
)


def _write_completion_to_ledger(
    *,
    task_id: str,
    project: str,
    source: str,
    disposition: str,
) -> None:
    """Record task completion in state.db. Defensive: never fails handoff."""
    try:
        from core.lib.state import open_db, mark_task_completed, record_event
        with open_db() as conn:
            mark_task_completed(conn, task_id, disposition=disposition)
            record_event(conn, "task.completed", project,
                         task_id=task_id, source=source, disposition=disposition)
    except Exception as exc:
        print(f"warn: state.db unavailable, skipping ledger write: {exc}", file=sys.stderr)


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


def _seat_fallback_path(profile: object, seat: str, filename: str) -> Path:
    return profile.workspace_for(seat) / filename  # type: ignore[attr-defined]


def _seat_fallback_receipt_path(profile: object, seat: str, primary: Path) -> Path:
    return profile.workspace_for(seat) / ".clawseat" / "handoffs" / primary.name  # type: ignore[attr-defined]


def persist_delivery(
    profile: object,
    *,
    seat: str,
    task_id: str,
    owner: str,
    target: str,
    title: str,
    summary: str,
    status: str,
    verdict: str | None = None,
    frontstage_disposition: str | None = None,
    user_summary: str | None = None,
    next_action: str | None = None,
) -> tuple[Path, bool]:
    primary = profile.delivery_path(seat)  # type: ignore[attr-defined]
    try:
        write_delivery(
            primary,
            task_id=task_id,
            owner=owner,
            target=target,
            title=title,
            summary=summary,
            status=status,
            verdict=verdict,
            frontstage_disposition=frontstage_disposition,
            user_summary=user_summary,
            next_action=next_action,
        )
        return primary, False
    except PermissionError as exc:
        fallback = _seat_fallback_path(profile, seat, "DELIVERY.md")
        write_delivery(
            fallback,
            task_id=task_id,
            owner=owner,
            target=target,
            title=title,
            summary=summary,
            status=status,
            verdict=verdict,
            frontstage_disposition=frontstage_disposition,
            user_summary=user_summary,
            next_action=next_action,
        )
        print(
            f"warn: delivery path {primary} not writable ({exc}); "
            f"wrote fallback delivery to {fallback}",
            file=sys.stderr,
        )
        return fallback, True


def persist_receipt(
    profile: object,
    *,
    seat: str,
    primary: Path,
    payload: dict[str, object],
) -> Path:
    try:
        write_json(primary, payload)
        return primary
    except PermissionError as exc:
        fallback = _seat_fallback_receipt_path(profile, seat, primary)
        write_json(fallback, payload)
        print(
            f"warn: receipt path {primary} not writable ({exc}); "
            f"wrote fallback receipt to {fallback}",
            file=sys.stderr,
        )
        return fallback


def append_consumed_ack_with_fallback(
    profile: object,
    *,
    seat: str,
    task_id: str,
    source: str,
) -> tuple[str, Path]:
    primary = profile.todo_path(seat)  # type: ignore[attr-defined]
    try:
        return append_consumed_ack(primary, task_id=task_id, source=source), primary
    except PermissionError as exc:
        fallback = _seat_fallback_path(profile, seat, "TODO.md")
        ack_line = append_consumed_ack(fallback, task_id=task_id, source=source)
        print(
            f"warn: todo path {primary} not writable ({exc}); "
            f"appended consumed ACK to fallback TODO {fallback}",
            file=sys.stderr,
        )
        return ack_line, fallback


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
    ]
    if disposition == "AUTO_ADVANCE":
        lines.append("Summarize the result for the user in plain language and auto-advance the chain unless a real decision gate appears.")
    if next_action:
        lines.append(f"NextAction: {next_action}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Complete or consume a dynamic-roster harness handoff.")
    parser.add_argument("--profile", required=True, help="Path to the dynamic profile TOML.")
    parser.add_argument("--source", required=True, help="Source seat for the completion or ACK.")
    parser.add_argument("--target", help="Target seat. Defaults to the resolved planner seat.")
    parser.add_argument("--task-id", required=True, help="Task id.")
    parser.add_argument("--title", help="Delivery title.")
    parser.add_argument("--summary", help="Delivery summary text.")
    parser.add_argument("--status", default="completed", help="Delivery status.")
    parser.add_argument("--verdict", help="Canonical review verdict.")
    parser.add_argument("--frontstage-disposition", help="AUTO_ADVANCE or USER_DECISION_NEEDED.")
    parser.add_argument("--user-summary", help="Short user-facing summary.")
    parser.add_argument("--next-action", help="Short frontstage instruction.")
    parser.add_argument("--ack-only", action="store_true", help="Only append the durable Consumed ACK.")
    add_notify_args(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    do_notify = resolve_notify(args)
    profile = load_profile(args.profile)
    target = args.target or preferred_planner_seat(profile)
    receipt_path = profile.handoff_path(args.task_id, args.source, target)
    receipt = load_json(receipt_path) or {
        "project": profile.project_name,
        "kind": "completion",
        "task_id": args.task_id,
        "source": args.source,
        "target": target,
    }
    receipt["project"] = profile.project_name
    receipt["target"] = target
    source_role = profile.seat_roles.get(args.source, "")
    if args.ack_only:
        ack_line, ack_path = append_consumed_ack_with_fallback(
            profile,
            seat=target,
            task_id=args.task_id,
            source=args.source,
        )
        receipt["consumed_at"] = utc_now_iso()
        receipt["consumed_ack"] = ack_line
        receipt["todo_path"] = str(ack_path)
        receipt_path = persist_receipt(
            profile,
            seat=args.source,
            primary=receipt_path,
            payload=receipt,
        )
        print(ack_line)
        print(f"receipt: {receipt_path}")
        return 0
    if source_role == "reviewer" and args.verdict not in VALID_VERDICTS:
        raise SystemExit(
            f"{args.source} delivery requires --verdict with a canonical value "
            "because the source seat is a reviewer"
        )
    if args.frontstage_disposition and args.frontstage_disposition not in VALID_FRONTSTAGE_DISPOSITIONS:
        raise SystemExit("invalid --frontstage-disposition; use AUTO_ADVANCE or USER_DECISION_NEEDED")
    planner_to_frontstage = (
        args.source == preferred_planner_seat(profile) and target == profile.heartbeat_owner
    )
    if planner_to_frontstage:
        if args.frontstage_disposition not in VALID_FRONTSTAGE_DISPOSITIONS:
            raise SystemExit("planner delivery back to frontstage requires --frontstage-disposition")
        if not args.user_summary:
            raise SystemExit("planner delivery back to frontstage requires --user-summary")
        if args.frontstage_disposition == "USER_DECISION_NEEDED" and not args.next_action:
            raise SystemExit("planner delivery with USER_DECISION_NEEDED requires --next-action")
    summary = args.summary or f"{args.task_id} completed by {args.source}."
    title = args.title or args.task_id
    delivery_path, used_fallback_delivery = persist_delivery(
        profile,
        seat=args.source,
        task_id=args.task_id,
        owner=args.source,
        target=target,
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
    receipt["used_fallback_delivery"] = used_fallback_delivery
    if planner_to_frontstage:
        frontstage_todo = profile.todo_path(target)
        write_todo(
            frontstage_todo,
            task_id=args.task_id,
            project=profile.project_name,
            owner=target,
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
    if do_notify:
        message = build_completion_message(
            profile.project_name,
            args.task_id,
            delivery_path,
            source=args.source,
            target=target,
        )
        result = notify(profile, target, message)
        require_success(result, "completion notify")
        receipt["notified_at"] = utc_now_iso()
        receipt["notify_message"] = message
    receipt_path = persist_receipt(
        profile,
        seat=args.source,
        primary=receipt_path,
        payload=receipt,
    )
    _write_completion_to_ledger(
        task_id=args.task_id,
        project=profile.project_name,
        source=args.source,
        disposition=args.frontstage_disposition or "",
    )
    print(f"completed {args.task_id} -> {target}")
    print(f"delivery: {delivery_path}")
    print(f"receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
