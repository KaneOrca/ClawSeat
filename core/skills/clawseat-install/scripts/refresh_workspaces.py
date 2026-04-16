#!/usr/bin/env python3
"""
refresh_workspaces.py — Regenerate all seat workspace files after ClawSeat update.

Rewrites AGENTS.md, WORKSPACE_CONTRACT.toml, settings.local.json, and
skill paths for every seat in the project, using current template + profile.

Also refreshes koder's OpenClaw workspace if --koder-workspace is given.

Usage:
    # Refresh backend seats only
    python3 refresh_workspaces.py --profile <profile.toml> --project install

    # Refresh backend seats + koder OpenClaw workspace
    python3 refresh_workspaces.py --profile <profile.toml> --project install \
        --koder-workspace ~/.openclaw/workspace-koder \
        --feishu-group-id oc_xxx
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
_core = str(REPO_ROOT / "core")
if _core not in sys.path:
    sys.path.insert(0, _core)

_harness_scripts = str(REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts")
if _harness_scripts not in sys.path:
    sys.path.insert(0, _harness_scripts)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Refresh all ClawSeat workspace files after code update.")
    p.add_argument("--profile", required=True, help="Path to the dynamic profile TOML.")
    p.add_argument("--project", default="install", help="Project name.")
    p.add_argument("--koder-workspace", help="OpenClaw koder workspace path. If given, also refreshes koder files.")
    p.add_argument("--feishu-group-id", default="", help="Feishu group ID for the project.")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def refresh_backend_seats(profile_path: str, project: str, *, dry_run: bool) -> int:
    """Re-run agent_admin apply-template + materialize_profile_runtime for all backend seats."""
    from _common import load_profile, materialize_profile_runtime

    profile = load_profile(profile_path)
    agent_admin = REPO_ROOT / "core" / "scripts" / "agent_admin.py"

    # Re-apply template to regenerate AGENTS.md, WORKSPACE_CONTRACT, settings
    print(f"re-applying template '{profile.template_name}' for project '{project}'...")
    result = subprocess.run(
        [
            "python3", str(agent_admin),
            "project", "bootstrap",
            "--template", profile.template_name,
            "--local", str(profile.profile_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"warning: agent_admin bootstrap returned {result.returncode}", file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)

    # Re-materialize runtime (status scripts, heartbeat, settings patches)
    if not dry_run:
        print("re-materializing profile runtime...")
        materialize_profile_runtime(profile)

    # Report what was refreshed
    for seat in profile.seats:
        workspace = profile.workspace_for(seat)
        agents_md = workspace / "AGENTS.md"
        contract = workspace / "WORKSPACE_CONTRACT.toml"
        if agents_md.exists():
            print(f"  refreshed: {seat} AGENTS.md ({agents_md})")
        if contract.exists():
            print(f"  refreshed: {seat} WORKSPACE_CONTRACT.toml")

    return 0


def refresh_koder(
    koder_workspace: str,
    project: str,
    profile_path: str,
    feishu_group_id: str,
    *,
    dry_run: bool,
) -> int:
    """Re-run init_koder.py to refresh koder's OpenClaw workspace."""
    init_koder = SCRIPT_DIR / "init_koder.py"
    cmd = [
        "python3", str(init_koder),
        "--workspace", koder_workspace,
        "--project", project,
        "--profile", profile_path,
        "--feishu-group-id", feishu_group_id,
    ]
    if dry_run:
        cmd.append("--dry-run")

    print(f"refreshing koder workspace at {koder_workspace}...")
    result = subprocess.run(cmd, text=True, check=False)
    return result.returncode


def main() -> int:
    args = parse_args()

    errors = 0

    # 1. Refresh backend seats
    rc = refresh_backend_seats(args.profile, args.project, dry_run=args.dry_run)
    if rc != 0:
        errors += 1

    # 2. Refresh koder (if workspace given)
    if args.koder_workspace:
        rc = refresh_koder(
            args.koder_workspace,
            args.project,
            args.profile,
            args.feishu_group_id,
            dry_run=args.dry_run,
        )
        if rc != 0:
            errors += 1

    if errors == 0:
        print(f"\nall workspaces refreshed for project '{args.project}'")
    else:
        print(f"\nrefresh completed with {errors} error(s)", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
