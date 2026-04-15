#!/usr/bin/env python3
"""
OpenClaw koder bootstrap (production version) — initializes the ClawSeat bridge.

Reads OpenClaw environment configuration, initializes:
1. ClawSeatAdapter (control plane)
2. TmuxCliAdapter (tmux sessions)

And registers the bridge with the openclaw-plugin shell.

Production path: ClawSeat/shells/openclaw-plugin/openclaw_bootstrap.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# OpenClaw may inject environment variables for project configuration.
# Default to the canonical install project rather than a smoke-only placeholder.
OPENCLAW_PROJECT = os.environ.get("OPENCLAW_PROJECT", "install")
OPENCLAW_AGENTS_ROOT = os.environ.get("AGENTS_ROOT", str(Path.home() / ".agents"))
OPENCLAW_SESSIONS_ROOT = os.environ.get("SESSIONS_ROOT", f"{OPENCLAW_AGENTS_ROOT}/sessions")
OPENCLAW_WORKSPACES_ROOT = os.environ.get("WORKSPACES_ROOT", f"{OPENCLAW_AGENTS_ROOT}/workspaces")


def _resolve_clawseat_root(agents_root: Path | None = None) -> Path:
    """Resolve CLAWSEAT_ROOT using the same 4-layer chain as TmuxCliAdapter."""
    configured = os.environ.get("CLAWSEAT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()

    helper_markers = (
        Path("core/scripts/agent_admin.py"),
        Path("core/skills/gstack-harness/scripts/_common.py"),
    )
    script_path = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in script_path.parents:
        candidates.append(parent)
        candidates.append(parent / "ClawSeat")

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if all((candidate / marker).exists() for marker in helper_markers):
            return candidate

    if agents_root is not None:
        agents_root_candidate = agents_root.parent / "coding" / "ClawSeat"
        if all((agents_root_candidate / marker).exists() for marker in helper_markers):
            return agents_root_candidate

    fallback = Path.home() / "coding" / "ClawSeat"
    if all((fallback / marker).exists() for marker in helper_markers):
        return fallback

    fallback = Path.home() / "coding" / "ClawSeat"
    print(
        f"warning: CLAWSEAT_ROOT not set; falling back to {fallback}",
        file=sys.stderr,
    )
    return fallback


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]  # shells/openclaw-plugin/ → shells/ → ClawSeat root
CLAWSEAT_ROOT = _resolve_clawseat_root(Path(OPENCLAW_AGENTS_ROOT))

sys.path.insert(0, str(CLAWSEAT_ROOT))


def main() -> dict[str, str]:
    from shells.openclaw_plugin import openclaw_bridge

    os.environ["CLAWSEAT_ROOT"] = str(CLAWSEAT_ROOT)
    # CLAWSEAT_REFAC_ROOT is inherited from the environment; if unset, _get_migration_root()
    # in clawseat_adapter.py falls back to REPO_ROOT / "refac" / "migration" (production path)

    state = openclaw_bridge.bootstrap(
        project_name=OPENCLAW_PROJECT,
    )

    tmux_adapter = openclaw_bridge.init_tmux_adapter(
        agents_root=OPENCLAW_AGENTS_ROOT,
        sessions_root=OPENCLAW_SESSIONS_ROOT,
        workspaces_root=OPENCLAW_WORKSPACES_ROOT,
    )

    sessions = openclaw_bridge.list_team_sessions(
        OPENCLAW_PROJECT,
        tmux_adapter=tmux_adapter,
    )

    print(f"OpenClaw → ClawSeat bridge initialized", file=sys.stderr)
    print(f"  project: {OPENCLAW_PROJECT}", file=sys.stderr)
    print(f"  profile: {state['profile_path']}", file=sys.stderr)
    print(f"  planner brief: {state['planner_brief_title']!r} ({state['planner_brief_status']})", file=sys.stderr)
    print(f"  tmux_adapter: {state['tmux_adapter']}", file=sys.stderr)
    print(f"  active sessions: {len(sessions)}", file=sys.stderr)
    for s in sessions:
        print(f"    - {s['seat_id']} ({s['tool']}): {s['runtime_id']}", file=sys.stderr)

    # koder IS the OpenClaw agent — it does not need a tmux session.
    # Backend seats (planner, builder, reviewer, etc.) are started later
    # by the koder frontstage skill after the user completes configuration
    # (provider selection, auth setup, API key provisioning).

    return {
        "status": "initialized",
        "project": OPENCLAW_PROJECT,
        "profile": state["profile_path"],
        "planner_brief": state["planner_brief_title"],
        "sessions_count": len(sessions),
        "tmux_adapter": state["tmux_adapter"],
    }


if __name__ == "__main__":
    result = main()
    print(result)
