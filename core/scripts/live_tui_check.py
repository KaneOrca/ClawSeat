#!/usr/bin/env python3
"""
live_tui_check.py — Verify that every seat's TUI is visible to the user.

Usage:
    python3 live_tui_check.py --project <project_name>
    python3 live_tui_check.py --profile <profile.toml>

Exit codes:
    0 — all seats visible
    1 — one or more seats not visible
    2 — usage error / profile not found
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "core"))
sys.path.insert(0, str(REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts"))

from agent_admin_window import verify_tui_visible


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check TUI visibility for all seats in a project.")
    p.add_argument("--project", help="Project name (auto-resolves profile from ~/.agents/profiles/)")
    p.add_argument("--profile", help="Explicit path to profile TOML")
    p.add_argument("--recover", action="store_true", help="Attempt to re-open window for invisible seats")
    p.add_argument("--json", action="store_true", help="Output results as JSON")
    return p.parse_args()


def resolve_profile_path(project: str | None, profile_path: str | None) -> Path | None:
    if profile_path:
        p = Path(profile_path).expanduser()
        return p if p.exists() else None
    if project:
        from resolve import dynamic_profile_path
        p = dynamic_profile_path(project)
        return p if p.exists() else None
    return None


def load_profile_seats(profile_path: Path) -> list[dict[str, str]]:
    """Load seats from a profile TOML, returning list of {seat_id, role, tool}."""
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore

    data = tomllib.loads(profile_path.read_text(encoding="utf-8"))
    seats = data.get("seats", [])
    seat_roles = data.get("seat_roles", {})
    # Try to load session data for tool info
    project_name = data.get("project_name", "")

    result = []
    for seat_id in seats:
        role = seat_roles.get(seat_id, "unknown")
        # Resolve tmux session name from session.toml if available
        session_name = ""
        tool = ""
        sessions_dir = Path.home() / ".agents" / "sessions" / project_name
        session_toml = sessions_dir / seat_id / "session.toml"
        if session_toml.exists():
            try:
                sdata = tomllib.loads(session_toml.read_text(encoding="utf-8"))
                session_name = sdata.get("session", "")
                tool = sdata.get("tool", "")
            except Exception:
                pass
        if not session_name:
            session_name = f"{project_name}-{seat_id}"
        result.append({
            "seat_id": seat_id,
            "role": role,
            "session_name": session_name,
            "tool": tool,
        })
    return result


def check_seat(seat: dict[str, str]) -> dict:
    """Check one seat's TUI visibility."""
    session_name = seat["session_name"]
    result = verify_tui_visible(session_name, retries=2, delay=1.0)
    return {
        **seat,
        **result,
        "status": "VISIBLE" if result["visible"] else (
            "RUNNING_NOT_VISIBLE" if result["session_exists"] else "NOT_RUNNING"
        ),
    }


def try_recover(seat_result: dict, profile_path: Path) -> bool:
    """Try to open a window for an invisible seat."""
    if seat_result["status"] != "RUNNING_NOT_VISIBLE":
        return False
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore

    data = tomllib.loads(profile_path.read_text(encoding="utf-8"))
    agent_admin_raw = data.get("agent_admin", "")
    project_name = data.get("project_name", "")
    if not agent_admin_raw or not project_name:
        return False

    # Expand {CLAWSEAT_ROOT} and ~ in the path
    agent_admin = agent_admin_raw.replace(
        "{CLAWSEAT_ROOT}", os.environ.get("CLAWSEAT_ROOT", str(REPO_ROOT))
    )
    agent_admin = os.path.expanduser(agent_admin)
    if not os.path.exists(agent_admin):
        return False

    result = subprocess.run(
        [
            "python3", agent_admin, "window", "open-engineer",
            seat_result["seat_id"], "--project", project_name,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return result.returncode == 0


def main() -> int:
    args = parse_args()

    profile_path = resolve_profile_path(args.project, args.profile)
    if profile_path is None:
        project = args.project or "(none)"
        print(f"error: could not find profile for project '{project}'", file=sys.stderr)
        return 2

    seats = load_profile_seats(profile_path)
    if not seats:
        print(f"error: no seats found in profile {profile_path}", file=sys.stderr)
        return 2

    # Skip koder (frontstage) — it's the caller, not a backend seat
    backend_seats = [s for s in seats if s["role"] != "frontstage-supervisor"]
    if not backend_seats:
        backend_seats = seats  # fallback: check all if no frontstage

    results = [check_seat(s) for s in backend_seats]

    if args.json:
        import json
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        # Table output
        print(f"{'Seat':<20} {'Session':<35} {'Tool':<8} {'Clients':>7} {'Content':>7} {'Status'}")
        print("-" * 100)
        for r in results:
            print(
                f"{r['seat_id']:<20} {r['session_name']:<35} {r.get('tool',''):<8} "
                f"{r['clients']:>7} {'yes' if r['pane_content'] else 'no':>7} "
                f"{r['status']}"
            )
        print()
        visible = sum(1 for r in results if r["status"] == "VISIBLE")
        total = len(results)
        print(f"summary: {visible}/{total} seats visible")

    # Recovery pass
    not_visible = [r for r in results if r["status"] != "VISIBLE"]
    if not_visible and args.recover:
        print()
        for r in not_visible:
            print(f"recovering: {r['seat_id']} ({r['status']})…", end=" ")
            if try_recover(r, profile_path):
                # Re-check
                new_result = check_seat(r)
                print(f"→ {new_result['status']}")
            else:
                print("→ FAILED")

    if any(r["status"] != "VISIBLE" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
