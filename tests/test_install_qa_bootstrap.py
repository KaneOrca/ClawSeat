from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_INSTALL = _REPO / "scripts" / "install.sh"
_CREATIVE_TEMPLATE = _REPO / "templates" / "clawseat-creative.toml"
_ENGINEERING_TEMPLATE = _REPO / "templates" / "clawseat-engineering.toml"


def _run_dry(tmp_path: Path, *, opt_in: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "CLAWSEAT_REAL_HOME": str(tmp_path / "home"),
        "PYTHON_BIN": sys.executable,
    }
    if opt_in is not None:
        env["CLAWSEAT_QA_PATROL_CRON_OPT_IN"] = opt_in
    return subprocess.run(
        [
            "bash",
            str(_INSTALL),
            "--dry-run",
            "--project",
            "qa-bootstrap",
            "--provider",
            "minimax",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_install_profile_includes_qa() -> None:
    creative = _CREATIVE_TEMPLATE.read_text(encoding="utf-8")
    engineering = _ENGINEERING_TEMPLATE.read_text(encoding="utf-8")

    assert 'id = "qa"' in creative
    assert 'role = "qa"' in creative
    assert 'right_seats = ["builder", "qa", "designer"]' in creative
    assert "monitor_max_panes = 5" in creative
    assert "monitor_max_panes = 6" in engineering


def test_install_sh_invokes_install_qa_hook(tmp_path: Path) -> None:
    result = _run_dry(tmp_path)
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    assert "PENDING_SEATS=(planner builder qa designer)" in combined
    assert "Step 7.6: install qa hook + qa patrol cron" in combined
    assert "engineer create qa qa-bootstrap --no-monitor" in combined
    assert "install_qa_hook.py --workspace" in combined
    assert "/.agents/workspaces/qa-bootstrap/qa" in combined


def test_install_sh_qa_cron_optin_yes(tmp_path: Path) -> None:
    result = _run_dry(tmp_path, opt_in="y")
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    assert "install_qa_patrol_cron.py install" in combined
    assert "QA Patrol Cron installed" in combined


def test_install_sh_qa_cron_optin_no(tmp_path: Path) -> None:
    result = _run_dry(tmp_path, opt_in="n")
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    assert "install_qa_patrol_cron.py install" not in combined
    assert "QA Patrol Cron skipped" in combined
