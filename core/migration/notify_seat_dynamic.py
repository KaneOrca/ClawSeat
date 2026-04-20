#!/usr/bin/env python3
from __future__ import annotations

import argparse

from dynamic_common import build_notify_payload, load_profile, notify, require_success, utc_now_iso, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a protocol-compliant dynamic-roster seat notification.")
    parser.add_argument("--profile", required=True, help="Path to the dynamic profile TOML.")
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


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    payload = build_notify_payload(
        source=args.source,
        target=args.target,
        message=args.message,
        kind=args.kind,
        task_id=args.task_id,
        reply_to=args.reply_to,
        project_name=profile.project_name,
    )
    result = notify(profile, args.target, payload)
    require_success(result, "notify seat")
    if args.task_id and not args.skip_receipt:
        receipt = {
            "project": profile.project_name,
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
