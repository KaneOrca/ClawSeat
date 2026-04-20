#!/usr/bin/env python3
"""install_bundled_skills.py — Install ClawSeat shared skills into ~/.openclaw/skills/.

Phase 0 of the ClawSeat install flow. This script is agent-agnostic:
it does NOT touch any per-agent workspace. It only creates the global
skill symlinks under ~/.openclaw/skills/ and checks for required
external skills (lark-* and gstack-*).

For the Phase 3 step (overlaying ClawSeat koder templates into a chosen
OpenClaw agent workspace), run install_koder_overlay.py separately.

Rationale for the split
-----------------------
The removed ``install_openclaw_bundle.py`` hardcoded
``~/.openclaw/workspace-koder/skills/`` as the overlay target. That
forced every install to use the agent named "koder" and prevented
users from overlaying ClawSeat onto a different OpenClaw agent
(cartooner, mor, scout, etc.). Splitting the script keeps Phase 0
(shared skills) deterministic and defers the "which agent" choice to
Phase 2 (after the memory seat can enumerate the candidates). The old
wrapper was deleted after the split stabilized; see
``core/skills/clawseat-install/references/ancestor-runbook.md`` for the
canonical 6-phase flow.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CLAWSEAT_ROOT = SCRIPT_PATH.parents[2]

# Resolve via core/lib/real_home — bypasses isolated/sandbox HOME so skill
# symlinks and gstack/lark skill probes target the real user home, not the
# harness sandbox (ancestor CC launcher, tmux seat, Docker --user, etc.).
_CORE_LIB = CLAWSEAT_ROOT / "core" / "lib"
if str(_CORE_LIB) not in sys.path:
    sys.path.insert(0, str(_CORE_LIB))
from real_home import real_user_home  # noqa: E402

_USER_HOME = real_user_home()
DEFAULT_OPENCLAW_HOME = _USER_HOME / ".openclaw"

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
    "tmux-basics": CLAWSEAT_ROOT / "core" / "skills" / "tmux-basics",
    # Local convenience entrypoint
    "cs": CLAWSEAT_ROOT / "core" / "skills" / "cs",
}

LARK_SKILLS_REPO = "https://github.com/larksuite/cli.git"


def _resolve_gstack_skills_root() -> Path:
    """Return the gstack skills root. Honors GSTACK_SKILLS_ROOT env.

    Keep in sync with core/skill_registry.py::_resolve_gstack_skills_root
    and core/skills/gstack-harness/scripts/dispatch_task.py. Operators who
    cloned gstack outside the canonical `~/.gstack/repos/gstack` can export
    GSTACK_SKILLS_ROOT=/abs/path/to/.agents/skills and this install step
    will symlink from there instead.
    """
    env = os.environ.get("GSTACK_SKILLS_ROOT", "").strip()
    if env:
        return Path(env).expanduser()
    return _USER_HOME / ".gstack" / "repos" / "gstack" / ".agents" / "skills"


GSTACK_SKILLS_ROOT = _resolve_gstack_skills_root()

# Skill lists are derived from the skill registry (SSOT) rather than hardcoded.
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install the ClawSeat global skill symlinks into ~/.openclaw/skills/. "
            "This is Phase 0 of the install flow; it does not modify any agent workspace."
        )
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


def check_agent_skills(dry_run: bool) -> list[str]:
    """Check if required lark skills are installed in ~/.agents/skills/."""
    agents_skills = _USER_HOME / ".agents" / "skills"
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


def check_gstack_skills(dry_run: bool) -> list[str]:
    missing = []
    for skill_name in REQUIRED_GSTACK_SKILLS:
        skill_path = GSTACK_SKILLS_ROOT / skill_name / "SKILL.md"
        if not skill_path.exists():
            missing.append(skill_name)
    return missing


def install_bundled_skills(openclaw_home: Path, *, dry_run: bool) -> int:
    """Install global skill symlinks and check external skills.

    Returns the count of missing required external skills (lark + gstack).
    Returns 0 when the bundled portion is fully installed and all external
    skills are already present.
    """
    skills_root = openclaw_home / "skills"

    for skill_name, source in GLOBAL_SKILLS.items():
        ensure_symlink(skills_root / skill_name, source, dry_run=dry_run)

    missing_agent_skills = check_agent_skills(dry_run)
    if missing_agent_skills and not dry_run:
        print()
        print(f"lark_skills_required: {', '.join(missing_agent_skills)}")
        print("  planner needs these skills for Feishu bridge integration.")
        print("  Install via OpenClaw: openclaw skills install larksuite/cli")
        print(f"  Or manually clone {LARK_SKILLS_REPO} and copy skills/ to ~/.agents/skills/")

    missing_gstack = check_gstack_skills(dry_run)
    if missing_gstack:
        if dry_run:
            print(f"gstack_skills_missing: {', '.join(missing_gstack)}")
        else:
            print()
            print(f"gstack_skills_required: {', '.join(missing_gstack)}")
            print(f"  Looked under: {GSTACK_SKILLS_ROOT}")
            print("  Specialist seats need gstack skills for implementation, review, QA, and design.")
            print("  Install gstack at the canonical path:")
            print("    git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.gstack/repos/gstack")
            print("    cd ~/.gstack/repos/gstack && ./setup")
            print("  Or, if gstack is already installed elsewhere:")
            print("    export GSTACK_SKILLS_ROOT=/absolute/path/to/.agents/skills")
            print("    # then re-run this install_bundled_skills.py")
    elif not dry_run:
        print(f"gstack_skills: all {len(REQUIRED_GSTACK_SKILLS)} required skills present")

    return len(missing_agent_skills) + len(missing_gstack)


def main() -> int:
    args = parse_args()
    openclaw_home = Path(args.openclaw_home).expanduser()

    if not CLAWSEAT_ROOT.exists():
        raise RuntimeError(f"CLAWSEAT_ROOT not found: {CLAWSEAT_ROOT}")

    missing_count = install_bundled_skills(openclaw_home, dry_run=args.dry_run)

    if not args.dry_run:
        print()
        if missing_count > 0:
            print(
                f"bundled_skills_install_incomplete: {missing_count} external skill(s) missing "
                "— seats may lack key capabilities"
            )
            print("  Run the install commands above, then re-run this script to verify.")
            return 2  # partial install — bundled skills OK, external skills missing
        print("bundled_skills_install_ok")
        print()
        print("next_steps:")
        print("  1. Start the memory seat so the installer can enumerate OpenClaw agents:")
        print(f'     python3 "{CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/start_seat.py" \\')
        print('       --profile "/tmp/<project>-profile-dynamic.toml" --seat memory --confirm-start')
        print("  2. Query memory for the agent list and pick your koder overlay target:")
        print(f'     python3 "{CLAWSEAT_ROOT}/core/skills/memory-oracle/scripts/query_memory.py" \\')
        print("       --file openclaw --section agents")
        print("  3. Overlay ClawSeat koder templates into the chosen agent workspace:")
        print(f'     python3 "{CLAWSEAT_ROOT}/shells/openclaw-plugin/install_koder_overlay.py" \\')
        print("       --agent <AGENT_NAME>")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
