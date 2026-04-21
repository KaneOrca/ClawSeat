"""Profile guard regression tests for R1 fix: install-with-memory.toml tmux mode
vs install-openclaw.toml overlay mode.

Background: install-with-memory.toml was wrongly using heartbeat_transport="openclaw"
with koder absent from runtime_seats; R1 flipped it to tmux transport + koder in
runtime_seats. A regression there would re-break /cs init.

This test file locks in the two profile invariants that guard the R1 fix:
1. install-with-memory.toml is pure tmux mode (koder is a tmux seat)
2. install-openclaw.toml is pure overlay mode (koder is NOT a tmux seat)
3. The two profiles are mutually exclusive in transport + runtime_seats
4. Any profile with heartbeat_transport="openclaw" + koder in runtime_seats is invalid
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def _load_profile(profile_path: Path):
    """Load a HarnessProfile from a TOML path, using the live dynamic_common."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "dynamic_common", _REPO / "core" / "migration" / "dynamic_common.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dynamic_common"] = mod
    spec.loader.exec_module(mod)
    return mod.load_profile(profile_path)


# Canonical profile paths
_INSTALL_WITH_MEMORY = _REPO / "examples" / "starter" / "profiles" / "legacy" / "install-with-memory.toml"
_INSTALL_OPENCLAW = _REPO / "examples" / "starter" / "profiles" / "legacy" / "install-openclaw.toml"


# ── install-with-memory.toml — pure tmux mode ─────────────────────────────────


def test_install_with_memory_heartbeat_transport_is_tmux():
    """install-with-memory is the local /cs starter profile; koder runs as a tmux seat."""
    profile = _load_profile(_INSTALL_WITH_MEMORY)
    assert profile.heartbeat_transport == "tmux", (
        f"install-with-memory must use heartbeat_transport='tmux' for /cs local mode, "
        f"got {profile.heartbeat_transport!r}"
    )


def test_install_with_memory_koder_in_runtime_seats():
    """koder is a declared runtime seat in tmux mode — it gets started by start_seat."""
    profile = _load_profile(_INSTALL_WITH_MEMORY)
    assert "koder" in profile.runtime_seats, (
        f"koder must be in runtime_seats for tmux mode, got {profile.runtime_seats!r}"
    )


def test_install_with_memory_heartbeat_owner_is_koder():
    profile = _load_profile(_INSTALL_WITH_MEMORY)
    assert profile.heartbeat_owner == "koder"


def test_install_with_memory_koder_runs_in_tmux():
    """koder is a tmux seat in install-with-memory profile."""
    profile = _load_profile(_INSTALL_WITH_MEMORY)
    # koder runs in tmux when heartbeat_transport=="tmux"
    assert profile.heartbeat_transport == "tmux"
    assert "koder" in profile.runtime_seats
    # seat_runs_in_tmux: koder != heartbeat_owner so check is runtime_seats
    assert profile.seat_runs_in_tmux("koder"), (
        f"koder must seat_runs_in_tmux=True in tmux mode profile"
    )


# ── install-openclaw.toml — overlay mode ───────────────────────────────────────


def test_install_openclaw_heartbeat_transport_is_openclaw():
    """install-openclaw is the overlay profile; koder is owned by OpenClaw frontstage."""
    profile = _load_profile(_INSTALL_OPENCLAW)
    assert profile.heartbeat_transport == "openclaw", (
        f"install-openclaw must use heartbeat_transport='openclaw', got {profile.heartbeat_transport!r}"
    )


def test_install_openclaw_koder_not_in_runtime_seats():
    """koder is NOT a runtime seat in overlay mode — OpenClaw owns it."""
    profile = _load_profile(_INSTALL_OPENCLAW)
    assert "koder" not in profile.runtime_seats, (
        f"koder must NOT be in runtime_seats for openclaw overlay mode, "
        f"got {profile.runtime_seats!r}. "
        f"R1 fixed this: koder is the overlay target, not a tmux seat."
    )


def test_install_openclaw_heartbeat_owner_is_koder():
    """koder is still the heartbeat owner even in overlay mode."""
    profile = _load_profile(_INSTALL_OPENCLAW)
    assert profile.heartbeat_owner == "koder"


def test_install_openclaw_koder_does_not_run_in_tmux():
    """koder is NOT a tmux seat in openclaw overlay mode."""
    profile = _load_profile(_INSTALL_OPENCLAW)
    assert profile.heartbeat_transport == "openclaw"
    assert "koder" not in profile.runtime_seats
    # seat_runs_in_tmux: koder IS the heartbeat_owner and transport is openclaw → False
    assert not profile.seat_runs_in_tmux("koder"), (
        f"koder must seat_runs_in_tmux=False in openclaw mode profile"
    )


# ── Mutual exclusion invariants ────────────────────────────────────────────────


def test_install_profiles_have_opposite_transports():
    """The two canonical profiles must have opposite heartbeat_transport values."""
    mem_profile = _load_profile(_INSTALL_WITH_MEMORY)
    oc_profile = _load_profile(_INSTALL_OPENCLAW)
    assert mem_profile.heartbeat_transport != oc_profile.heartbeat_transport, (
        f"install-with-memory and install-openclaw must have opposite transports, "
        f"got memory={mem_profile.heartbeat_transport!r}, openclaw={oc_profile.heartbeat_transport!r}"
    )


def test_install_profiles_have_opposite_koder_runtime_seat_membership():
    """koder is in runtime_seats for tmux mode, excluded for openclaw mode."""
    mem_profile = _load_profile(_INSTALL_WITH_MEMORY)
    oc_profile = _load_profile(_INSTALL_OPENCLAW)
    koder_in_memory = "koder" in mem_profile.runtime_seats
    koder_in_oc = "koder" in oc_profile.runtime_seats
    assert koder_in_memory != koder_in_oc, (
        f"koder runtime_seats membership must differ between profiles: "
        f"memory={koder_in_memory}, openclaw={koder_in_oc}"
    )


# ── Guard: openclaw + koder-in-runtime is an invalid combination ────────────────


def test_openclaw_profile_koder_not_in_runtime_is_valid():
    """The openclaw profile is the valid configuration (koder excluded, not a tmux seat)."""
    profile = _load_profile(_INSTALL_OPENCLAW)
    # This should be valid — no exception
    assert profile.heartbeat_transport == "openclaw"
    assert "koder" not in profile.runtime_seats


def test_tmux_profile_koder_in_runtime_is_valid():
    """The tmux profile is the valid configuration (koder included as tmux seat)."""
    profile = _load_profile(_INSTALL_WITH_MEMORY)
    # This should be valid — no exception
    assert profile.heartbeat_transport == "tmux"
    assert "koder" in profile.runtime_seats
