#!/usr/bin/env python3
"""install_koder_overlay.py — Overlay ClawSeat koder skill symlinks into a chosen OpenClaw agent workspace.

Phase 3 of the ClawSeat install flow. This script is explicitly
agent-scoped: it requires ``--agent <NAME>`` and refuses to pick a
default. The agent selection MUST come from the user after consulting
the memory seat, which is the canonical source of truth for the set of
OpenClaw agents on the host (see core/skills/clawseat-install/references/
memory-query-protocol.md).

This script:

* symlinks a fixed set of workspace-scoped skills into
  ``~/.openclaw/workspace-<agent>/skills/``
* leaves every other file in that workspace untouched
* does NOT write the managed MD scaffolding (IDENTITY / SOUL / TOOLS /
  MEMORY / AGENTS / WORKSPACE_CONTRACT) — that is the job of
  ``core/skills/clawseat-install/scripts/init_koder.py``

Contract:

* ``--agent`` is required; omitting it exits 2 with a pointer to the
  memory query protocol.
* The target workspace ``~/.openclaw/workspace-<agent>/`` must exist;
  otherwise the script exits 3 and lists candidate directories it did
  find (without guessing — the list is purely informational; real agent
  enumeration still belongs to memory).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CLAWSEAT_ROOT = SCRIPT_PATH.parents[2]
DEFAULT_OPENCLAW_HOME = Path.home() / ".openclaw"

# Skills symlinked into <agent_workspace>/skills/.
# Intentionally a subset of GLOBAL_SKILLS from install_bundled_skills.py —
# the agent workspace only needs the skills that koder-as-agent consults
# directly. Platform-level skills (cs, lark-im, etc.) live solely under
# ~/.openclaw/skills/.
WORKSPACE_KODER_SKILLS = {
    "gstack-harness": CLAWSEAT_ROOT / "core" / "skills" / "gstack-harness",
    "clawseat-install": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-install",
    "clawseat-koder-frontstage": CLAWSEAT_ROOT / "core" / "skills" / "clawseat-koder-frontstage",
    "socratic-requirements": CLAWSEAT_ROOT / "core" / "skills" / "socratic-requirements",
    "agent-monitor": CLAWSEAT_ROOT / "core" / "skills" / "agent-monitor",
    "tmux-basics": CLAWSEAT_ROOT / "core" / "skills" / "tmux-basics",
}

MEMORY_PROTOCOL_HINT = (
    "Agent selection must come from the memory seat, which owns the\n"
    "canonical list of OpenClaw agents on this host. Before re-running\n"
    "this script:\n"
    "\n"
    "  1. Start the memory seat (once per install, Phase 1):\n"
    "       python3 \"$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py\" \\\n"
    "         --profile \"/tmp/<project>-profile-dynamic.toml\" --seat memory --confirm-start\n"
    "\n"
    "  2. Query the memory knowledge base for the agent list (Phase 2):\n"
    "       python3 \"$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py\" \\\n"
    "         --file openclaw --section agents\n"
    "\n"
    "  3. Re-run install_koder_overlay.py with --agent <NAME>.\n"
    "\n"
    "See core/skills/clawseat-install/references/memory-query-protocol.md for the\n"
    "seat->memory contract that forbids hardcoded agent defaults in install scripts."
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Overlay ClawSeat koder skill symlinks into an OpenClaw agent workspace. "
            "Phase 3 of the ClawSeat install flow."
        )
    )
    parser.add_argument(
        "--agent",
        required=True,
        help=(
            "OpenClaw agent name (e.g. 'koder', 'cartooner'). The overlay target "
            "is <openclaw-home>/workspace-<agent>/skills/. Ask the memory seat for "
            "the canonical agent list; this script never picks a default."
        ),
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
    return parser.parse_args(argv)


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


def resolve_workspace(openclaw_home: Path, agent: str) -> Path:
    return openclaw_home / f"workspace-{agent}"


def _candidate_workspaces(openclaw_home: Path) -> list[str]:
    """Return agent names derived from ``workspace-*`` directories.

    This is **not** an agent enumeration contract — the memory seat owns
    that. It is only used to produce a clearer error message when the user
    passes a name that has no corresponding workspace directory.
    """
    if not openclaw_home.is_dir():
        return []
    names: list[str] = []
    for entry in sorted(openclaw_home.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        if not entry.name.startswith("workspace-"):
            continue
        agent_name = entry.name[len("workspace-"):]
        if agent_name:
            names.append(agent_name)
    return names


def install_overlay(
    openclaw_home: Path,
    agent: str,
    *,
    dry_run: bool,
) -> int:
    """Install workspace skill symlinks for ``agent`` into ``openclaw_home``.

    Returns 0 on success, 3 if the chosen agent's workspace directory is
    missing. Raises on other filesystem errors.
    """
    workspace = resolve_workspace(openclaw_home, agent)

    if not workspace.is_dir():
        candidates = _candidate_workspaces(openclaw_home)
        print(f"error: agent workspace not found: {workspace}", file=sys.stderr)
        if candidates:
            print(
                "  workspace-* directories found under "
                f"{openclaw_home}: {', '.join(candidates)}",
                file=sys.stderr,
            )
            print(
                "  (This list is informational only; re-query memory for the "
                "canonical agent set.)",
                file=sys.stderr,
            )
        else:
            print(
                f"  no workspace-* directories found under {openclaw_home}.",
                file=sys.stderr,
            )
        return 3

    skills_root = workspace / "skills"
    for skill_name, source in WORKSPACE_KODER_SKILLS.items():
        ensure_symlink(skills_root / skill_name, source, dry_run=dry_run)

    if not dry_run:
        print()
        print(f"koder_overlay_ok: agent={agent} workspace={workspace}")
        print()
        print("next_steps:")
        print("  Finalize the koder workspace with the managed scaffolding:")
        print(f'     python3 "{CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/init_koder.py" \\')
        print(f'       --workspace "{workspace}" --project <project>')

    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        # argparse exits with 2 on missing required args. Surface the memory
        # query protocol hint so the user knows where the agent list comes
        # from — but only when --agent was the cause (which argparse reports
        # via a message on stderr that we cannot inspect directly here; we
        # unconditionally print the hint on exit code 2).
        if exc.code == 2:
            print(file=sys.stderr)
            print(MEMORY_PROTOCOL_HINT, file=sys.stderr)
        raise

    openclaw_home = Path(args.openclaw_home).expanduser()

    if not CLAWSEAT_ROOT.exists():
        raise RuntimeError(f"CLAWSEAT_ROOT not found: {CLAWSEAT_ROOT}")

    return install_overlay(openclaw_home, args.agent, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
