#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from _common import (
    append_consumed_ack,
    append_task_to_queue,
    broadcast_feishu_group_message,
    build_delegation_report_text,
    build_completion_message,
    complete_task_in_queue,
    load_json,
    load_profile,
    legacy_feishu_group_broadcast_enabled,
    notify,
    require_success,
    resolve_primary_feishu_group_id,
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


def _should_announce_planner_event(source: str, target: str, profile=None) -> bool:
    override = os.environ.get("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS")
    if override is not None:
        return override == "1" and (source == "planner" or target == "planner")
    observability = getattr(profile, "observability", None)
    if observability is None:
        return False
    return getattr(observability, "announce_planner_events", False) and (
        source == "planner" or target == "planner"
    )


def _try_announce_planner_event(*, project: str, source: str, target: str, task_id: str, verb: str) -> None:
    message = f"[{project}] {source} → {target}: {task_id} {verb}"
    if len(message) > 80:
        message = message[:77] + "..."
    try:
        from _feishu import send_feishu_user_message
        send_feishu_user_message(message, project=project)
    except Exception as exc:
        print(f"warn: planner announce failed for {task_id}: {exc}", file=sys.stderr)


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


def complete_source_queue_if_possible(
    profile: object,
    *,
    seat: str,
    task_id: str,
    summary: str,
) -> Path:
    primary = profile.todo_path(seat)  # type: ignore[attr-defined]
    try:
        complete_task_in_queue(primary, task_id=task_id, summary=summary)
        return primary
    except PermissionError as exc:
        print(
            f"warn: todo path {primary} not writable ({exc}); "
            "skipping source queue completion in shared task ledger",
            file=sys.stderr,
        )
        return primary


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
        ack_line, ack_path = append_consumed_ack_with_fallback(
            profile,
            seat=args.target,
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
        if _should_announce_planner_event(args.source, args.target, profile=profile):
            _try_announce_planner_event(
                project=profile.project_name,
                source=args.source,
                target=args.target,
                task_id=args.task_id,
                verb="consumed",
            )
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
    # Guard (followup #22): only planner can close out to the frontstage
    # supervisor (koder). Non-planner specialists that target koder fall
    # into the tmux seat path — but koder runs inside OpenClaw, not as a
    # tmux session, so `notify` silently fails and the Feishu
    # OC_DELEGATION_REPORT_V1 path is skipped (that path is gated on
    # source=planner). The receipt lands on disk but the user never hears
    # about it. Force such specialists back through planner.
    if args.target == profile.heartbeat_owner and not planner_to_frontstage:
        raise SystemExit(
            f"complete_handoff to {profile.heartbeat_owner!r} requires "
            f"source={profile.active_loop_owner!r} (got source={args.source!r}). "
            f"Non-planner specialists must close back to planner; planner "
            f"aggregates and forwards to {profile.heartbeat_owner!r} via Feishu "
            f"OC_DELEGATION_REPORT_V1. This enforces canonical chain §6 "
            f"closeout path."
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
    delivery_path, used_fallback_delivery = persist_delivery(
        profile,
        seat=args.source,
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
    source_todo_path = complete_source_queue_if_possible(
        profile,
        seat=args.source,
        task_id=args.task_id,
        summary=args.summary or f"completed by {args.source}",
    )
    receipt["delivery_path"] = str(delivery_path)
    receipt["delivered_at"] = utc_now_iso()
    receipt["source_todo_path"] = str(source_todo_path)
    receipt["used_fallback_delivery"] = used_fallback_delivery
    receipt["verdict"] = args.verdict
    receipt["frontstage_disposition"] = args.frontstage_disposition
    receipt["user_summary"] = args.user_summary
    receipt["next_action"] = args.next_action
    if planner_to_frontstage:
        frontstage_todo = profile.todo_path(args.target)
        append_task_to_queue(
            frontstage_todo,
            task_id=args.task_id,
            project=profile.project_name,
            owner=args.target,
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
        print(
            f"warn: planner is closing task {args.task_id!r} directly to koder"
            " (self-close path). If this involved implementation, ensure"
            " builder-1 and reviewer-1 were in the loop (R-03 Review Gate).",
            file=sys.stderr,
        )
        receipt["todo_path"] = str(frontstage_todo)
        receipt["assigned_at"] = utc_now_iso()
    # Graceful degrade for external callers (e.g. the ancestor Claude Code
    # running an install via query_memory.py --ask). These callers pass
    # source strings like "memory-client" / "bootstrap-installer" that are
    # not real tmux seats — trying to notify them via send-and-verify.sh
    # fails with a bogus tmux session name.
    target_is_known_seat = args.target in (getattr(profile, "seats", None) or [])
    if not target_is_known_seat and not args.skip_notify:
        receipt["notify_skipped"] = "target_not_registered_seat"
        # Auditable: we KNOW we skipped; caller can inspect receipt JSON.
        print(
            f"notify_skipped: target {args.target!r} is not a registered seat; "
            "completion receipt written but no tmux/Feishu notification sent.",
            file=sys.stderr,
        )
        args.skip_notify = True  # force-skip the branches below

    if not args.skip_notify:
        message = build_completion_message(
            args.task_id,
            delivery_path,
            source=args.source,
            target=args.target,
            user_summary=args.user_summary,
        )
        # Determine koder type once: OpenClaw koder has a Feishu group configured.
        # In OpenClaw mode koder is NOT a tmux session — Feishu is the only notify channel.
        # In local CLI mode (no Feishu group) koder runs as a tmux session.
        openclaw_koder = planner_to_frontstage and bool(resolve_primary_feishu_group_id(project=profile.project_name))
        if openclaw_koder:
            # ── OpenClaw koder path ────────────────────────────────────────────
            # Send OC_DELEGATION_REPORT_V1 directly. Never attempt tmux for this case.
            # Pass project so send_feishu_user_message resolves the group from BRIDGE.toml
            # rather than the first global entry in openclaw.json.
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
            _broadcast = None
            for _attempt in range(3):
                _broadcast = send_feishu_user_message(
                    delegation_report, project=profile.project_name
                )
                if _broadcast.get("status") != "failed":
                    break
                if _attempt < 2:
                    time.sleep(2 ** _attempt)  # 1s then 2s
            broadcast = _broadcast
            receipt["feishu_delegation_report"] = broadcast
            if broadcast.get("status") == "failed":
                detail = (
                    broadcast.get("stderr")
                    or broadcast.get("stdout")
                    or broadcast.get("reason", "unknown")
                )
                raise RuntimeError(
                    f"completion notify (feishu openclaw koder) failed after 3 attempts"
                    f" for {args.task_id}: {detail}"
                )
            if broadcast.get("status") != "failed":
                receipt["notified_at"] = utc_now_iso()
            receipt["notify_message"] = message
        else:
            # ── tmux seat path (local CLI koder or any non-frontstage seat) ───
            result = notify(profile, args.target, message)
            require_success(result, "completion notify")
            receipt["notified_at"] = utc_now_iso()
            receipt["notify_message"] = message
            # Legacy group broadcast is opt-in and only applies to tmux-mode transitions.
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
                broadcast = broadcast_feishu_group_message(broadcast_message, project=profile.project_name)
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
    if not args.skip_notify:
        assert (
            receipt.get("notified_at")
            or receipt.get("notify_skipped")
            or receipt.get("feishu_delegation_report", {}).get("status") == "ok"
        ), "notify path produced no observable success/skip marker"
    receipt_path = persist_receipt(
        profile,
        seat=args.source,
        primary=receipt_path,
        payload=receipt,
    )
    print(f"completed {args.task_id} -> {args.target}")
    print(f"delivery: {delivery_path}")
    print(f"receipt: {receipt_path}")
    if _should_announce_planner_event(args.source, args.target, profile=profile):
        _try_announce_planner_event(
            project=profile.project_name,
            source=args.source,
            target=args.target,
            task_id=args.task_id,
            verb="delivered",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
