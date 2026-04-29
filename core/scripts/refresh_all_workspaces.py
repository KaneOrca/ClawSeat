#!/usr/bin/env python3
"""Batch regenerate project workspaces with the current ClawSeat templates."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def _home() -> Path:
    return Path(os.environ.get("CLAWSEAT_REAL_HOME") or os.environ.get("HOME") or str(Path.home())).expanduser()


def _projects_root() -> Path:
    return _home() / ".agents" / "projects"


def _agent_admin_path() -> Path:
    override = os.environ.get("CLAWSEAT_AGENT_ADMIN")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "core" / "scripts" / "agent_admin.py"


def _parse_projects(value: str | None) -> list[str] | None:
    if value is None:
        return None
    projects = [item.strip() for item in value.split(",") if item.strip()]
    return projects


def list_projects(selected: list[str] | None = None) -> list[str]:
    if selected is not None:
        return sorted(dict.fromkeys(selected))
    root = _projects_root()
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def regenerate_command(project: str) -> list[str]:
    return [
        sys.executable,
        str(_agent_admin_path()),
        "engineer",
        "regenerate-workspace",
        "--all-seats",
        "--project",
        project,
        "--yes",
    ]


def refresh_project(project: str, *, dry_run: bool = False) -> None:
    cmd = regenerate_command(project)
    if dry_run:
        print(f"[dry-run] {shlex.join(cmd)}")
        return
    print(f"==> refreshing {project}")
    subprocess.run(cmd, check=True)
    print(f"==> refreshed {project}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch refresh ClawSeat workspaces with current render templates.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print regenerate commands without running them.")
    parser.add_argument("--projects", help="Comma-separated project subset; default is all ~/.agents/projects entries.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    projects = list_projects(_parse_projects(args.projects))
    if not projects:
        print(f"no projects found under {_projects_root()}")
        return 0
    for project in projects:
        refresh_project(project, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
