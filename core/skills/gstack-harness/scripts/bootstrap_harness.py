#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import (
    HarnessProfile,
    load_profile,
    make_local_override,
    materialize_profile_runtime,
    require_success,
    run_command,
    seed_empty_secret_from_peer,
    seed_empty_oauth_runtime_from_peer,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a project from a gstack harness profile.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--project-name", help="Override project name from the profile.")
    parser.add_argument("--repo-root", help="Override repo root from the profile.")
    parser.add_argument("--start", action="store_true", help="Start the project monitor after bootstrap.")
    return parser.parse_args()


def with_overrides(profile: HarnessProfile, *, project_name: str, repo_root: Path) -> HarnessProfile:
    if project_name == profile.project_name and repo_root == profile.repo_root:
        return profile
    tasks_root = repo_root / ".tasks"
    return HarnessProfile(
        profile_path=profile.profile_path,
        profile_name=profile.profile_name,
        template_name=profile.template_name,
        project_name=project_name,
        repo_root=repo_root,
        tasks_root=tasks_root,
        project_doc=tasks_root / "PROJECT.md",
        tasks_doc=tasks_root / "TASKS.md",
        status_doc=tasks_root / "STATUS.md",
        send_script=profile.send_script,
        status_script=tasks_root / "patrol" / "check-status.sh",
        patrol_script=tasks_root / "patrol" / "patrol-supervisor.sh",
        agent_admin=profile.agent_admin,
        workspace_root=profile.workspace_root.parent / project_name,
        handoff_dir=tasks_root / "patrol" / "handoffs",
        heartbeat_owner=profile.heartbeat_owner,
        active_loop_owner=profile.active_loop_owner,
        default_notify_target=profile.default_notify_target,
        heartbeat_receipt=(profile.workspace_root.parent / project_name / profile.heartbeat_owner / "HEARTBEAT_RECEIPT.toml"),
        seats=list(profile.seats),
        heartbeat_seats=list(profile.heartbeat_seats),
        seat_roles=dict(profile.seat_roles),
        seat_overrides={seat: dict(values) for seat, values in profile.seat_overrides.items()},
        dynamic_roster_enabled=profile.dynamic_roster_enabled,
        session_root=profile.session_root,
        bootstrap_seats=list(profile.bootstrap_seats or []),
        default_start_seats=list(profile.default_start_seats or []),
        compat_legacy_seats=profile.compat_legacy_seats,
        legacy_seats=list(profile.legacy_seats or []),
        legacy_seat_roles=dict(profile.legacy_seat_roles or {}),
    )


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    project_name = args.project_name or profile.project_name
    repo_root = Path(args.repo_root).expanduser() if args.repo_root else profile.repo_root
    effective_profile = with_overrides(profile, project_name=project_name, repo_root=repo_root)
    local_path = make_local_override(profile, project_name=project_name, repo_root=repo_root)
    try:
        cmd = [
            "python3",
            str(profile.agent_admin),
            "project",
            "bootstrap",
            "--template",
            profile.template_name,
            "--local",
            str(local_path),
        ]
        result = run_command(cmd, cwd=profile.repo_root)
        require_success(result, "bootstrap_harness")
        materialize_profile_runtime(effective_profile)
        for seat in (effective_profile.bootstrap_seats or effective_profile.seats):
            seed_empty_secret_from_peer(effective_profile, seat)
            seed_empty_oauth_runtime_from_peer(effective_profile, seat)
        if args.start:
            start_result = run_command(
                [
                    "python3",
                    str(profile.agent_admin),
                    "session",
                    "start-engineer",
                    effective_profile.heartbeat_owner,
                    "--project",
                    project_name,
                ],
                cwd=profile.repo_root,
            )
            require_success(start_result, "bootstrap_harness start frontstage")
            if start_result.stdout.strip():
                print(start_result.stdout.strip())
            open_result = run_command(
                [
                    "python3",
                    str(profile.agent_admin),
                    "window",
                    "open-monitor",
                    project_name,
                ],
                cwd=profile.repo_root,
            )
            require_success(open_result, "bootstrap_harness open-monitor")
        if result.stdout.strip():
            print(result.stdout.strip())
        return 0
    except Exception as exc:
        print(
            f"warn: bootstrap failed for {project_name!r}: {exc}\n"
            f"Rollback hint: remove workspace at {effective_profile.workspace_root}"
            f" and re-run bootstrap_harness, or run: python3 agent.py project"
            f" teardown --project {project_name}",
            file=sys.stderr,
        )
        raise
    finally:
        local_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
