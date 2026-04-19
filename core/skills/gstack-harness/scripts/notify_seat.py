#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _common import (
    assert_target_not_memory,
    load_profile,
    notify,
    require_success,
    utc_now_iso,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a protocol-compliant seat notification.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--source", required=True, help="Seat sending the notification.")
    parser.add_argument("--target", required=True, help="Seat receiving the notification.")
    parser.add_argument("--message", required=True, help="Human-readable message body.")
    parser.add_argument("--task-id", help="Optional task id for receipt tracking.")
    parser.add_argument("--reply-to", help="Optional reply target to mention in the notice.")
    parser.add_argument(
        "--kind",
        default="notice",
        help="Notification kind for receipt metadata (notice, reminder, unblock, etc).",
    )
    parser.add_argument(
        "--skip-receipt",
        action="store_true",
        help="Do not write a JSON receipt even when task-id is provided.",
    )
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> str:
    prefix = f"{args.kind} from {args.source} to {args.target}"
    if args.task_id:
        prefix = f"{args.task_id} {prefix}"
    suffix = ""
    if args.reply_to:
        suffix = f" Reply to {args.reply_to} if follow-up or completion is required."
    return f"{prefix}: {args.message.strip()}{suffix}"


def main() -> int:
    args = parse_args()
    # T9: block notify to memory before touching the profile — memory is an
    # oracle; reach it via query_memory.py instead. Check before load_profile
    # so the guard works even when the profile path is bogus.
    assert_target_not_memory(args.target, "notify_seat.py")
    profile = load_profile(args.profile)
    payload = build_payload(args)
    result = notify(profile, args.target, payload)
    # silent-ok audit: require_success raises on non-sent status; failure is not silent
    require_success(result, "notify seat")

    if args.task_id and not args.skip_receipt:
        receipt = {
            "kind": args.kind,
            "task_id": args.task_id,
            "source": args.source,
            "target": args.target,
            "reply_to": args.reply_to,
            "message": payload,
            "notified_at": utc_now_iso(),
        }
        receipt_path = profile.handoff_path(args.task_id, args.source, args.target)
        write_json(receipt_path, receipt)
        print(f"receipt: {receipt_path}")

    print(f"notified {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
