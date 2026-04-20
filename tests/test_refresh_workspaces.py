"""Tests for core/skills/clawseat-install/scripts/refresh_workspaces.py detection helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from refresh_workspaces import (
    _detect_feishu_group_id,
    _detect_koder_workspace,
    _detect_profile,
    _detect_project_from_contract,
)


# ── _detect_koder_workspace ──────────────────────────────────────────


def test_detect_koder_workspace_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Workspace is returned when WORKSPACE_CONTRACT.toml exists at OPENCLAW_HOME."""
    ws = tmp_path / "workspace-koder"
    ws.mkdir()
    (ws / "WORKSPACE_CONTRACT.toml").write_text('project = "demo"\n')

    monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
    # Point HOME to tmp so Path.home() won't find the real ~/.openclaw
    monkeypatch.setenv("HOME", str(tmp_path))
    # Ensure cwd does not accidentally match
    monkeypatch.chdir(tmp_path)

    result = _detect_koder_workspace()
    assert result == str(ws)


def test_detect_koder_workspace_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Returns None when no contract file exists anywhere."""
    # Point OPENCLAW_HOME to an empty dir; home fallback also won't match
    monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    result = _detect_koder_workspace()
    assert result is None


# ── _detect_project_from_contract ────────────────────────────────────


def test_detect_project_from_contract_extracts_name(tmp_path: Path):
    """Project name is correctly read from WORKSPACE_CONTRACT.toml."""
    contract = tmp_path / "WORKSPACE_CONTRACT.toml"
    contract.write_text('project = "test-project"\n')

    result = _detect_project_from_contract(str(tmp_path))
    assert result == "test-project"


def test_detect_project_from_contract_none_when_ws_is_none():
    """Returns None immediately when koder_ws is None."""
    result = _detect_project_from_contract(None)
    assert result is None


# ── _detect_feishu_group_id ──────────────────────────────────────────


def test_detect_feishu_group_id_extracts_id(tmp_path: Path):
    """Feishu group ID is correctly read from the contract."""
    contract = tmp_path / "WORKSPACE_CONTRACT.toml"
    contract.write_text('project = "demo"\nfeishu_group_id = "oc_abc123"\n')

    result = _detect_feishu_group_id(str(tmp_path))
    assert result == "oc_abc123"


def test_detect_feishu_group_id_empty_when_missing(tmp_path: Path):
    """Returns empty string when feishu_group_id is not in the contract."""
    contract = tmp_path / "WORKSPACE_CONTRACT.toml"
    contract.write_text('project = "demo"\n')

    result = _detect_feishu_group_id(str(tmp_path))
    assert result == ""


# ── _detect_profile ──────────────────────────────────────────────────


def test_detect_profile_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Returns the profile path when the file exists."""
    profile = tmp_path / "myapp-profile-dynamic.toml"
    profile.write_text('version = 1\n')

    monkeypatch.setattr(
        "refresh_workspaces.dynamic_profile_path",
        lambda project: profile,
    )

    result = _detect_profile("myapp")
    assert result == str(profile)


def test_detect_profile_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Returns None when neither primary nor legacy profile exists."""
    missing = tmp_path / "nonexistent-profile-dynamic.toml"

    monkeypatch.setattr(
        "refresh_workspaces.dynamic_profile_path",
        lambda project: missing,
    )

    result = _detect_profile("nonexistent")
    assert result is None
