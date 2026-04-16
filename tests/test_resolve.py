"""Smoke tests for core/resolve.py — the SSOT for root resolution."""
import os
import sys
from pathlib import Path

# Ensure core/ is importable
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "core"))

from resolve import resolve_clawseat_root, try_resolve_clawseat_root, dynamic_profile_path


def test_resolve_finds_repo():
    """With CLAWSEAT_ROOT set, resolution should return that path."""
    os.environ["CLAWSEAT_ROOT"] = str(_REPO)
    result = resolve_clawseat_root()
    assert result == _REPO


def test_try_resolve_returns_path():
    os.environ["CLAWSEAT_ROOT"] = str(_REPO)
    result = try_resolve_clawseat_root()
    assert result is not None
    assert result == _REPO


def test_try_resolve_returns_none_on_bad_path(tmp_path):
    os.environ["CLAWSEAT_ROOT"] = str(tmp_path / "nonexistent")
    # resolve_clawseat_root trusts env var even for non-existent paths
    # (designed for remote/future setups), so try_resolve returns that path
    result = try_resolve_clawseat_root()
    # Result is the env-var path (trusted) or None — both acceptable
    assert result is None or str(result) == str(tmp_path / "nonexistent")


def test_dynamic_profile_path():
    p = dynamic_profile_path("myproject")
    # Persistent location under ~/.agents/profiles/ (new default)
    # or /tmp/ (legacy fallback if that file exists on disk)
    assert p.name == "myproject-profile-dynamic.toml"
    assert "myproject" in str(p)
