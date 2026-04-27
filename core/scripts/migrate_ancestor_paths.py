#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import subprocess
from pathlib import Path


def real_home() -> Path:
    override = os.environ.get("CLAWSEAT_REAL_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate v1/v2 ancestor path names to memory/QA path names."
    )
    parser.add_argument("--project", action="append", help="Project name to migrate. May be repeated.")
    parser.add_argument("--all", action="store_true", help="Migrate every project under ~/.agents/tasks.")
    return parser.parse_args()


def project_names(home: Path, args: argparse.Namespace) -> list[str]:
    names = [name for value in (args.project or []) for name in value.split(",") if name.strip()]
    if names:
        return sorted(dict.fromkeys(names))
    tasks_root = home / ".agents" / "tasks"
    if args.all and tasks_root.is_dir():
        return sorted(path.name for path in tasks_root.iterdir() if path.is_dir())
    return []


def symlink_alias(alias: Path, target: Path, changed: list[str]) -> None:
    if alias.is_symlink():
        return
    if alias.exists():
        backup = alias.with_name(alias.name + ".deprecated")
        suffix = 1
        while backup.exists():
            backup = alias.with_name(f"{alias.name}.deprecated.{suffix}")
            suffix += 1
        alias.rename(backup)
        changed.append(f"backup {alias} -> {backup}")
    try:
        alias.symlink_to(target.name)
        changed.append(f"symlink {alias} -> {target.name}")
    except OSError as exc:
        changed.append(f"warn symlink failed {alias}: {exc}")


def rename_with_alias(old: Path, new: Path, changed: list[str]) -> None:
    if old.is_symlink():
        return
    if old.exists() and not new.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        changed.append(f"rename {old} -> {new}")
    if new.exists() and not old.exists():
        symlink_alias(old, new, changed)
    elif new.exists() and old.exists() and not old.is_symlink():
        symlink_alias(old, new, changed)


def run_launchctl(args: list[str], changed: list[str]) -> None:
    if platform.system() != "Darwin":
        return
    try:
        subprocess.run(["launchctl", *args], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        changed.append(f"warn launchctl {' '.join(args)} failed: {exc}")


def migrate_launch_agent(home: Path, project: str, changed: list[str]) -> None:
    launch_agents = home / "Library" / "LaunchAgents"
    old_label = f"com.clawseat.{project}.ancestor-patrol"
    new_label = f"com.clawseat.{project}.qa-patrol"
    old_path = launch_agents / f"{old_label}.plist"
    new_path = launch_agents / f"{new_label}.plist"

    if old_path.exists() and not old_path.is_symlink():
        run_launchctl(["bootout", f"gui/{os.getuid()}/{old_label}"], changed)
        if not new_path.exists():
            old_path.rename(new_path)
            changed.append(f"rename {old_path} -> {new_path}")
        else:
            symlink_alias(old_path, new_path, changed)
    if new_path.exists():
        text = new_path.read_text(encoding="utf-8")
        updated = text.replace(old_label, new_label).replace(
            "session-name ancestor --project", "session-name memory --project"
        ).replace(
            "--project '{PROJECT}' ancestor", "--project '{PROJECT}' memory"
        )
        if updated != text:
            new_path.write_text(updated, encoding="utf-8")
            changed.append(f"patch {new_path}")
        symlink_alias(old_path, new_path, changed)
        run_launchctl(["bootstrap", f"gui/{os.getuid()}", str(new_path)], changed)


def patch_profile(path: Path, changed: list[str]) -> None:
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8")
    updated = original.replace('active_loop_owner = "planner"', 'active_loop_owner = "memory"')
    updated = updated.replace('default_notify_target = "planner"', 'default_notify_target = "memory"')
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        changed.append(f"patch {path}")


def migrate_project(home: Path, project: str) -> list[str]:
    changed: list[str] = []
    tasks_root = home / ".agents" / "tasks" / project
    handoffs = tasks_root / "patrol" / "handoffs"

    rename_with_alias(handoffs / "ancestor-bootstrap.md", handoffs / "memory-bootstrap.md", changed)
    rename_with_alias(handoffs / "ancestor-kickoff.txt", handoffs / "memory-kickoff.txt", changed)
    rename_with_alias(tasks_root / "ancestor-provider.env", tasks_root / "memory-provider.env", changed)
    rename_with_alias(
        tasks_root / "ancestor-provider-decision.md",
        tasks_root / "memory-provider-decision.md",
        changed,
    )
    migrate_launch_agent(home, project, changed)

    profiles = home / ".agents" / "profiles"
    patch_profile(profiles / f"{project}-profile-dynamic.toml", changed)
    return changed


def main() -> int:
    home = real_home()
    args = parse_args()
    names = project_names(home, args)
    if not names:
        print("migrate_ancestor_paths: no projects selected")
        return 0
    for project in names:
        changed = migrate_project(home, project)
        if changed:
            print(f"migrate_ancestor_paths: {project}")
            for item in changed:
                print(f"  {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
