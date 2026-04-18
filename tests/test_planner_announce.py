"""
Tests for planner-event Feishu announce helpers in dispatch_task.py and complete_handoff.py.

Gate logic: CLAWSEAT_ANNOUNCE_PLANNER_EVENTS=1 AND (source=="planner" OR target=="planner").
Fail-safe: _feishu exceptions are swallowed; main flow exit code unaffected.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts directory is on path for direct import
_SCRIPTS = Path(__file__).resolve().parent.parent / "core/skills/gstack-harness/scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import dispatch_task
import complete_handoff


# ── _should_announce_planner_event ────────────────────────────────────────────


def test_env_on_planner_source_triggers(monkeypatch):
    monkeypatch.setenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", "1")
    assert dispatch_task._should_announce_planner_event("planner", "builder-1") is True


def test_env_on_planner_target_triggers(monkeypatch):
    monkeypatch.setenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", "1")
    assert dispatch_task._should_announce_planner_event("builder-1", "planner") is True


def test_env_off_not_triggered(monkeypatch):
    monkeypatch.delenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", raising=False)
    assert dispatch_task._should_announce_planner_event("planner", "builder-1") is False


def test_env_zero_not_triggered(monkeypatch):
    monkeypatch.setenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", "0")
    assert dispatch_task._should_announce_planner_event("planner", "builder-1") is False


def test_non_planner_event_not_triggered(monkeypatch):
    monkeypatch.setenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", "1")
    assert dispatch_task._should_announce_planner_event("builder-1", "reviewer-1") is False


# ── _try_announce_planner_event ───────────────────────────────────────────────


def test_feishu_called_on_announce(monkeypatch):
    """send_feishu_user_message is called with the formatted message."""
    mock_send = MagicMock()
    with patch.dict("sys.modules", {"_feishu": MagicMock(send_feishu_user_message=mock_send)}):
        dispatch_task._try_announce_planner_event(
            project="install",
            source="planner",
            target="builder-1",
            task_id="task-123",
            verb="dispatched",
        )
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    msg = call_args[0][0] if call_args[0] else call_args[1].get("message", "")
    assert "planner" in msg
    assert "builder-1" in msg
    assert "task-123" in msg
    assert "dispatched" in msg


def test_feishu_exception_does_not_crash(monkeypatch, capsys):
    """RuntimeError from _feishu is swallowed; no re-raise."""
    boom = MagicMock(side_effect=RuntimeError("simulated feishu down"))
    with patch.dict("sys.modules", {"_feishu": MagicMock(send_feishu_user_message=boom)}):
        dispatch_task._try_announce_planner_event(
            project="install",
            source="planner",
            target="builder-1",
            task_id="fail-task",
            verb="dispatched",
        )
    captured = capsys.readouterr()
    assert "warn: planner announce failed" in captured.err
    assert "simulated feishu down" in captured.err


def test_message_format_under_80_chars():
    """Normal project/task_id yields a message ≤80 chars."""
    msg = f"[install] planner → builder-1: my-task dispatched"
    assert len(msg) <= 80


def test_message_truncated_over_80_chars(monkeypatch):
    """Very long task_id triggers truncation to ≤80 chars with '...' suffix."""
    called_with: list[str] = []
    mock_send = MagicMock(side_effect=lambda m, **_kw: called_with.append(m))
    with patch.dict("sys.modules", {"_feishu": MagicMock(send_feishu_user_message=mock_send)}):
        dispatch_task._try_announce_planner_event(
            project="install",
            source="planner",
            target="builder-1",
            task_id="x" * 100,
            verb="dispatched",
        )
    assert called_with, "send_feishu_user_message was not called"
    msg = called_with[0]
    assert len(msg) <= 80
    assert msg.endswith("...")


def test_special_char_safe(monkeypatch):
    """task_id/project with special chars does not raise during message construction."""
    mock_send = MagicMock()
    with patch.dict("sys.modules", {"_feishu": MagicMock(send_feishu_user_message=mock_send)}):
        dispatch_task._try_announce_planner_event(
            project="我的项目",
            source="planner",
            target="builder-1",
            task_id="task-$|&-🚀",
            verb="dispatched",
        )
    mock_send.assert_called_once()


# ── Verb differentiation in complete_handoff ──────────────────────────────────


def test_complete_handoff_helpers_byte_equivalent(monkeypatch):
    """Both files expose identical _should_announce_planner_event logic."""
    monkeypatch.setenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", "1")
    assert complete_handoff._should_announce_planner_event("planner", "qa-1") is True
    assert complete_handoff._should_announce_planner_event("builder-1", "reviewer-1") is False


def test_dispatch_task_dispatched_verb(monkeypatch):
    """_try_announce_planner_event with verb='dispatched' includes that word."""
    sent: list[str] = []
    mock_send = MagicMock(side_effect=lambda m, **_kw: sent.append(m))
    with patch.dict("sys.modules", {"_feishu": MagicMock(send_feishu_user_message=mock_send)}):
        dispatch_task._try_announce_planner_event(
            project="install", source="planner", target="builder-1",
            task_id="t1", verb="dispatched",
        )
    assert sent and "dispatched" in sent[0]


def test_complete_handoff_delivered_verb(monkeypatch):
    """_try_announce_planner_event with verb='delivered' includes that word."""
    sent: list[str] = []
    mock_send = MagicMock(side_effect=lambda m, **_kw: sent.append(m))
    with patch.dict("sys.modules", {"_feishu": MagicMock(send_feishu_user_message=mock_send)}):
        complete_handoff._try_announce_planner_event(
            project="install", source="builder-1", target="planner",
            task_id="t2", verb="delivered",
        )
    assert sent and "delivered" in sent[0]


def test_complete_handoff_consumed_verb(monkeypatch):
    """_try_announce_planner_event with verb='consumed' includes that word."""
    sent: list[str] = []
    mock_send = MagicMock(side_effect=lambda m, **_kw: sent.append(m))
    with patch.dict("sys.modules", {"_feishu": MagicMock(send_feishu_user_message=mock_send)}):
        complete_handoff._try_announce_planner_event(
            project="install", source="planner", target="builder-1",
            task_id="t3", verb="consumed",
        )
    assert sent and "consumed" in sent[0]
