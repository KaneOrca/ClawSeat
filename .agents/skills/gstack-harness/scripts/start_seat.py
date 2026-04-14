#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _common import (
    capture_session_pane,
    detect_claude_onboarding_step,
    load_profile,
    load_toml,
    materialize_profile_runtime,
    require_success,
    run_command,
    seed_empty_secret_from_peer,
    seed_empty_oauth_runtime_from_peer,
    session_path_for,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a harness seat for a project profile.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--seat", required=True, help="Seat id to start.")
    parser.add_argument("--reset", action="store_true", help="Reset the seat session before starting.")
    parser.add_argument(
        "--confirm-start",
        action="store_true",
        help="Required for non-frontstage seats after the launch summary has been reviewed with the user.",
    )
    return parser.parse_args()


def render_launch_summary(profile, seat: str) -> str:
    session_data = load_toml(session_path_for(profile, seat))
    role = profile.seat_roles.get(seat, "specialist")
    lines = [
        "launch_summary:",
        f"  profile: {profile.profile_name}",
        f"  harness_template: {profile.template_name}",
        f"  project: {profile.project_name}",
        f"  seat: {seat}",
        f"  role: {role}",
        f"  tool: {session_data.get('tool', '-')}",
        f"  auth_mode: {session_data.get('auth_mode', '-')}",
        f"  provider: {session_data.get('provider', '-')}",
        f"  session: {session_data.get('session', '-')}",
        f"  workspace: {session_data.get('workspace', '-')}",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    materialize_profile_runtime(profile)
    if args.seat not in profile.heartbeat_seats and not args.confirm_start:
        print(render_launch_summary(profile, args.seat))
        print(
            "launch_confirmation_required: review the selected harness, seat, tool, auth mode, and provider with the user first; then re-run with --confirm-start."
        )
        return 2
    seeded_from = seed_empty_secret_from_peer(profile, args.seat)
    oauth_seeded_from = seed_empty_oauth_runtime_from_peer(profile, args.seat)
    cmd = [
        "python3",
        str(profile.agent_admin),
        "session",
        "start-engineer",
        args.seat,
        "--project",
        profile.project_name,
    ]
    if args.reset:
        cmd.append("--reset")
    result = run_command(cmd, cwd=profile.repo_root)
    require_success(result, "start_seat")
    open_result = run_command(
        [
            "python3",
            str(profile.agent_admin),
            "window",
            "open-engineer",
            args.seat,
            "--project",
            profile.project_name,
        ],
        cwd=profile.repo_root,
    )
    require_success(open_result, "start_seat open-engineer")
    if seeded_from is not None:
        print(f"seeded secret for {args.seat} from {seeded_from}")
    if oauth_seeded_from is not None:
        print(f"seeded oauth runtime for {args.seat} from {oauth_seeded_from}")
    if result.stdout.strip():
        print(result.stdout.strip())
    pane_text = capture_session_pane(profile, args.seat)
    onboarding_step = detect_claude_onboarding_step(pane_text)
    if onboarding_step is not None:
        print(
            "manual_onboarding_required: "
            f"{args.seat} is waiting on Claude first-run step '{onboarding_step}'. "
            "Ask the user to complete the prompt in the TUI window, then notify the operator to take over."
        )
    else:
        print(
            "contract_reread_required: "
            f"after {args.seat} is up, have that seat re-read its generated workspace guide "
            "and WORKSPACE_CONTRACT.toml before treating it as fully ready. "
            "If you need durable proof, run scripts/ack_contract.py for that seat afterwards."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
