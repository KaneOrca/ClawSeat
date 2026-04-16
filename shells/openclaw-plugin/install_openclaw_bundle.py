#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CLAWSEAT_ROOT = SCRIPT_PATH.parents[2]
DEFAULT_OPENCLAW_HOME = Path.home() / ".openclaw"

GLOBAL_SKILLS = {
    # Core runtime — loaded by ALL seats
    "gstack-harness": CLAWSEAT_ROOT / "core" / "skills" / "gstack-harness",
    # Entry points + install
    "clawseat": CLAWSEAT_ROOT / "core" / "skills" / "clawseat",
    "clawseat-install": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-install",
    "clawseat-koder-frontstage": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-koder-frontstage",
    # Base package — bundled into ClawSeat, zero external deps
    "socratic-requirements": CLAWSEAT_ROOT / "core" / "skills" / "socratic-requirements",
    "agent-monitor": CLAWSEAT_ROOT / "core" / "skills" / "agent-monitor",
    "lark-shared": CLAWSEAT_ROOT / "core" / "skills" / "lark-shared",
    "lark-im": CLAWSEAT_ROOT / "core" / "skills" / "lark-im",
    # Local convenience entrypoint
    "cs": CLAWSEAT_ROOT / "core" / "skills" / "cs",
}

WORKSPACE_KODER_SKILLS = {
    "gstack-harness": CLAWSEAT_ROOT / "core" / "skills" / "gstack-harness",
    "clawseat-install": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-install",
    "clawseat-koder-frontstage": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-koder-frontstage",
    "socratic-requirements": CLAWSEAT_ROOT / "core" / "skills" / "socratic-requirements",
    "agent-monitor": CLAWSEAT_ROOT / "core" / "skills" / "agent-monitor",
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


# Skill lists are derived from the skill registry (SSOT) rather than hardcoded.
_SKILL_REGISTRY_PATH = CLAWSEAT_ROOT / "core" / "skill_registry.py"
LARK_SKILLS_REPO = "https://github.com/larksuite/cli.git"
GSTACK_SKILLS_ROOT = Path.home() / ".gstack" / "repos" / "gstack" / ".agents" / "skills"

try:
    sys.path.insert(0, str(CLAWSEAT_ROOT / "core"))
    from skill_registry import load_registry, skills_for_source
    _REGISTRY = load_registry()
    REQUIRED_AGENT_SKILLS = [s.name for s in skills_for_source(_REGISTRY, "agent")]
    REQUIRED_GSTACK_SKILLS = [s.name for s in skills_for_source(_REGISTRY, "gstack")]
except Exception:
    # Fallback: keep working even if registry is unavailable
    REQUIRED_AGENT_SKILLS = ["lark-shared", "lark-im"]
    REQUIRED_GSTACK_SKILLS = [
        "gstack-investigate", "gstack-review", "gstack-qa", "gstack-qa-only",
        "gstack-design-review", "gstack-design-shotgun", "gstack-design-html",
        "gstack-ship", "gstack-careful", "gstack-browse", "gstack-freeze",
        "gstack-plan-eng-review",
    ]


def check_agent_skills(dry_run: bool) -> list[str]:
    """Check if required lark skills are installed in ~/.agents/skills/."""
    agents_skills = Path.home() / ".agents" / "skills"
    missing = []
    for skill_name in REQUIRED_AGENT_SKILLS:
        skill_path = agents_skills / skill_name / "SKILL.md"
        if skill_path.exists():
            print(f"agent_skill_ok: {skill_name}")
        else:
            missing.append(skill_name)
            if dry_run:
                print(f"agent_skill_missing: {skill_name} — would need install")
            else:
                print(f"agent_skill_missing: {skill_name}")
    return missing


def install_bundle(openclaw_home: Path, *, dry_run: bool) -> int:
    """Install symlinks and check external skills. Returns count of missing required skills."""
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

    missing_agent_skills = check_agent_skills(dry_run)
    if missing_agent_skills and not dry_run:
        print()
        print(f"lark_skills_required: {', '.join(missing_agent_skills)}")
        print(f"  planner needs these skills for Feishu bridge integration.")
        print(f"  Install via OpenClaw: openclaw skills install larksuite/cli")
        print(f"  Or manually clone {LARK_SKILLS_REPO} and copy skills/ to ~/.agents/skills/")

    # Check gstack skills
    missing_gstack = []
    for skill_name in REQUIRED_GSTACK_SKILLS:
        skill_path = GSTACK_SKILLS_ROOT / skill_name / "SKILL.md"
        if skill_path.exists():
            if not dry_run:
                pass  # suppress per-skill OK to keep output clean
        else:
            missing_gstack.append(skill_name)
    if missing_gstack:
        if dry_run:
            print(f"gstack_skills_missing: {', '.join(missing_gstack)}")
        else:
            print()
            print(f"gstack_skills_required: {', '.join(missing_gstack)}")
            print(f"  Specialist seats need gstack skills for implementation, review, QA, and design.")
            print(f"  Install gstack first: see https://github.com/gstack-cli/gstack")
    elif not dry_run:
        print("gstack_skills: all {0} required skills present".format(len(REQUIRED_GSTACK_SKILLS)))

    return len(missing_agent_skills) + len(missing_gstack)


def main() -> int:
    args = parse_args()
    openclaw_home = Path(args.openclaw_home).expanduser()

    if not CLAWSEAT_ROOT.exists():
        raise RuntimeError(f"CLAWSEAT_ROOT not found: {CLAWSEAT_ROOT}")

    missing_count = install_bundle(openclaw_home, dry_run=args.dry_run)

    if not args.dry_run:
        print()
        if missing_count > 0:
            print(f"install_incomplete: {missing_count} external skill(s) missing — seats may lack key capabilities")
            print("  Run the install commands above, then re-run this script to verify.")
            return 2  # partial install — bundled skills OK, external skills missing
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
