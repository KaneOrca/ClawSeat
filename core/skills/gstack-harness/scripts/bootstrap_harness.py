#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import (
    HarnessProfile,
    REPO_ROOT,
    load_profile,
    make_local_override,
    materialize_profile_runtime,
    require_success,
    run_command,
    seed_empty_secret_from_peer,
)


def _link_sandbox_tasks_to_real_home(
    profile: HarnessProfile,
    seats: list[str],
    *,
    _agents_home: Path | None = None,
) -> None:
    """Create sandbox_home/.agents/tasks/<project>/<seat> → real tasks_root/<seat> symlinks.

    Idempotent. Fail-safe: warns on error, never raises.
    """
    try:
        import tomllib as _tomllib
    except ModuleNotFoundError:
        import tomli as _tomllib  # type: ignore

    agents_home = _agents_home or (Path.home() / ".agents")

    for seat in seats:
        session_path = agents_home / "sessions" / profile.project_name / seat / "session.toml"
        if not session_path.is_file():
            continue
        try:
            with open(session_path, "rb") as _f:
                session_data = _tomllib.load(_f)
        except Exception as exc:
            print(f"warn: _link_sandbox_tasks: cannot read session for {seat}: {exc}", file=sys.stderr)
            continue

        runtime_dir = session_data.get("runtime_dir", "")
        if not runtime_dir:
            continue
        sandbox_home = Path(runtime_dir) / "home"
        if not sandbox_home.is_dir():
            continue

        real_tasks = profile.tasks_root / seat
        sandbox_tasks_parent = sandbox_home / ".agents" / "tasks" / profile.project_name
        sandbox_tasks = sandbox_tasks_parent / seat

        try:
            real_tasks.mkdir(parents=True, exist_ok=True)
            if sandbox_tasks.is_symlink():
                if sandbox_tasks.resolve() == real_tasks.resolve():
                    continue
                print(
                    f"warn: _link_sandbox_tasks: {sandbox_tasks} is symlink to different target, skipping",
                    file=sys.stderr,
                )
                continue
            if sandbox_tasks.exists():
                print(
                    f"warn: _link_sandbox_tasks: {sandbox_tasks} is a regular dir with data, skipping",
                    file=sys.stderr,
                )
                continue
            sandbox_tasks_parent.mkdir(parents=True, exist_ok=True)
            sandbox_tasks.symlink_to(real_tasks)
        except Exception as exc:
            print(f"warn: _link_sandbox_tasks: failed to link {seat}: {exc}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a project from a gstack harness profile.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--project-name", help="Override project name from the profile.")
    parser.add_argument("--repo-root", help="Override repo root from the profile.")
    parser.add_argument("--start", action="store_true", help="Start the project monitor after bootstrap.")
    parser.add_argument("--refresh-existing", action="store_true", help="Refresh workspace files for already-deployed seats from current template.")
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
        materialized_seats=list(profile.materialized_seats or []),
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

    # Validate skills before bootstrap — block on required missing
    try:
        import importlib.util as _ilu
        _sr_spec = _ilu.spec_from_file_location("skill_registry", str(REPO_ROOT / "core" / "skill_registry.py"))
        if _sr_spec and _sr_spec.loader:
            _sr = _ilu.module_from_spec(_sr_spec)
            # Python 3.12+ dataclass(slots=True) needs the module in sys.modules
            sys.modules.setdefault("skill_registry", _sr)
            _sr_spec.loader.exec_module(_sr)
            _sr_result = _sr.validate_all()
            for _si in _sr_result.required_missing:
                print(f"skill_blocked: {_si.name} ({_si.source}) — {_si.expanded_path}", file=sys.stderr)
                if _si.fix_hint:
                    print(f"  -> {_si.fix_hint}", file=sys.stderr)
            if _sr_result.required_missing:
                print(f"\nBootstrap aborted: {len(_sr_result.required_missing)} required skill(s) missing.", file=sys.stderr)
                return 1
            for _si in _sr_result.optional_missing:
                print(f"skill_warning: {_si.name} ({_si.source}) — {_si.expanded_path}", file=sys.stderr)
    except (ImportError, FileNotFoundError, OSError) as _exc:
        print(f"skill_check_skipped: {_exc}", file=sys.stderr)

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
        _link_sandbox_tasks_to_real_home(
            effective_profile,
            list(effective_profile.materialized_seats or effective_profile.seats),
        )
        for seat in (effective_profile.materialized_seats or effective_profile.seats):
            seed_empty_secret_from_peer(effective_profile, seat)
            # OAuth is user-managed via the TUI; nothing to seed here.
        if args.refresh_existing:
            for seat in (effective_profile.materialized_seats or effective_profile.seats):
                refresh_cmd = [
                    "python3", str(profile.agent_admin),
                    "engineer", "refresh-workspace", seat,
                    "--project", project_name,
                ]
                refresh_result = run_command(refresh_cmd, cwd=profile.repo_root)
                require_success(refresh_result, f"bootstrap_harness refresh-existing {seat}")
                if refresh_result.stdout.strip():
                    print(refresh_result.stdout.strip())
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
