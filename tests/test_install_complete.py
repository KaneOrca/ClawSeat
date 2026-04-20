"""Tests for T18 D2: install_complete.py G1-G15 validator."""
from __future__ import annotations

import json
import subprocess
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
    # G1: shared bundled skills dir (referenced by per-agent symlink below)
    skills_dir = root / ".openclaw" / "skills"
    skills_dir.mkdir(parents=True)
    for name in ["clawseat", "clawseat-install", "gstack-harness", "memory-oracle"]:
        (skills_dir / name).mkdir()

    # G1 (per-agent): workspace-koder/skills → symlink to shared ../skills/
    # Removing the shared skills dir breaks this symlink → G1 FAIL (used by test 2)
    ws_koder = root / ".openclaw" / "workspace-koder"
    ws_koder.mkdir(parents=True)
    (ws_koder / "skills").symlink_to("../skills")

    # G2: memory index.json
    mem_dir = root / ".agents" / "memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "index.json").write_text(json.dumps({"scanned_at": "2026-04-20"}))

    # G6/G8: BRIDGE.toml with agent field so auto-resolve works
    bridge_dir = root / ".agents" / "projects" / project
    bridge_dir.mkdir(parents=True)
    (bridge_dir / "BRIDGE.toml").write_text(
        'agent = "koder"\nbound_by = "test-user"\ngroup_id = "oc_test"\n'
    )

    # G11: .last_refresh fallback (projects/<project>/.last_refresh)
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
    # Remove skills dir to trigger G1 failure (workspace-koder/skills symlink breaks)
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


# ══════════════════════════════════════════════════════════════════════════════
# Test 5 (F1 fixture): install-canonical fixture → PASS
# ══════════════════════════════════════════════════════════════════════════════

def test_install_complete_install_passes_with_fixture(tmp_path):
    """Group A canonical fixture: install project with all critical checks met."""
    oc = tmp_path / ".openclaw"
    ag = tmp_path / ".agents"

    # G1: workspace-koder/skills with ≥4 entries
    ws_koder = oc / "workspace-koder"
    skills_dir = ws_koder / "skills"
    skills_dir.mkdir(parents=True)
    for name in ["clawseat", "clawseat-install", "gstack-harness", "memory-oracle"]:
        (skills_dir / name).mkdir()

    # G2: memory index.json
    (ag / "memory").mkdir(parents=True)
    (ag / "memory" / "index.json").write_text(json.dumps({"scanned_at": "2026-04-20"}))

    # G6/G8: BRIDGE.toml
    proj_dir = ag / "projects" / "install"
    proj_dir.mkdir(parents=True)
    (proj_dir / "BRIDGE.toml").write_text('bound_by = "test-user"\ngroup_id = "oc_test"\n')

    # G11: koder seat .last_refresh
    koder_ws = ag / "workspaces" / "install" / "koder"
    koder_ws.mkdir(parents=True)
    (koder_ws / ".last_refresh").write_text("2026-04-20T00:00:00Z")

    with patch("subprocess.run") as mock_run:
        import subprocess
        mock_run.return_value = subprocess.CompletedProcess(
            args=["lark-cli"], returncode=0,
            stdout="im:message.group_msg:receive\n", stderr=""
        )
        rc = ic.run_checks("install", koder_agent="koder", agents_home=ag, openclaw_home=oc)

    results = {c["id"]: c for c in rc}
    assert results["G1"]["passed"], "G1 should pass: workspace-koder/skills/ has ≥4 entries"
    assert results["G2"]["passed"], "G2 should pass: memory index.json present"
    assert results["G6"]["passed"], "G6 should pass: BRIDGE.toml present"
    assert results["G11"]["passed"], "G11 should pass: .last_refresh present"

    failures = [c["id"] for c in rc if c["level"] == "FAIL" and c["id"] in ic.CRITICAL]
    assert failures == [], f"Unexpected critical failures: {failures}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 6 (F1 regression canary): hardening-b gap fixture → G1+G11 FAIL
# ══════════════════════════════════════════════════════════════════════════════

def test_install_complete_hardening_b_fails_with_missing_g1_g4_g11(tmp_path, capsys):
    """F1 canary: Group B gap fixture — workspace-mor exists but lacks skills/+refresh."""
    oc = tmp_path / ".openclaw"
    ag = tmp_path / ".agents"

    # G1 gap: workspace-mor exists but NO skills/ dir
    (oc / "workspace-mor").mkdir(parents=True)

    # G4 gap: no .entry_skills_installed (warn-only, but gap is present)

    # G2: memory index.json present (so G2 passes)
    (ag / "memory").mkdir(parents=True)
    (ag / "memory" / "index.json").write_text(json.dumps({"scanned_at": "2026-04-20"}))

    # G6/G8: BRIDGE.toml present (so G6/G8 pass)
    proj_dir = ag / "projects" / "hardening-b"
    proj_dir.mkdir(parents=True)
    (proj_dir / "BRIDGE.toml").write_text('bound_by = "test-user"\ngroup_id = "oc_test"\n')

    # G11 gap: no .last_refresh and no WORKSPACE_CONTRACT anywhere

    with patch("subprocess.run") as mock_run:
        import subprocess
        mock_run.return_value = subprocess.CompletedProcess(
            args=["lark-cli"], returncode=0,
            stdout="im:message.group_msg:receive\n", stderr=""
        )
        checks = ic.run_checks(
            "hardening-b", koder_agent="mor", agents_home=ag, openclaw_home=oc
        )

    results = {c["id"]: c for c in checks}
    out = "\n".join(
        f"[{c['level']}] {c['id']} {c['desc']}" for c in checks
    )

    assert not results["G1"]["passed"], "G1 must FAIL: workspace-mor/skills/ missing"
    assert not results["G11"]["passed"], "G11 must FAIL: no refresh marker"
    assert results["G1"]["level"] == "FAIL"
    assert results["G11"]["level"] == "FAIL"

    failures = [c["id"] for c in checks if c["level"] == "FAIL" and c["id"] in ic.CRITICAL]
    assert "G1" in failures, f"G1 must be in critical failures; got: {failures}"
    assert "G11" in failures, f"G11 must be in critical failures; got: {failures}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 7 (T17): --with-feishu-smoke flag — install with receipt passes
# ══════════════════════════════════════════════════════════════════════════════

def test_with_feishu_smoke_install_receipt_passes(tmp_path):
    """With smoke receipt present, G_SMOKE_RECEIPT must PASS."""
    oc = tmp_path / ".openclaw"
    ag = tmp_path / ".agents"

    # Minimal G1/G2/G6/G11 setup for install (auto-resolves to koder)
    ws_koder = oc / "workspace-koder"
    (ws_koder / "skills").mkdir(parents=True)
    for name in ["clawseat", "clawseat-install", "gstack-harness", "memory-oracle"]:
        (ws_koder / "skills" / name).mkdir()
    (ag / "memory").mkdir(parents=True)
    (ag / "memory" / "index.json").write_text(json.dumps({"scanned_at": "2026-04-20"}))
    proj_dir = ag / "projects" / "install"
    proj_dir.mkdir(parents=True)
    (proj_dir / "BRIDGE.toml").write_text('bound_by = "test-user"\ngroup_id = "oc_test"\n')
    koder_ws = ag / "workspaces" / "install" / "koder"
    koder_ws.mkdir(parents=True)
    (koder_ws / ".last_refresh").write_text("2026-04-20T00:00:00Z")

    # Phase 5: create smoke receipt
    handoffs = ag / "tasks" / "install" / "patrol" / "handoffs"
    handoffs.mkdir(parents=True)
    (handoffs / "feishu-bridge-smoke-001__planner__koder.json").write_text('{"status":"done"}')

    # Mock both subprocess.run calls (lark-cli for G14 + send_delegation_report for G_SMOKE_AUTH)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='{"status": "ok", "identity": "user"}\n', stderr=""
        )
        checks = ic.run_checks(
            "install", koder_agent="koder", agents_home=ag, openclaw_home=oc,
            with_feishu_smoke=True,
        )

    results = {c["id"]: c for c in checks}
    assert "G_SMOKE_RECEIPT" in results, "G_SMOKE_RECEIPT check must be present when --with-feishu-smoke"
    assert results["G_SMOKE_RECEIPT"]["passed"], "G_SMOKE_RECEIPT must pass when receipt file exists"


# ══════════════════════════════════════════════════════════════════════════════
# Test 8 (T17): --with-feishu-smoke flag — hardening-b without receipt fails
# ══════════════════════════════════════════════════════════════════════════════

def test_with_feishu_smoke_hardening_b_no_receipt_fails(tmp_path):
    """Without smoke receipt, G_SMOKE_RECEIPT must FAIL for hardening-b."""
    oc = tmp_path / ".openclaw"
    ag = tmp_path / ".agents"

    # workspace-mor exists but no smoke receipt at all
    (oc / "workspace-mor").mkdir(parents=True)
    (ag / "memory").mkdir(parents=True)
    (ag / "memory" / "index.json").write_text(json.dumps({"scanned_at": "2026-04-20"}))
    proj_dir = ag / "projects" / "hardening-b"
    proj_dir.mkdir(parents=True)
    (proj_dir / "BRIDGE.toml").write_text('bound_by = "test-user"\ngroup_id = "oc_test"\n')
    # No handoffs dir → no receipt

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='{"status": "ok"}\n', stderr=""
        )
        checks = ic.run_checks(
            "hardening-b", koder_agent="mor", agents_home=ag, openclaw_home=oc,
            with_feishu_smoke=True,
        )

    results = {c["id"]: c for c in checks}
    assert "G_SMOKE_RECEIPT" in results
    assert not results["G_SMOKE_RECEIPT"]["passed"], "G_SMOKE_RECEIPT must FAIL when no receipt"
    assert results["G_SMOKE_RECEIPT"]["level"] == "FAIL"
