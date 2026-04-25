"""Tests for T12 + RCA 2026-04-25: session stop-engineer closes iTerm pane (not tab) before tmux kill.

Covers:
  1. test_stop_engineer_closes_iterm_pane_when_tty_found
  2. test_stop_engineer_warns_when_iterm_pane_not_found
  3. test_stop_engineer_warns_on_iterm_close_error
  4. test_stop_engineer_default_does_not_close_iterm  — F1 regression canary
  5. test_stop_engineer_no_tty_skips_iterm_close
  6. test_session_stop_engineer_cli_passes_close_iterm_pane_true_by_default
  7. test_iterm_close_template_uses_close_s_not_close_t  — RCA 2026-04-25 pin
  8. test_stop_engineer_legacy_close_iterm_tab_kwarg_still_works  — backward compat
  9. test_close_pane_only_targets_one_session_in_multi_pane_tab  — multi-pane safety
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
from agent_admin_commands import CommandHandlers


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_session(name: str = "test-session") -> SimpleNamespace:
    return SimpleNamespace(session=name)


def _make_service() -> aas.SessionService:
    hooks = MagicMock()
    hooks.tmux_has_session.return_value = True
    return aas.SessionService(hooks)


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: close_iterm_pane=True + tty found → pane closed + tmux killed
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_closes_iterm_pane_when_tty_found(capsys):
    svc = _make_service()
    session = _make_session("koder-1")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys001") as mock_tty,
        patch.object(aas, "_close_iterm_pane_by_tty", return_value={"status": "ok", "detail": None}) as mock_close,
        patch.object(svc, "_run_tmux_with_retry") as mock_tmux,
    ):
        svc.stop_engineer(session, close_iterm_pane=True)

    mock_tty.assert_called_once_with("koder-1")
    mock_close.assert_called_once_with("/dev/ttys001")
    mock_tmux.assert_called_once()
    assert "iterm_pane_closed" in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: close_iterm_pane=True + pane not found → warn stderr + tmux killed
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_warns_when_iterm_pane_not_found(capsys):
    svc = _make_service()
    session = _make_session("koder-2")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys002"),
        patch.object(aas, "_close_iterm_pane_by_tty", return_value={"status": "not_found", "detail": "no match"}),
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session, close_iterm_pane=True)

    err = capsys.readouterr().err
    assert "iterm_pane_not_found" in err


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: close_iterm_pane=True + osascript error → warn stderr + tmux killed
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_warns_on_iterm_close_error(capsys):
    svc = _make_service()
    session = _make_session("koder-3")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys003"),
        patch.object(aas, "_close_iterm_pane_by_tty", return_value={"status": "error", "detail": "timeout"}),
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session, close_iterm_pane=True)

    err = capsys.readouterr().err
    assert "iterm_pane_close_failed" in err
    assert "timeout" in err


# ══════════════════════════════════════════════════════════════════════════════
# Test 4 (F1 regression canary): default stop_engineer() does NOT close iTerm
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_default_does_not_close_iterm():
    svc = _make_service()
    session = _make_session("koder-4")

    with (
        patch.object(aas, "_get_tmux_tty") as mock_tty,
        patch.object(aas, "_close_iterm_pane_by_tty") as mock_close,
        patch.object(svc, "_run_tmux_with_retry") as mock_tmux,
    ):
        svc.stop_engineer(session)  # default: close_iterm_pane=False

    mock_tty.assert_not_called()
    mock_close.assert_not_called()
    mock_tmux.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# Test 5: close_iterm_pane=True + no tty → _close_iterm_pane_by_tty never called
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_no_tty_skips_iterm_close():
    svc = _make_service()
    session = _make_session("koder-5")

    with (
        patch.object(aas, "_get_tmux_tty", return_value=None),
        patch.object(aas, "_close_iterm_pane_by_tty") as mock_close,
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session, close_iterm_pane=True)

    mock_close.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Test 6: CLI handler passes close_iterm_pane=True by default
# ══════════════════════════════════════════════════════════════════════════════

def test_session_stop_engineer_cli_passes_close_iterm_pane_true_by_default():
    """session_stop_engineer with args.keep_iterm_tab=False → close_iterm_pane=True."""
    fake_session = _make_session("koder-6")
    mock_hooks = MagicMock()
    mock_hooks.resolve_engineer_session.return_value = fake_session

    handlers = CommandHandlers(mock_hooks)
    args = SimpleNamespace(engineer="koder", project=None, keep_iterm_tab=False)
    handlers.session_stop_engineer(args)

    mock_hooks.session_service.stop_engineer.assert_called_once_with(
        fake_session, close_iterm_pane=True
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 7 (RCA 2026-04-25 pin): AppleScript template uses `close s`, NOT `close t`
# Closing the entire tab nukes all sibling panes — the cartooner 6-pane RCA.
# ══════════════════════════════════════════════════════════════════════════════

def test_iterm_close_template_uses_close_s_not_close_t():
    template = aas._ITERM_CLOSE_SCRIPT_TEMPLATE
    assert "close s" in template, (
        "AppleScript must close the session/pane (close s), not the tab (close t). "
        "RCA 2026-04-25: closing the tab nukes sibling panes."
    )
    assert "\nclose t\n" not in template and " close t " not in template, (
        "`close t` must not appear — it would close the entire tab."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 8 (backward compat): legacy close_iterm_tab kwarg still accepted
# ══════════════════════════════════════════════════════════════════════════════

def test_stop_engineer_legacy_close_iterm_tab_kwarg_still_works(capsys):
    """External callers still passing close_iterm_tab=True must work, mapping to pane close."""
    svc = _make_service()
    session = _make_session("koder-7")

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys007"),
        patch.object(aas, "_close_iterm_pane_by_tty", return_value={"status": "ok", "detail": None}) as mock_close,
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session, close_iterm_tab=True)  # legacy kwarg name

    mock_close.assert_called_once_with("/dev/ttys007")


# ══════════════════════════════════════════════════════════════════════════════
# Test 9 (multi-pane safety): only the targeted pane is closed via osascript
# ══════════════════════════════════════════════════════════════════════════════

def test_close_pane_only_targets_one_session_in_multi_pane_tab():
    """Simulate 1 tab × 6 sessions: stop_engineer for one seat must invoke osascript
    with the specific tty; AppleScript template's `close s` (not `close t`) ensures
    only that single pane is closed, leaving 5 sibling panes intact."""
    svc = _make_service()
    session_target = _make_session("install-builder-1-claude")

    captured_args: list[tuple] = []

    def fake_close(tty: str) -> dict:
        captured_args.append(("close_called", tty))
        return {"status": "ok", "detail": None}

    with (
        patch.object(aas, "_get_tmux_tty", return_value="/dev/ttys100"),
        patch.object(aas, "_close_iterm_pane_by_tty", side_effect=fake_close),
        patch.object(svc, "_run_tmux_with_retry"),
    ):
        svc.stop_engineer(session_target, close_iterm_pane=True)

    # _close_iterm_pane_by_tty was called exactly once with the target tty
    assert captured_args == [("close_called", "/dev/ttys100")]
    # And the AppleScript template uses `close s` so sibling panes (different ttys
    # not matching /dev/ttys100) are not affected — verified by template inspection
    assert "close s" in aas._ITERM_CLOSE_SCRIPT_TEMPLATE
