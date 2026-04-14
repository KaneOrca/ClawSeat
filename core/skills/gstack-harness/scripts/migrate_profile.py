#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a fixed harness profile into a dynamic-roster profile.")
    parser.add_argument("--source-profile", required=True, help="Existing profile.toml path.")
    parser.add_argument("--output-profile", required=True, help="Destination dynamic profile path.")
    parser.add_argument("--project-name", help="Optional project-name override.")
    parser.add_argument("--repo-root", help="Optional repo-root override.")
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Generate a new-project profile that only bootstraps koder and does not preserve legacy seats.",
    )
    return parser.parse_args()


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def q_array(values: list[str]) -> str:
    return "[" + ", ".join(q(value) for value in values) + "]"


def build_lines(data: dict[str, Any], *, project_name: str, repo_root: str, bootstrap_only: bool) -> list[str]:
    tasks_root = f"/tmp/{project_name}/.tasks"
    workspace_root = str(Path.home() / ".agents" / "workspaces" / project_name)
    heartbeat_owner = str(data.get("heartbeat_owner", "koder"))
    active_loop_owner = str(data.get("active_loop_owner", heartbeat_owner))
    default_notify_target = str(data.get("default_notify_target", active_loop_owner))
    legacy_seat_roles = {str(k): str(v) for k, v in data.get("seat_roles", {}).items() if str(k) != heartbeat_owner}
    legacy_seats = [seat for seat in data.get("seats", []) if str(seat) != heartbeat_owner]
    if bootstrap_only:
        active_loop_owner = heartbeat_owner
        default_notify_target = heartbeat_owner
        legacy_seat_roles = {}
        legacy_seats = []

    lines = [
        "version = 2",
        f'profile_name = {q(str(data.get("profile_name", project_name + ".dynamic")))}',
        f'description = {q(str(data.get("description", "dynamic-roster harness profile")))}',
        f'template_name = {q("gstack-harness-dynamic-roster")}',
        f'project_name = {q(project_name)}',
        f'repo_root = {q(repo_root)}',
        f'tasks_root = {q(tasks_root)}',
        f'project_doc = {q(tasks_root + "/PROJECT.md")}',
        f'tasks_doc = {q(tasks_root + "/TASKS.md")}',
        f'status_doc = {q(tasks_root + "/STATUS.md")}',
        f'send_script = {q(str(data["send_script"]))}',
        f'status_script = {q(tasks_root + "/patrol/check-status.sh")}',
        f'patrol_script = {q(tasks_root + "/patrol/patrol-supervisor.sh")}',
        f'agent_admin = {q(str(data["agent_admin"]))}',
        f'workspace_root = {q(workspace_root)}',
        f'handoff_dir = {q(tasks_root + "/patrol/handoffs")}',
        f'heartbeat_owner = {q(heartbeat_owner)}',
        f'active_loop_owner = {q(active_loop_owner)}',
        f'default_notify_target = {q(default_notify_target)}',
        f'heartbeat_receipt = {q(workspace_root + f"/{heartbeat_owner}/HEARTBEAT_RECEIPT.toml")}',
        'seats = ["koder"]',
        'heartbeat_seats = ["koder"]',
        "",
        "[seat_roles]",
        'koder = "frontstage-supervisor"',
        "",
        "[dynamic_roster]",
        "enabled = true",
        'session_root = "~/.agents/sessions"',
        'bootstrap_seats = ["koder"]',
        'default_start_seats = ["koder"]',
        f"compat_legacy_seats = {'false' if bootstrap_only else 'true'}",
        "",
        f"legacy_seats = {q_array([str(seat) for seat in legacy_seats])}",
        "",
        "[legacy_seat_roles]",
    ]
    if legacy_seat_roles:
        for seat, role in legacy_seat_roles.items():
            lines.append(f"{seat} = {q(role)}")
    lines.extend(
        [
            "",
            "[patrol]",
            "enabled = false",
            f'planner_brief_path = {q(tasks_root + "/planner/PLANNER_BRIEF.md")}',
        ]
    )
    return lines


def main() -> int:
    args = parse_args()
    source_profile = Path(args.source_profile).expanduser()
    output_profile = Path(args.output_profile).expanduser()
    data = load_toml(source_profile)
    project_name = args.project_name or str(data["project_name"])
    repo_root = args.repo_root or str(data["repo_root"])
    lines = build_lines(
        data,
        project_name=project_name,
        repo_root=repo_root,
        bootstrap_only=args.bootstrap_only,
    )
    output_profile.parent.mkdir(parents=True, exist_ok=True)
    output_profile.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output_profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
