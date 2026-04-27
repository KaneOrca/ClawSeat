from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
INSTALL = REPO / "scripts" / "install.sh"


def test_install_help_lists_two_templates_and_provider_deprecation() -> None:
    result = subprocess.run(
        ["bash", str(INSTALL), "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHON_BIN": sys.executable},
        check=False,
    )
    assert result.returncode == 0
    assert "clawseat-creative|clawseat-engineering" in result.stdout
    assert "--all-api-provider" in result.stdout
    assert "--provider now controls the memory seat only" in result.stdout


def test_templates_directory_has_only_creative_and_engineering_rosters() -> None:
    roster_names = sorted(path.name for path in (REPO / "templates").glob("clawseat-*.toml"))
    assert roster_names == ["clawseat-creative.toml", "clawseat-engineering.toml"]
