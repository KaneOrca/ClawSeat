"""Tests for T12: session stop-engineer closes iTerm tab before tmux kill.

Covers:
  1. test_stop_engineer_closes_iterm_tab_when_tty_found
  2. test_stop_engineer_warns_when_iterm_tab_not_found
  3. test_stop_engineer_warns_on_iterm_close_error
  4. test_stop_engineer_keep_iterm_tab_skips_close
  5. test_stop_engineer_no_tty_skips_iterm_close
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import agent_admin_session as aas


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_session(name: str = "test-session") -> SimpleNamespace:
    return SimpleNamespace(session=name)


def _make_service() -> aas.SessionService:
    hooks = MagicMock()
    hooks.tmux_has_session.return_value = True
    return aas.SessionService(hooks)


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: tty found → iTerm tab closed → tmux killed
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_closes_iterm_tab_when_tty_found(capsys):
    svc = _make_service()
    session = _make_session("koder-1")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys001") as mock_tty,
        patch.object(aas, "_close_iterm_tab_by_tty", return_value={"status": "ok", "detail": None}) as mock_close,
        patch.object(svc, "_run_tmux_with_retry") as mock_tmux,
    ):
        svc.stop_engineer(session)

    mock_tty.assert_called_once_with("koder-1")
    mock_close.assert_called_once_with("/dev/ttys001")
    mock_tmux.assert_called_once()
    assert "iterm_tab_closed" in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: iTerm tab not found → warn on stderr, still kill tmux
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_warns_when_iterm_tab_not_found(capsys):
    svc = _make_service()
    session = _make_session("koder-2")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys002"),
        patch.object(aas, "_close_iterm_tab_by_tty", return_value={"status": "not_found", "detail": "no match"}),
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session)

    err = capsys.readouterr().err
    assert "iterm_tab_not_found" in err


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: osascript error → warn on stderr, still kill tmux
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_warns_on_iterm_close_error(capsys):
    svc = _make_service()
    session = _make_session("koder-3")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys003"),
        patch.object(aas, "_close_iterm_tab_by_tty", return_value={"status": "error", "detail": "timeout"}),
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session)

    err = capsys.readouterr().err
    assert "iterm_tab_close_failed" in err
    assert "timeout" in err


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: --keep-iterm-tab → iTerm helpers never called, tmux still killed
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_keep_iterm_tab_skips_close():
    svc = _make_service()
    session = _make_session("koder-4")

    with (
        patch.object(aas, "_get_tmux_tty") as mock_tty,
        patch.object(aas, "_close_iterm_tab_by_tty") as mock_close,
        patch.object(svc, "_run_tmux_with_retry") as mock_tmux,
    ):
        svc.stop_engineer(session, keep_iterm_tab=True)

    mock_tty.assert_not_called()
    mock_close.assert_not_called()
    mock_tmux.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# Test 5: no tty attached → _close_iterm_tab_by_tty never called
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_no_tty_skips_iterm_close():
    svc = _make_service()
    session = _make_session("koder-5")

    with (
        patch.object(aas, "_get_tmux_tty", return_value=None),
        patch.object(aas, "_close_iterm_tab_by_tty") as mock_close,
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session)

    mock_close.assert_not_called()
