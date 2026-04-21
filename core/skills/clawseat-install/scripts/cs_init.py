#!/usr/bin/env python3
"""cs_init.py — v0.4 convenience resumer for the canonical `install` project.

Historically this script bootstrapped install from a v1 profile template,
writing memory/koder/planner/builder-1/reviewer-1 as tmux seats and
explicitly starting koder before planner.

Under v0.4 (docs/schemas/v0.4-layered-model.md) the ancestor seat owns
project lifecycle (see docs/design/ancestor-responsibilities.md). `/cs`
is now a thin resumer that only:

  1. verifies the project has a v2 profile (refuses v1 + missing),
  2. ensures the ancestor tmux session is alive, launching it via
     core/launchers/agent-launcher.sh --headless if not,
  3. exits — ancestor itself does Phase-A (memory check, seat spawn,
     Feishu binding) and Phase-B (patrol).

It does NOT:
  - write any profile (v1 or v2),
  - start koder / memory as tmux seats (v0.4 forbids both),
  - start planner directly (ancestor does this in Phase-A B4).

Fresh-install operators should use `install_entrypoint.py` instead.
See core/skills/cs/SKILL.md for the full flow.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    import tomllib  # type: ignore[attr-defined]
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "core"))
from lib.real_home import real_user_home  # noqa: E402
from resolve import dynamic_profile_path  # noqa: E402

PROJECT = "install"
DYNAMIC_PROFILE = dynamic_profile_path(PROJECT)
ANCESTOR_SESSION = f"{PROJECT}-ancestor-claude"
LAUNCHER = REPO_ROOT / "core" / "launchers" / "agent-launcher.sh"


def _refuse(reason: str, hint: str) -> "None":
    sys.stderr.write(
        f"cs_init refuses to resume: {reason}.\n\n"
        f"cs_init is the v0.4 resumer for an EXISTING install project.\n"
        f"It never writes profiles or spawns koder/memory as tmux seats.\n\n"
        f"{hint}\n"
    )
    raise SystemExit(2)


def _require_v2_profile() -> Path:
    if not DYNAMIC_PROFILE.exists():
        _refuse(
            f"no profile at {DYNAMIC_PROFILE}",
            "Fresh install → run:\n"
            "  python3 -m core.tui.install_entrypoint --project install",
        )
    try:
        parsed = tomllib.loads(DYNAMIC_PROFILE.read_text(encoding="utf-8"))
    except Exception as exc:
        _refuse(
            f"profile at {DYNAMIC_PROFILE} is unparseable ({exc})",
            "Repair the TOML manually or re-generate via install_entrypoint.py.",
        )
    if int(parsed.get("version", 0)) < 2:
        _refuse(
            f"profile at {DYNAMIC_PROFILE} is v{parsed.get('version')!r}, not v2",
            "Migrate with:\n"
            "  python3 core/scripts/migrate_profile_to_v2.py apply --project install",
        )
    return DYNAMIC_PROFILE


def _tmux_has_session(name: str) -> bool:
    r = subprocess.run(
        ["tmux", "has-session", "-t", f"={name}"],
        capture_output=True, text=True, check=False,
    )
    return r.returncode == 0


def _launch_ancestor(profile: Path) -> None:
    # Read ancestor's auth_mode from profile so we spawn with the right secret.
    parsed = tomllib.loads(profile.read_text(encoding="utf-8"))
    overrides = parsed.get("seat_overrides", {}).get("ancestor", {})
    tool = overrides.get("tool", "claude")
    auth = overrides.get("auth_mode", "oauth_token")
    if not LAUNCHER.is_file():
        _refuse(
            f"launcher missing at {LAUNCHER}",
            "clawseat install looks incomplete — re-install the launchers module.",
        )
    cmd = [
        str(LAUNCHER),
        "--tool", tool, "--auth", auth,
        "--session", ANCESTOR_SESSION,
        "--dir", str(REPO_ROOT),
        "--headless",
    ]
    print(f"launching ancestor: {' '.join(cmd)}")
    r = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        env={**os.environ, "CLAWSEAT_ROOT": str(REPO_ROOT)},
        text=True, capture_output=True, check=False,
    )
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != 0:
        sys.stderr.write(r.stderr or "")
        raise SystemExit(r.returncode)


def main() -> int:
    argparse.ArgumentParser(
        description="v0.4 resumer for the canonical install project",
    ).parse_args()

    profile = _require_v2_profile()
    print(f"profile_ok: {profile} (v2)")

    if _tmux_has_session(ANCESTOR_SESSION):
        print(f"ancestor_state: already_alive ({ANCESTOR_SESSION})")
        return 0

    print(f"ancestor_state: absent — launching {ANCESTOR_SESSION}")
    _launch_ancestor(profile)

    if _tmux_has_session(ANCESTOR_SESSION):
        print(f"ancestor_state: now_alive ({ANCESTOR_SESSION})")
        print("\nancestor will run Phase-A checklist: memory verify, seat spawn, "
              "Feishu binding, smoke dispatch — then enter Phase-B patrol.\n"
              f"Monitor via: python3 core/scripts/iterm_panes_driver.py")
        return 0

    sys.stderr.write(
        f"ancestor_state: still_absent after launch — check launcher logs. "
        f"Session name expected: {ANCESTOR_SESSION}\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
