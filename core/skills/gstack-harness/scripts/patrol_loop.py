#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from _common import executable_command, load_profile, materialize_profile_runtime, require_success, run_command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the patrol loop for a project profile.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--send", action="store_true", help="Allow reminders to be sent.")
    return parser.parse_args()


def run_auto_supersede(profile, *, age_days: int = 3) -> None:
    cmd = [
        sys.executable,
        str(profile.agent_admin),
        "task",
        "auto-supersede",
        "--project",
        profile.project_name,
        "--age-days",
        str(age_days),
    ]
    result = run_command(cmd, cwd=profile.repo_root)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        stderr = result.stderr.strip()
        suffix = f": {stderr}" if stderr else ""
        print(f"warn: task auto-supersede failed{suffix}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    materialize_profile_runtime(profile)
    cmd = executable_command(profile.patrol_script)
    if args.send:
        cmd.append("--send")
    result = run_command(cmd, cwd=profile.repo_root)
    require_success(result, "patrol_loop")
    if result.stdout.strip():
        print(result.stdout.strip())
    run_auto_supersede(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
