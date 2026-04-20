"""Tests for refresh_workspaces auto-detection without workspace-name hardcoding."""
from __future__ import annotations

import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "skills" / "clawseat-install" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import refresh_workspaces  # noqa: E402


def test_detect_koder_workspace_prefers_cwd_contract(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace-cartooner"
    workspace.mkdir()
    (workspace / "WORKSPACE_CONTRACT.toml").write_text(
        'seat_id = "cartooner"\nproject = "install"\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(workspace)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENCLAW_HOME", raising=False)

    assert refresh_workspaces._detect_koder_workspace() == str(workspace)


def test_detect_koder_workspace_returns_single_contract_candidate(tmp_path, monkeypatch):
    openclaw_home = tmp_path / ".openclaw"
    workspace = openclaw_home / "workspace-cartooner"
    workspace.mkdir(parents=True)
    (workspace / "WORKSPACE_CONTRACT.toml").write_text(
        'seat_id = "cartooner"\nproject = "install"\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("OPENCLAW_HOME", str(openclaw_home))

    assert refresh_workspaces._detect_koder_workspace() == str(workspace)


def test_detect_koder_workspace_prefers_exact_frontstage_seat(tmp_path, monkeypatch):
    openclaw_home = tmp_path / ".openclaw"
    other = openclaw_home / "workspace-cartooner"
    other.mkdir(parents=True)
    (other / "WORKSPACE_CONTRACT.toml").write_text(
        'seat_id = "cartooner"\nproject = "install"\n',
        encoding="utf-8",
    )
    frontstage = openclaw_home / "workspace-frontstage"
    frontstage.mkdir(parents=True)
    (frontstage / "WORKSPACE_CONTRACT.toml").write_text(
        'seat_id = "koder"\nproject = "install"\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("OPENCLAW_HOME", str(openclaw_home))

    assert refresh_workspaces._detect_koder_workspace() == str(frontstage)
