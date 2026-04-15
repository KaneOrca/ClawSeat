#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CLAWSEAT_ROOT = SCRIPT_PATH.parents[2]
DEFAULT_OPENCLAW_HOME = Path.home() / ".openclaw"

GLOBAL_SKILLS = {
    "clawseat": CLAWSEAT_ROOT / "core" / "skills" / "clawseat",
    "clawseat-install": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-install",
    "clawseat-koder-frontstage": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-koder-frontstage",
}

WORKSPACE_KODER_SKILLS = {
    "clawseat-koder-frontstage": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-koder-frontstage",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the ClawSeat OpenClaw skill bundle into ~/.openclaw."
    )
    parser.add_argument(
        "--openclaw-home",
        default=str(DEFAULT_OPENCLAW_HOME),
        help="Path to the target OpenClaw home. Defaults to ~/.openclaw.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the planned symlink operations without changing the filesystem.",
    )
    return parser.parse_args()


def ensure_symlink(destination: Path, source: Path, *, dry_run: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        current = destination.resolve()
        if current == source.resolve():
            print(f"already_installed: {destination} -> {source}")
            return
        if dry_run:
            print(f"would_replace_symlink: {destination} -> {source}")
            return
        destination.unlink()
    elif destination.exists():
        raise RuntimeError(
            f"refusing to overwrite non-symlink path: {destination}. Move it away first."
        )
    if dry_run:
        print(f"would_install: {destination} -> {source}")
        return
    destination.symlink_to(source)
    print(f"installed: {destination} -> {source}")


def install_bundle(openclaw_home: Path, *, dry_run: bool) -> None:
    skills_root = openclaw_home / "skills"
    workspace_koder_skills_root = openclaw_home / "workspace-koder" / "skills"

    for skill_name, source in GLOBAL_SKILLS.items():
        ensure_symlink(skills_root / skill_name, source, dry_run=dry_run)

    for skill_name, source in WORKSPACE_KODER_SKILLS.items():
        ensure_symlink(
            workspace_koder_skills_root / skill_name,
            source,
            dry_run=dry_run,
        )


def main() -> int:
    args = parse_args()
    openclaw_home = Path(args.openclaw_home).expanduser()

    if not CLAWSEAT_ROOT.exists():
        raise RuntimeError(f"CLAWSEAT_ROOT not found: {CLAWSEAT_ROOT}")

    install_bundle(openclaw_home, dry_run=args.dry_run)

    if not args.dry_run:
        print()
        print("next_steps:")
        print(f"  export CLAWSEAT_ROOT=\"{CLAWSEAT_ROOT}\"")
        print("  在 OpenClaw / 飞书里直接说：安装 ClawSeat 或 启动 ClawSeat")
        print("  OpenClaw 应优先加载 $clawseat，而不是要求用户输入 /cs")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
