#!/usr/bin/env python3
"""
tui_ctl.py — TUI visibility controller for ClawSeat seats.

Agent-facing CLI for checking, recovering, and rebuilding iTerm/tmux windows.
Designed to be called by koder/planner seats the same way they call dispatch_task.py.

Usage:
    python3 tui_ctl.py --profile <profile.toml> check
    python3 tui_ctl.py --profile <profile.toml> check --seat planner
    python3 tui_ctl.py --profile <profile.toml> recover
    python3 tui_ctl.py --profile <profile.toml> recover --seat builder-1
    python3 tui_ctl.py --profile <profile.toml> rebuild
    python3 tui_ctl.py --profile <profile.toml> status --json

Exit codes:
    0 — all targeted seats visible
    1 — one or more seats not visible (or recovery failed)
    2 — usage error / profile not found
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from _common import (
    load_profile,
    load_toml,
    run_command,
    session_name_for,
    session_path_for,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parents[3]

sys.path.insert(0, str(REPO_ROOT / "core" / "scripts"))

from agent_admin_window import verify_tui_visible


# ── Argument parsing ───────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tui_ctl",
        description="TUI visibility controller — check, recover, or rebuild seat windows.",
    )
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    sub = parser.add_subparsers(dest="command", required=True)

    # check
    p_check = sub.add_parser("check", help="Check if seats are visible. Exit 0=all visible, 1=some not.")
    p_check.add_argument("--seat", help="Check a single seat instead of all.")
    p_check.add_argument("--json", action="store_true", help="Output JSON.")

    # recover
    p_recover = sub.add_parser("recover", help="Re-open windows for invisible seats.")
    p_recover.add_argument("--seat", help="Recover a single seat.")
    p_recover.add_argument("--json", action="store_true", help="Output JSON.")

    # rebuild
    p_rebuild = sub.add_parser("rebuild", help="Rebuild the entire project window (open-monitor).")
    p_rebuild.add_argument("--json", action="store_true", help="Output JSON.")

    # status
    p_status = sub.add_parser("status", help="Show detailed TUI status for all seats.")
    p_status.add_argument("--seat", help="Show a single seat.")
    p_status.add_argument("--json", action="store_true", help="Output JSON.")

    return parser.parse_args()


# ── Core logic ─────────────────────────────────────────────────────


def get_backend_seats(profile) -> list[str]:
    """Return seat IDs that are NOT the heartbeat owner (koder)."""
    all_seats = list(profile.seats or [])
    owner = getattr(profile, "heartbeat_owner", None)
    backend = [s for s in all_seats if s != owner]
    return backend or all_seats


def check_one_seat(profile, seat_id: str) -> dict:
    """Check TUI visibility for one seat."""
    sname = session_name_for(profile, seat_id)
    role = (profile.seat_roles or {}).get(seat_id, "unknown")
    tool = ""
    if sname:
        session_data = load_toml(session_path_for(profile, seat_id))
        tool = str((session_data or {}).get("tool", ""))

    if not sname:
        return {
            "seat_id": seat_id,
            "role": role,
            "session_name": "",
            "tool": tool,
            "session_exists": False,
            "clients": 0,
            "pane_content": False,
            "visible": False,
            "status": "NO_SESSION_RECORD",
        }

    result = verify_tui_visible(sname, retries=2, delay=1.0)
    status = "VISIBLE" if result["visible"] else (
        "RUNNING_NOT_VISIBLE" if result["session_exists"] else "NOT_RUNNING"
    )
    return {
        "seat_id": seat_id,
        "role": role,
        "session_name": sname,
        "tool": tool,
        **result,
        "status": status,
    }


def recover_seat(profile, seat_id: str) -> bool:
    """Try to open an iTerm window for an invisible seat."""
    result = run_command(
        [
            "python3",
            str(profile.agent_admin),
            "window",
            "open-engineer",
            seat_id,
            "--project",
            profile.project_name,
        ],
        cwd=profile.repo_root,
    )
    if result.returncode != 0:
        return False
    # Wait briefly for attach to complete, then verify
    time.sleep(2)
    sname = session_name_for(profile, seat_id)
    if not sname:
        return False
    verify = verify_tui_visible(sname, retries=2, delay=1.0)
    return verify.get("visible", False)


def rebuild_project_window(profile) -> dict:
    """Rebuild the entire project window via open-monitor."""
    result = run_command(
        [
            "python3",
            str(profile.agent_admin),
            "window",
            "open-monitor",
            profile.project_name,
        ],
        cwd=profile.repo_root,
    )
    if result.returncode != 0:
        return {
            "success": False,
            "error": f"open-monitor failed (rc={result.returncode})",
            "stderr": (result.stderr or "").strip(),
        }
    # Wait for tabs to attach, then check all
    time.sleep(3)
    seats = get_backend_seats(profile)
    results = [check_one_seat(profile, s) for s in seats]
    visible = sum(1 for r in results if r["status"] == "VISIBLE")
    return {
        "success": True,
        "visible": visible,
        "total": len(results),
        "seats": results,
    }


# ── Output helpers ─────────────────────────────────────────────────


def print_table(results: list[dict]) -> None:
    print(f"{'Seat':<20} {'Session':<35} {'Tool':<8} {'Clients':>7} {'Content':>7} {'Status'}")
    print("-" * 100)
    for r in results:
        print(
            f"{r['seat_id']:<20} {r.get('session_name',''):<35} {r.get('tool',''):<8} "
            f"{r['clients']:>7} {'yes' if r['pane_content'] else 'no':>7} "
            f"{r['status']}"
        )


# ── Commands ───────────────────────────────────────────────────────


def cmd_check(profile, args) -> int:
    seats = [args.seat] if args.seat else get_backend_seats(profile)
    results = [check_one_seat(profile, s) for s in seats]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_table(results)
        visible = sum(1 for r in results if r["status"] == "VISIBLE")
        print(f"\n{visible}/{len(results)} visible")
    return 0 if all(r["status"] == "VISIBLE" for r in results) else 1


def cmd_recover(profile, args) -> int:
    seats = [args.seat] if args.seat else get_backend_seats(profile)
    results_before = [check_one_seat(profile, s) for s in seats]
    to_recover = [r for r in results_before if r["status"] == "RUNNING_NOT_VISIBLE"]

    if not to_recover:
        if args.json:
            print(json.dumps({"recovered": 0, "already_visible": len(results_before)}, ensure_ascii=False))
        else:
            print(f"all {len(results_before)} targeted seat(s) already visible — nothing to recover")
        return 0

    recovered = 0
    for r in to_recover:
        if not args.json:
            print(f"recovering {r['seat_id']}…", end=" ", flush=True)
        ok = recover_seat(profile, r["seat_id"])
        if not args.json:
            print("✓ VISIBLE" if ok else "✗ FAILED")
        if ok:
            recovered += 1

    if args.json:
        results_after = [check_one_seat(profile, s) for s in seats]
        print(json.dumps({
            "recovered": recovered,
            "failed": len(to_recover) - recovered,
            "seats": results_after,
        }, indent=2, ensure_ascii=False))

    return 0 if recovered == len(to_recover) else 1


def cmd_rebuild(profile, args) -> int:
    if not args.json:
        print(f"rebuilding project window for '{profile.project_name}'…")
    result = rebuild_project_window(profile)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            print(f"rebuilt: {result['visible']}/{result['total']} seats visible")
            print_table(result["seats"])
        else:
            print(f"rebuild failed: {result.get('error', 'unknown')}", file=sys.stderr)
    return 0 if result.get("success") and result.get("visible") == result.get("total") else 1


def cmd_status(profile, args) -> int:
    seats = [args.seat] if args.seat else get_backend_seats(profile)
    results = [check_one_seat(profile, s) for s in seats]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_table(results)
        visible = sum(1 for r in results if r["status"] == "VISIBLE")
        running = sum(1 for r in results if r["status"] == "RUNNING_NOT_VISIBLE")
        stopped = sum(1 for r in results if r["status"] in ("NOT_RUNNING", "NO_SESSION_RECORD"))
        print(f"\nvisible={visible}  running_not_visible={running}  stopped={stopped}  total={len(results)}")
    return 0


# ── Main ───────────────────────────────────────────────────────────


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    if profile is None:
        print(f"error: could not load profile: {args.profile}", file=sys.stderr)
        return 2

    handlers = {
        "check": cmd_check,
        "recover": cmd_recover,
        "rebuild": cmd_rebuild,
        "status": cmd_status,
    }
    handler = handlers.get(args.command)
    if handler is None:
        print(f"error: unknown command: {args.command}", file=sys.stderr)
        return 2
    return handler(profile, args)


if __name__ == "__main__":
    raise SystemExit(main())
