"""Tests for T12 + T12-fix1: session stop-engineer closes iTerm tab before tmux kill.

Covers:
  1. test_stop_engineer_closes_iterm_tab_when_tty_found
  2. test_stop_engineer_warns_when_iterm_tab_not_found
  3. test_stop_engineer_warns_on_iterm_close_error
  4. test_stop_engineer_default_does_not_close_iterm  — F1 regression canary
  5. test_stop_engineer_no_tty_skips_iterm_close
  6. test_session_stop_engineer_cli_passes_close_iterm_tab_true_by_default
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import agent_admin_session as aas
from agent_admin_commands import CommandHandlers, CommandHooks


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_session(name: str = "test-session") -> SimpleNamespace:
    return SimpleNamespace(session=name)


def _make_service() -> aas.SessionService:
    hooks = MagicMock()
    hooks.tmux_has_session.return_value = True
    return aas.SessionService(hooks)


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: close_iterm_tab=True + tty found → tab closed + tmux killed
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_closes_iterm_tab_when_tty_found(capsys):
    svc = _make_service()
    session = _make_session("koder-1")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys001") as mock_tty,
        patch.object(aas, "_close_iterm_tab_by_tty", return_value={"status": "ok", "detail": None}) as mock_close,
        patch.object(svc, "_run_tmux_with_retry") as mock_tmux,
    ):
        svc.stop_engineer(session, close_iterm_tab=True)

    mock_tty.assert_called_once_with("koder-1")
    mock_close.assert_called_once_with("/dev/ttys001")
    mock_tmux.assert_called_once()
    assert "iterm_tab_closed" in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: close_iterm_tab=True + tab not found → warn stderr + tmux killed
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_warns_when_iterm_tab_not_found(capsys):
    svc = _make_service()
    session = _make_session("koder-2")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys002"),
        patch.object(aas, "_close_iterm_tab_by_tty", return_value={"status": "not_found", "detail": "no match"}),
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session, close_iterm_tab=True)

    err = capsys.readouterr().err
    assert "iterm_tab_not_found" in err


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: close_iterm_tab=True + osascript error → warn stderr + tmux killed
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_warns_on_iterm_close_error(capsys):
    svc = _make_service()
    session = _make_session("koder-3")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys003"),
        patch.object(aas, "_close_iterm_tab_by_tty", return_value={"status": "error", "detail": "timeout"}),
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session, close_iterm_tab=True)

    err = capsys.readouterr().err
    assert "iterm_tab_close_failed" in err
    assert "timeout" in err


# ══════════════════════════════════════════════════════════════════════════════
# Test 4 (F1 regression canary): default stop_engineer() does NOT close iTerm
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_default_does_not_close_iterm():
    """Calling stop_engineer() without close_iterm_tab must never touch iTerm helpers.

    This is the regression canary for F1: crud/switch internal callers must not
    accidentally close iTerm tabs just because they call stop_engineer().
    """
    svc = _make_service()
    session = _make_session("koder-4")

    with (
        patch.object(aas, "_get_tmux_tty") as mock_tty,
        patch.object(aas, "_close_iterm_tab_by_tty") as mock_close,
        patch.object(svc, "_run_tmux_with_retry") as mock_tmux,
    ):
        svc.stop_engineer(session)  # default: close_iterm_tab=False

    mock_tty.assert_not_called()
    mock_close.assert_not_called()
    mock_tmux.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# Test 5: close_iterm_tab=True + no tty → _close_iterm_tab_by_tty never called
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_no_tty_skips_iterm_close():
    svc = _make_service()
    session = _make_session("koder-5")

    with (
        patch.object(aas, "_get_tmux_tty", return_value=None),
        patch.object(aas, "_close_iterm_tab_by_tty") as mock_close,
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session, close_iterm_tab=True)

    mock_close.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Test 6: CLI handler passes close_iterm_tab=True by default (no --keep-iterm-tab)
# ══════════════════════════════════════════════════════════════════════════════

def test_session_stop_engineer_cli_passes_close_iterm_tab_true_by_default():
    """session_stop_engineer with args.keep_iterm_tab=False → close_iterm_tab=True."""
    fake_session = _make_session("koder-6")
    mock_hooks = MagicMock()
    mock_hooks.resolve_engineer_session.return_value = fake_session

    handlers = CommandHandlers(mock_hooks)
    args = SimpleNamespace(engineer="koder", project=None, keep_iterm_tab=False)
    handlers.session_stop_engineer(args)

    mock_hooks.session_service.stop_engineer.assert_called_once_with(
        fake_session, close_iterm_tab=True
    )
