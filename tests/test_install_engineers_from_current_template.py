from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]


def test_engineers_from_template_uses_creative_patrol_not_qa(tmp_path: Path) -> None:
    home = tmp_path / "home"
    probe = f"""
set -euo pipefail
source "{_REPO / 'scripts' / 'install.sh'}" >/dev/null
_engineers_from_template "{_REPO / 'templates' / 'clawseat-creative.toml'}"
"""
    result = subprocess.run(
        ["bash", "-c", probe],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "CLAWSEAT_REAL_HOME": str(home),
            "PYTHON_BIN": sys.executable,
        },
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "memory planner builder patrol designer"
    assert "qa" not in result.stdout.split()
