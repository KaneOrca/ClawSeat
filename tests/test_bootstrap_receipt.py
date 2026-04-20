"""Tests for core/bootstrap_receipt.py — receipt read/write/validation."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.bootstrap_receipt import (
    RECEIPT_VALID_FOR_SECONDS,
    RECEIPT_VERSION,
    _receipt_path,
    _resolve_agents_root,
    is_valid,
    read_receipt,
    write_receipt,
)
from core.preflight import PreflightItem, PreflightResult, PreflightStatus


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def agents_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point _resolve_agents_root to a temp dir."""
    agents = tmp_path / ".agents"
    agents.mkdir()
    monkeypatch.setattr(
        "core.bootstrap_receipt._resolve_agents_root",
        lambda: agents,
    )
    return agents


@pytest.fixture()
def fake_preflight() -> PreflightResult:
    """A synthetic all-passing PreflightResult."""
    items = [
        PreflightItem(name="CLAWSEAT_ROOT", status=PreflightStatus.PASS, message="ok"),
        PreflightItem(name="python3", status=PreflightStatus.PASS, message="ok"),
        PreflightItem(name="tmux", status=PreflightStatus.PASS, message="ok"),
        PreflightItem(name="tmux_server", status=PreflightStatus.PASS, message="ok"),
    ]
    return PreflightResult(
        all_pass=True,
        has_hard_blocked=False,
        has_retryable=False,
        items=items,
        passing_items=items,
    )


@pytest.fixture()
def mock_resolve_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    """Mock _resolve_clawseat_root to return a stable tmp path."""
    root = tmp_path / "ClawSeat"
    root.mkdir()
    monkeypatch.setattr(
        "core.bootstrap_receipt._resolve_clawseat_root",
        lambda: root,
    )
    return root


@pytest.fixture()
def mock_profile_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    """Create a dynamic profile and patch the resolver to find it."""
    profile = tmp_path / "profiles" / "test-profile-dynamic.toml"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# profile", encoding="utf-8")
    monkeypatch.setattr(
        "core.resolve.dynamic_profile_path",
        lambda p: profile,
    )
    return profile


# ── 1. write_receipt creates file with expected fields ───────────────


def test_write_receipt_creates_file(
    agents_tmp: Path,
    fake_preflight: PreflightResult,
    mock_resolve_root: Path,
    mock_profile_exists: Path,
) -> None:
    """write_receipt should create a TOML file containing version and timestamp."""
    path = write_receipt(
        "test",
        fake_preflight,
        python_version="Python 3.12.0",
        tmux_version="tmux 3.4",
    )
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "version" in content
    assert "bootstrapped_at" in content
    assert "test" in content


# ── 2. read_receipt after write → fields match ───────────────────────


def test_read_receipt_round_trip(
    agents_tmp: Path,
    fake_preflight: PreflightResult,
    mock_resolve_root: Path,
    mock_profile_exists: Path,
) -> None:
    """read_receipt should return the same data that write_receipt wrote."""
    write_receipt(
        "test",
        fake_preflight,
        python_version="Python 3.12.0",
        tmux_version="tmux 3.4",
    )
    receipt = read_receipt("test")
    assert receipt is not None
    bootstrap = receipt.get("bootstrap", {})
    assert bootstrap["version"] == RECEIPT_VERSION
    assert bootstrap["project"] == "test"
    assert bootstrap["python_version"] == "Python 3.12.0"
    assert bootstrap["tmux_version"] == "tmux 3.4"


# ── 3. read_receipt nonexistent → returns None ───────────────────────


def test_read_receipt_nonexistent(agents_tmp: Path) -> None:
    """read_receipt for a project with no receipt should return None."""
    result = read_receipt("nonexistent-project")
    assert result is None


# ── 4. is_valid on fresh receipt + tmux running + profile exists ─────


def test_is_valid_fresh_receipt(
    agents_tmp: Path,
    fake_preflight: PreflightResult,
    mock_resolve_root: Path,
    mock_profile_exists: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A just-written receipt with tmux running should be valid."""
    write_receipt(
        "test",
        fake_preflight,
        python_version="Python 3.12.0",
        tmux_version="tmux 3.4",
    )
    receipt = read_receipt("test")
    assert receipt is not None

    # Mock tmux as running
    def _fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="0: 1 windows\n", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tmux")

    valid, reason = is_valid(receipt)
    assert valid is True
    assert reason == "valid"


# ── 5. is_valid with version mismatch ────────────────────────────────


def test_is_valid_version_mismatch(
    agents_tmp: Path,
    fake_preflight: PreflightResult,
    mock_resolve_root: Path,
    mock_profile_exists: Path,
) -> None:
    """A receipt with wrong version should be invalid."""
    write_receipt("test", fake_preflight, python_version="Python 3.12.0")
    receipt = read_receipt("test")
    assert receipt is not None

    # Tamper the version
    receipt["bootstrap"]["version"] = 999

    valid, reason = is_valid(receipt)
    assert valid is False
    assert "version" in reason.lower()


# ── 6. is_valid with root drift ─────────────────────────────────────


def test_is_valid_root_drift(
    agents_tmp: Path,
    fake_preflight: PreflightResult,
    mock_resolve_root: Path,
    mock_profile_exists: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If clawseat_root changed since bootstrap, receipt is invalid."""
    write_receipt("test", fake_preflight, python_version="Python 3.12.0")
    receipt = read_receipt("test")
    assert receipt is not None

    # Simulate root drift — _resolve_clawseat_root returns a different path
    new_root = tmp_path / "ClawSeat-v2"
    new_root.mkdir()
    monkeypatch.setattr(
        "core.bootstrap_receipt._resolve_clawseat_root",
        lambda: new_root,
    )

    valid, reason = is_valid(receipt)
    assert valid is False
    assert "root" in reason.lower() or "clawseat_root" in reason.lower()


# ── 7. is_valid with expired receipt ─────────────────────────────────


def test_is_valid_expired(
    agents_tmp: Path,
    fake_preflight: PreflightResult,
    mock_resolve_root: Path,
    mock_profile_exists: Path,
) -> None:
    """A receipt older than 24h should be invalid."""
    write_receipt("test", fake_preflight, python_version="Python 3.12.0")
    receipt = read_receipt("test")
    assert receipt is not None

    # Backdate the timestamp by > 24h
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    receipt["bootstrap"]["bootstrapped_at"] = old_time.isoformat()

    valid, reason = is_valid(receipt)
    assert valid is False
    assert "expired" in reason.lower() or "stale" in reason.lower()


# ── 8. is_valid with tmux not running ────────────────────────────────


def test_is_valid_tmux_not_running(
    agents_tmp: Path,
    fake_preflight: PreflightResult,
    mock_resolve_root: Path,
    mock_profile_exists: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If tmux server is down, receipt is stale."""
    write_receipt("test", fake_preflight, python_version="Python 3.12.0")
    receipt = read_receipt("test")
    assert receipt is not None

    # tmux is installed but list-sessions fails
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tmux")

    def _fail_run(cmd, **kw):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr("subprocess.run", _fail_run)

    valid, reason = is_valid(receipt)
    assert valid is False
    assert "tmux" in reason.lower()


# ── 9. is_valid with profile deleted ─────────────────────────────────


def test_is_valid_profile_deleted(
    agents_tmp: Path,
    fake_preflight: PreflightResult,
    mock_resolve_root: Path,
    mock_profile_exists: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the dynamic profile was deleted after bootstrap, receipt is stale."""
    write_receipt("test", fake_preflight, python_version="Python 3.12.0")
    receipt = read_receipt("test")
    assert receipt is not None

    # tmux is running (pass that check)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tmux")

    def _ok_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="0: 1 windows", stderr="")

    monkeypatch.setattr("subprocess.run", _ok_run)

    # Now point profile resolver to a non-existent file
    missing = Path("/tmp/definitely-not-here-profile-dynamic.toml")
    monkeypatch.setattr(
        "core.resolve.dynamic_profile_path",
        lambda p: missing,
    )

    valid, reason = is_valid(receipt)
    assert valid is False
    assert "profile" in reason.lower()


# ── 10. _receipt_path returns correct path under agents root ─────────


def test_receipt_path_structure(agents_tmp: Path) -> None:
    """_receipt_path should return .../workspaces/<project>/koder/BOOTSTRAP_RECEIPT.toml."""
    path = _receipt_path("myproject")
    assert path.name == "BOOTSTRAP_RECEIPT.toml"
    assert "workspaces" in path.parts
    assert "myproject" in path.parts
    assert "koder" in path.parts
    # The parent directories should have been created
    assert path.parent.exists()
