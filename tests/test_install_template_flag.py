"""Tests for install.sh --template flag.

Verifies:
1. --template clawseat-creative is accepted; CLAWSEAT_TEMPLATE_NAME propagated
2. --template bad dies with exit 2
3. Omitting --template keeps clawseat-default behaviour
4. BOOTSTRAP_TEMPLATE_PATH follows --template (patch for fd7cd74 bug)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_INSTALL = _REPO / "scripts" / "install.sh"


def _run(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "PYTHON_BIN": sys.executable,
        "CLAWSEAT_REAL_HOME": str(tmp_path / "home"),
    }
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["bash", str(_INSTALL)] + args,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_template_creative_accepted(tmp_path: Path) -> None:
    """--template clawseat-creative exits 0 in dry-run."""
    result = _run(["--project", "testproj", "--template", "clawseat-creative", "--dry-run"], tmp_path)
    assert result.returncode == 0, result.stderr
    # The template name must appear in the dry-run output (written to project-local.toml)
    assert "clawseat-creative" in result.stdout, f"expected template name in output:\n{result.stdout}"


def test_template_engineering_accepted(tmp_path: Path) -> None:
    """--template clawseat-engineering exits 0 in dry-run."""
    result = _run(["--project", "testproj", "--template", "clawseat-engineering", "--dry-run"], tmp_path)
    assert result.returncode == 0, result.stderr


def test_template_invalid_dies_exit_2(tmp_path: Path) -> None:
    """--template bad_value exits 2 with INVALID_TEMPLATE error code."""
    result = _run(["--project", "testproj", "--template", "bad_value", "--dry-run"], tmp_path)
    assert result.returncode == 2, f"expected exit 2, got {result.returncode}: {result.stderr}"
    assert "INVALID_TEMPLATE" in result.stderr or "template" in result.stderr.lower()


def test_template_default_when_omitted(tmp_path: Path) -> None:
    """Omitting --template keeps clawseat-default behaviour (backwards compat)."""
    result = _run(["--project", "testproj", "--dry-run"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "clawseat-default" in result.stdout, f"expected default template in output:\n{result.stdout}"


def test_bootstrap_template_path_follows_template_flag(tmp_path: Path) -> None:
    """BOOTSTRAP_TEMPLATE_PATH must use the --template value, not the hardcoded default.

    Regression for fd7cd74: BOOTSTRAP_TEMPLATE_DIR was computed at global init
    time before parse_args ran, so --template was ignored in the path.
    """
    result = _run(["--project", "pathtest", "--template", "clawseat-creative", "--dry-run"], tmp_path)
    assert result.returncode == 0, result.stderr
    # dry-run output must reference clawseat-creative path, not clawseat-default
    assert "clawseat-creative" in result.stdout, (
        f"Expected 'clawseat-creative' in BOOTSTRAP_TEMPLATE_PATH dry-run output:\n{result.stdout}"
    )
    assert "clawseat-default" not in result.stdout or result.stdout.count("clawseat-creative") > 0
