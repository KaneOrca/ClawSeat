"""tests/test_v05_smoke.py — pytest wrapper for the v0.5 smoke harness."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO / "tests" / "smoke" / "test_v05_install.sh"


def test_v05_install_smoke():
    """Run the shell smoke harness and assert all checks pass."""
    result = subprocess.run(
        ["bash", str(SMOKE_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO),
    )
    # Print output for visibility even on failure.
    if result.stdout:
        print(result.stdout, file=sys.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    assert result.returncode == 0, (
        f"v0.5 smoke harness failed (exit {result.returncode}).\n"
        f"See output above for PASS/FAIL lines."
    )
