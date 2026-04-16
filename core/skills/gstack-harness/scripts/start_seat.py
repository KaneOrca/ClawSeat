#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess

from _common import (
    REPO_ROOT,
    capture_session_pane,
    detect_claude_onboarding_step,
    load_profile,
    load_toml,
    materialize_profile_runtime,
    require_success,
    run_command,
    seed_empty_secret_from_peer,
    seed_empty_oauth_runtime_from_peer,
    session_name_for,
    session_path_for,
    utc_now_iso,
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
    parser.add_argument("--tool", help="Override tool (claude, codex, gemini). Updates session before start.")
    parser.add_argument("--auth-mode", help="Override auth mode (oauth, api). Updates session before start.")
    parser.add_argument("--provider", help="Override provider. Updates session before start.")
    return parser.parse_args()


def write_frontstage_receipt(profile, seat: str) -> str:
    """
    Write a durable frontstage binding receipt proving koder has entered frontstage
    with the correct identity and project binding.
    """
    session_data = load_toml(session_path_for(profile, seat))
    role = profile.seat_roles.get(seat, "specialist")
    workspace = profile.workspace_for(seat)
    receipt_path = workspace / "FRONTSTAGE_RECEIPT.toml"
    lines = [
        "version = 1",
        f'seat_id = "{seat}"',
        f'role = "{role}"',
        f'project = "{profile.project_name}"',
        f'entered_at = "{utc_now_iso()}"',
        f"tool = \"{session_data.get('tool', '-')}\"",
        f"auth_mode = \"{session_data.get('auth_mode', '-')}\"",
        f"provider = \"{session_data.get('provider', '-')}\"",
        f"identity = \"{session_data.get('identity', '-')}\"",
        f"workspace = \"{workspace}\"",
        f"contract_path = \"{workspace / 'WORKSPACE_CONTRACT.toml'}\"",
    ]
    receipt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(receipt_path)


SEND_SCRIPT_PATH = REPO_ROOT / "core" / "shell-scripts" / "send-and-verify.sh"


def _send_frontstage_via_send_and_verify(project: str, seat: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SEND_SCRIPT_PATH), "--project", project, seat, "enter_frontstage"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def send_frontstage_trigger(profile, seat: str) -> None:
    """
    Send a frontstage entry trigger to the seat via tmux.
    For koder, this triggers automatic entry into the frontstage shell.
    """
    session_name = session_name_for(profile, seat)
    if not session_name:
        return
    result = _send_frontstage_via_send_and_verify(profile.project_name, seat)
    if result.returncode == 0:
        print(
            f"frontstage_trigger_ok: {profile.project_name}/{seat} via send-and-verify "
            f"(session={session_name})"
        )
        return
    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    fix_hint = (
        "single_fix: run "
        f"`python3 {REPO_ROOT}/core/scripts/agent_admin.py window open-engineer {seat} --project {profile.project_name}` "
        "to reopen the frontstage window, then `tmux list-sessions` to confirm runtime state."
    )
    detail = output or "no output"
    if "RETRY_FAILED" in detail:
        detail += "; send-and-verify detected unsubmitted input"
    if "TMUX_MISSING" in detail:
        detail += "; recover path: ensure CLAWSEAT_ROOT and tmux are valid, then rerun preflight"
    raise RuntimeError(
        f"frontstage trigger failed for seat '{seat}' in project '{profile.project_name}': "
        f"tmux/send failed; return_code={result.returncode}; output={detail}; {fix_hint}"
    )


def apply_config_overrides(profile, seat: str, *, tool: str | None, auth_mode: str | None, provider: str | None) -> bool:
    """Apply tool/auth_mode/provider overrides via agent_admin switch-harness.

    Returns True if the session was updated, False if no changes were needed.
    """
    if not tool and not auth_mode and not provider:
        return False
    session_data = load_toml(session_path_for(profile, seat))
    current_tool = session_data.get("tool", "")
    current_auth = session_data.get("auth_mode", "")
    current_provider = session_data.get("provider", "")
    new_tool = tool or current_tool
    new_auth = auth_mode or current_auth
    new_provider = provider or current_provider
    if new_tool == current_tool and new_auth == current_auth and new_provider == current_provider:
        return False
    cmd = [
        "python3",
        str(profile.agent_admin),
        "session",
        "switch-harness",
        "--engineer",
        seat,
        "--project",
        profile.project_name,
        "--tool",
        new_tool,
        "--mode",
        new_auth,
        "--provider",
        new_provider,
    ]
    result = run_command(cmd, cwd=profile.repo_root)
    require_success(result, f"switch config for {seat}")
    if result.stdout.strip():
        print(result.stdout.strip())
    return True


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
        "config_override_hint: to change tool/auth/provider, re-run with --tool/--auth-mode/--provider flags.",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    materialize_profile_runtime(profile)
    # Per-seat skill validation
    try:
        import importlib.util as _ilu
        _sr_spec = _ilu.spec_from_file_location("skill_registry", str(REPO_ROOT / "core" / "skill_registry.py"))
        if _sr_spec and _sr_spec.loader:
            _sr = _ilu.module_from_spec(_sr_spec)
            _sr_spec.loader.exec_module(_sr)
            seat_role = (profile.seat_roles or {}).get(args.seat, "")
            if seat_role:
                _sr_result = _sr.validate_all(role=seat_role)
                for _si in _sr_result.required_missing:
                    print(f"skill_blocked: {_si.name} ({_si.source}) required for {seat_role} — not found at {_si.expanded_path}")
                    if _si.fix_hint:
                        print(f"  -> {_si.fix_hint}")
                if _sr_result.required_missing:
                    print(f"\nSeat {args.seat} cannot start: {len(_sr_result.required_missing)} required skill(s) missing.")
                    return 1
                for _si in _sr_result.optional_missing:
                    print(f"skill_warning: {_si.name} ({_si.source}) — {_si.expanded_path}")
    except Exception as _exc:
        print(f"skill_check_skipped: {_exc}")

    has_overrides = args.tool or args.auth_mode or args.provider
    if has_overrides:
        switched = apply_config_overrides(
            profile, args.seat,
            tool=args.tool, auth_mode=args.auth_mode, provider=args.provider,
        )
        if switched:
            print(f"config_updated: {args.seat} session updated before start")
    if args.seat not in profile.heartbeat_seats and not args.confirm_start:
        print(render_launch_summary(profile, args.seat))
        print(
            "launch_confirmation_required: review the selected harness, seat, tool, auth mode, and provider with the user first; then re-run with --confirm-start."
        )
        return 2
    seeded_from = seed_empty_secret_from_peer(profile, args.seat)
    oauth_seeded_from = seed_empty_oauth_runtime_from_peer(profile, args.seat)
    # Ensure model/effort are written to settings.local.json before starting.
    # This covers seats started after bootstrap (via planner dispatch).
    from _common import _patch_claude_settings_from_profile
    _patch_claude_settings_from_profile(profile, [args.seat])
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
        print(
            f"oauth_seed_warning: copied credentials for {args.seat} from {oauth_seeded_from} — "
            "Claude Code may still require a fresh OAuth login for this seat"
        )
    if result.stdout.strip():
        print(result.stdout.strip())
    pane_text = capture_session_pane(profile, args.seat)
    onboarding_step = detect_claude_onboarding_step(pane_text)
    if onboarding_step is not None:
        hint = ""
        if onboarding_step in ("oauth_login", "oauth_code", "oauth_error"):
            hint = (
                " If OAuth times out (e.g. 'timeout of 15000ms exceeded'), "
                "press Enter in the tmux window to retry."
            )
        print(
            "manual_onboarding_required: "
            f"{args.seat} is waiting on Claude first-run step '{onboarding_step}'.{hint} "
            "Ask the user to complete the prompt in the TUI window, then notify the operator to take over."
        )
    else:
        # No onboarding step detected — koder is ready to enter frontstage
        if args.seat == "koder":
            # Write durable frontstage receipt
            receipt_path = write_frontstage_receipt(profile, args.seat)
            print(f"frontstage_receipt_written: {receipt_path}")
            # Send frontstage entry trigger to koder
            send_frontstage_trigger(profile, args.seat)
            print(
                "frontstage_auto_entry: "
                f"{args.seat} has been triggered to enter frontstage shell automatically. "
                "The seat will read WORKSPACE_CONTRACT.toml and enter the frontstage loop."
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
