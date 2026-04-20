"""Tests for shells/openclaw-plugin/_bridge_binding.py."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

# Make the plugin module importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shells" / "openclaw-plugin"))

import pytest

import _bridge_binding as bb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_projects_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect _projects_root to a temp directory for every test."""
    monkeypatch.setattr(bb, "_projects_root", lambda: tmp_path)


@pytest.fixture(autouse=True)
def _patch_binding_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a local RLock so tests don't need the real openclaw_bridge module."""
    lock = threading.RLock()
    monkeypatch.setattr(bb, "_get_binding_lock", lambda: lock)


def _bind(project: str = "demo", group_id: str = "g-1", **kwargs) -> dict:
    """Shortcut to bind with sensible defaults."""
    defaults = dict(
        account_id="acc-1",
        session_key="sk-1",
        bound_by="tester",
        authorized=True,
    )
    defaults.update(kwargs)
    return bb.bind_project_to_group(project, group_id, **defaults)


# ---------------------------------------------------------------------------
# bind_project_to_group
# ---------------------------------------------------------------------------

def test_bind_creates_bridge_file(tmp_path: Path) -> None:
    _bind(project="alpha", group_id="g-100")
    bridge_file = tmp_path / "alpha" / "BRIDGE.toml"
    assert bridge_file.exists()


def test_bind_content_has_expected_fields(tmp_path: Path) -> None:
    result = _bind(project="beta", group_id="g-200", account_id="acc-X", bound_by="admin")
    assert result["project"] == "beta"
    assert result["group_id"] == "g-200"
    assert result["account_id"] == "acc-X"
    assert result["bound_by"] == "admin"
    # bound_at should be a non-empty ISO timestamp string.
    assert result["bound_at"] != ""


def test_bind_without_authorized_raises() -> None:
    with pytest.raises(PermissionError, match="authorized"):
        bb.bind_project_to_group(
            "proj", "g-1", "acc-1", "sk-1", "tester", authorized=False,
        )


def test_bind_overwrites_existing(tmp_path: Path) -> None:
    _bind(project="gamma", group_id="g-300")
    # Re-bind same project to same group with new account.
    result = _bind(project="gamma", group_id="g-300", account_id="acc-NEW")
    assert result["account_id"] == "acc-NEW"
    # Only one BRIDGE.toml should exist.
    assert (tmp_path / "gamma" / "BRIDGE.toml").exists()


# ---------------------------------------------------------------------------
# get_binding_for_group
# ---------------------------------------------------------------------------

def test_get_binding_for_group_found() -> None:
    _bind(project="proj-a", group_id="g-find-me")
    result = bb.get_binding_for_group("g-find-me")
    assert result is not None
    assert result["project"] == "proj-a"
    assert result["group_id"] == "g-find-me"


def test_get_binding_for_group_no_match() -> None:
    _bind(project="proj-b", group_id="g-other")
    assert bb.get_binding_for_group("g-nonexistent") is None


# ---------------------------------------------------------------------------
# unbind_project
# ---------------------------------------------------------------------------

def test_unbind_project_removes_file(tmp_path: Path) -> None:
    _bind(project="removeme", group_id="g-rm")
    bridge_file = tmp_path / "removeme" / "BRIDGE.toml"
    assert bridge_file.exists()

    old = bb.unbind_project("removeme")
    assert old is not None
    assert old["project"] == "removeme"
    assert not bridge_file.exists()


def test_unbind_project_nonexistent() -> None:
    result = bb.unbind_project("never-existed")
    assert result is None


# ---------------------------------------------------------------------------
# list_project_bindings
# ---------------------------------------------------------------------------

def test_list_project_bindings_two_projects() -> None:
    _bind(project="p1", group_id="g-a")
    _bind(project="p2", group_id="g-b")
    bindings = bb.list_project_bindings()
    projects = sorted(b["project"] for b in bindings)
    assert projects == ["p1", "p2"]


def test_list_project_bindings_empty() -> None:
    assert bb.list_project_bindings() == []
