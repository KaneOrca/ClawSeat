"""Tests for T18 D2: install_complete.py G1-G15 validator."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import install_complete as ic


# ── helpers ───────────────────────────────────────────────────────────────────

def _setup_full_state(root: Path, project: str = "testproj") -> None:
    """Build a fake install state satisfying all critical G checks."""
    # G1: bundled skills
    skills_dir = root / ".openclaw" / "skills"
    skills_dir.mkdir(parents=True)
    for name in ["clawseat", "clawseat-install", "gstack-harness", "memory-oracle"]:
        (skills_dir / name).mkdir()

    # G2: memory index.json
    mem_dir = root / ".agents" / "memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "index.json").write_text(json.dumps({"scanned_at": "2026-04-20"}))

    # G6/G8: BRIDGE.toml
    bridge_dir = root / ".agents" / "projects" / project
    bridge_dir.mkdir(parents=True)
    (bridge_dir / "BRIDGE.toml").write_text('bound_by = "test-user"\ngroup_id = "oc_test"\n')

    # G11: .last_refresh in project dir
    (bridge_dir / ".last_refresh").write_text("2026-04-20T00:00:00Z")


def _patch_home(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(ic, "_AGENTS_HOME", root / ".agents")
    monkeypatch.setattr(ic, "_OPENCLAW_HOME", root / ".openclaw")


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: all critical Gs present → PASS (exit 0)
# ══════════════════════════════════════════════════════════════════════════════

def test_full_install_state_passes(tmp_path, monkeypatch):
    _setup_full_state(tmp_path, "testproj")
    _patch_home(monkeypatch, tmp_path)

    # Mock lark-cli to return im:message.group_msg:receive
    with patch("subprocess.run") as mock_run:
        import subprocess
        mock_run.return_value = subprocess.CompletedProcess(
            args=["lark-cli"], returncode=0,
            stdout="im:message.group_msg:receive\nim:message\n", stderr=""
        )
        rc = ic.main(["--project", "testproj"])

    assert rc == 0


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: no bundled skills → G1 FAIL → exit non-zero
# ══════════════════════════════════════════════════════════════════════════════

def test_missing_bundled_skills_fails_g1(tmp_path, monkeypatch):
    _setup_full_state(tmp_path, "testproj")
    _patch_home(monkeypatch, tmp_path)
    # Remove skills dir to trigger G1 failure
    import shutil
    shutil.rmtree(tmp_path / ".openclaw" / "skills")

    with patch("subprocess.run") as mock_run:
        import subprocess
        mock_run.return_value = subprocess.CompletedProcess(
            args=["lark-cli"], returncode=0,
            stdout="im:message.group_msg:receive\n", stderr=""
        )
        rc = ic.main(["--project", "testproj"])

    assert rc != 0


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: no refresh marker → G11 FAIL → exit non-zero
# ══════════════════════════════════════════════════════════════════════════════

def test_missing_refresh_marker_fails_g11(tmp_path, monkeypatch):
    _setup_full_state(tmp_path, "testproj")
    _patch_home(monkeypatch, tmp_path)
    # Remove .last_refresh
    (tmp_path / ".agents" / "projects" / "testproj" / ".last_refresh").unlink()

    with patch("subprocess.run") as mock_run:
        import subprocess
        mock_run.return_value = subprocess.CompletedProcess(
            args=["lark-cli"], returncode=0,
            stdout="im:message.group_msg:receive\n", stderr=""
        )
        rc = ic.main(["--project", "testproj"])

    assert rc != 0


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: smoke — real-env --project install (read-only, no strict assert on exit)
# ══════════════════════════════════════════════════════════════════════════════

def test_smoke_real_env_install(capsys):
    """Smoke: --project install runs without crashing; output contains check IDs."""
    try:
        rc = ic.main(["--project", "install"])
    except SystemExit as exc:
        rc = exc.code
    out = capsys.readouterr().out
    assert "G1" in out
    assert "G6" in out
    assert "RESULT:" in out
