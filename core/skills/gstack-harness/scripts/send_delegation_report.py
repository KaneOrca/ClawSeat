#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from _common import (
    build_delegation_report_text,
    check_feishu_auth,
    send_feishu_user_message,
    stable_dispatch_nonce,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send an OC_DELEGATION_REPORT_V1 message to Feishu as the user."
    )
    parser.add_argument("--project", required=False, help="Project name.")
    parser.add_argument(
        "--lane",
        required=False,
        help="Delegation lane: planning | builder | reviewer | qa | designer | frontstage.",
    )
    parser.add_argument("--task-id", required=False, help="Task id.")
    parser.add_argument(
        "--dispatch-nonce",
        help="Stable nonce for the active delegation. Defaults to a hash of project/lane/task-id.",
    )
    parser.add_argument(
        "--report-status",
        required=False,
        help="in_progress | done | needs_decision | blocked",
    )
    parser.add_argument(
        "--decision-hint",
        required=False,
        help="hold | proceed | ask_user | retry | escalate | close",
    )
    parser.add_argument(
        "--user-gate",
        required=False,
        help="none | optional | required",
    )
    parser.add_argument(
        "--next-action",
        required=False,
        help="wait | consume_closeout | ask_user | retry_current_lane | surface_blocker | finalize_chain",
    )
    parser.add_argument("--summary", required=False, help="Single-line machine-readable summary.")
    parser.add_argument(
        "--human-summary",
        help="Optional human-readable tail shown after the structured envelope.",
    )
    parser.add_argument("--chat-id", help="Feishu group chat id. Defaults to the configured primary group.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the formatted delegation report without sending it.",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Only check lark-cli auth status and exit. No message is sent.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Auth-check-only mode: verify lark-cli is available and auth is valid.
    if args.check_auth:
        result = check_feishu_auth()
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("status") == "ok" else 1

    # Normal send mode — require the delegation fields.
    for field in ("project", "lane", "task_id", "report_status", "decision_hint", "user_gate", "next_action", "summary"):
        if not getattr(args, field.replace("-", "_"), None):
            print(f"error: --{field.replace('_', '-')} is required when sending a delegation report", flush=True)
            return 2

    dispatch_nonce = args.dispatch_nonce or stable_dispatch_nonce(
        args.project,
        args.lane,
        args.task_id,
    )
    message = build_delegation_report_text(
        project=args.project,
        lane=args.lane,
        task_id=args.task_id,
        dispatch_nonce=dispatch_nonce,
        report_status=args.report_status,
        decision_hint=args.decision_hint,
        user_gate=args.user_gate,
        next_action=args.next_action,
        summary=args.summary,
        human_summary=args.human_summary,
    )
    if args.dry_run:
        print(message)
        return 0

    result = send_feishu_user_message(message, group_id=args.chat_id, pre_check_auth=True)
    # silent-ok audit: status≠sent returns exit 1, caller surfaces failure via return code
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "sent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
