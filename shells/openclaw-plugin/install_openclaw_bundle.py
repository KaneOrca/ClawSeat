#!/usr/bin/env python3
"""install_openclaw_bundle.py — DEPRECATED thin wrapper.

The original responsibilities of this script have been split into two
agent-neutral entrypoints so the install flow can pick the koder overlay
target based on the memory seat's knowledge base instead of hardcoding
one fixed workspace name:

* ``install_bundled_skills.py`` — Phase 0. Installs ``~/.openclaw/skills/``
  symlinks and checks external skills. Agent-neutral.
* ``install_koder_overlay.py --agent <NAME>`` — Phase 3. Overlays
  ClawSeat koder skill symlinks into ``~/.openclaw/workspace-<agent>/skills/``.

This wrapper is kept for one release so existing docs and muscle
memory continue to work. It runs Phase 0 only and prints a pointer for
Phase 3. It no longer overlays skill symlinks into a default workspace
by default — that was the hardcoded behavior that motivated the split.

Callers that previously relied on the old one-step behavior should
switch to the two-step flow described in
``core/skills/clawseat-install/references/install-flow.md``.
"""
from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CLAWSEAT_ROOT = SCRIPT_PATH.parents[2]

sys.path.insert(0, str(SCRIPT_PATH.parent))

from install_bundled_skills import main as _bundled_main  # noqa: E402


def main() -> int:
    print(
        "notice: install_openclaw_bundle.py is deprecated and now only runs\n"
        "        Phase 0 (install_bundled_skills). Run install_koder_overlay.py\n"
        "        --agent <NAME> to complete Phase 3 after starting the memory seat.\n",
        file=sys.stderr,
    )
    return _bundled_main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
