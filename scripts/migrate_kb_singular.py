#!/usr/bin/env python3
"""Migrate memory project KB directories from plural to singular names."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


RENAMES = {
    "decisions": "decision",
    "findings": "finding",
    "plans": "plan",
    "tasks": "task",
}


def _default_projects_root() -> Path:
    return Path.home() / ".agents" / "memory" / "projects"


def _move_file(src: Path, dst: Path, *, commit: bool, report: dict[str, Any]) -> None:
    if dst.exists():
        if src.read_bytes() == dst.read_bytes():
            report["duplicates"].append(str(dst))
            if commit:
                src.unlink()
            return
        conflict = dst.with_name(f"{dst.stem}.from-plural{dst.suffix}")
        counter = 1
        while conflict.exists():
            conflict = dst.with_name(f"{dst.stem}.from-plural-{counter}{dst.suffix}")
            counter += 1
        report["conflicts"].append({"source": str(src), "target": str(conflict)})
        if commit:
            shutil.move(str(src), str(conflict))
        return

    report["moved_files"].append({"source": str(src), "target": str(dst)})
    if commit:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))


def migrate_project(project_dir: Path, *, commit: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "project": project_dir.name,
        "renamed_dirs": [],
        "merged_dirs": [],
        "moved_files": [],
        "duplicates": [],
        "conflicts": [],
    }
    for plural, singular in RENAMES.items():
        plural_dir = project_dir / plural
        singular_dir = project_dir / singular
        if not plural_dir.exists():
            continue
        if not singular_dir.exists():
            report["renamed_dirs"].append({"source": str(plural_dir), "target": str(singular_dir)})
            if commit:
                plural_dir.rename(singular_dir)
            continue

        report["merged_dirs"].append({"source": str(plural_dir), "target": str(singular_dir)})
        for src in sorted(path for path in plural_dir.rglob("*") if path.is_file()):
            rel = src.relative_to(plural_dir)
            _move_file(src, singular_dir / rel, commit=commit, report=report)
        if commit:
            for path in sorted(plural_dir.rglob("*"), reverse=True):
                if path.is_dir():
                    path.rmdir()
            plural_dir.rmdir()
    return report


def migrate_all(projects_root: Path, *, commit: bool) -> dict[str, Any]:
    reports = []
    if projects_root.exists():
        for project_dir in sorted(path for path in projects_root.iterdir() if path.is_dir()):
            reports.append(migrate_project(project_dir, commit=commit))
    return {"mode": "commit" if commit else "dry-run", "projects_root": str(projects_root), "projects": reports}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-root", default=str(_default_projects_root()))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    report = migrate_all(Path(args.projects_root).expanduser(), commit=bool(args.commit))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
