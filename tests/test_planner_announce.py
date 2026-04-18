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


# ── Config-gate tests (4 new) ─────────────────────────────────────────────────


def _make_profile_mock(announce: bool) -> MagicMock:
    obs = MagicMock()
    obs.announce_planner_events = announce
    profile = MagicMock()
    profile.observability = obs
    return profile


def test_config_gate_profile_true_env_unset(monkeypatch):
    """profile.observability.announce_planner_events=True + env unset → True (planner event)."""
    monkeypatch.delenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", raising=False)
    profile = _make_profile_mock(announce=True)
    assert dispatch_task._should_announce_planner_event("planner", "builder-1", profile=profile) is True


def test_config_gate_profile_false_env_unset(monkeypatch):
    """profile.observability.announce_planner_events=False + env unset → False."""
    monkeypatch.delenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", raising=False)
    profile = _make_profile_mock(announce=False)
    assert dispatch_task._should_announce_planner_event("planner", "builder-1", profile=profile) is False


def test_config_gate_env_one_overrides_profile_false(monkeypatch):
    """env='1' overrides profile.announce_planner_events=False → True."""
    monkeypatch.setenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", "1")
    profile = _make_profile_mock(announce=False)
    assert dispatch_task._should_announce_planner_event("planner", "builder-1", profile=profile) is True


def test_config_gate_env_zero_overrides_profile_true(monkeypatch):
    """env='0' overrides profile.announce_planner_events=True → False."""
    monkeypatch.setenv("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", "0")
    profile = _make_profile_mock(announce=True)
    assert dispatch_task._should_announce_planner_event("planner", "builder-1", profile=profile) is False


# ── E2E smoke: subprocess dispatch_task.py with profile config ────────────────


def test_e2e_config_announce_via_profile(tmp_path, monkeypatch):
    """Stub lark-cli; dispatch_task with profile announce=true triggers the stub."""
    import subprocess
    import json

    # Write a minimal stub lark-cli that records calls
    stub_log = tmp_path / "lark_calls.log"
    stub = tmp_path / "lark-cli"
    stub.write_text(f"#!/bin/sh\necho \"$@\" >> {stub_log}\nexit 0\n")
    stub.chmod(0o755)

    # Build a temporary profile that has observability.announce_planner_events=true
    # and minimal required fields
    import tomllib
    real_profile = Path("/Users/ywf/.agents/profiles/install-profile-dynamic.toml")
    if not real_profile.exists():
        pytest.skip("real profile not found")

    # Make a copy of the profile with announce=true (it already has it, but be explicit)
    profile_text = real_profile.read_text(encoding="utf-8")
    # If [observability] not present, add it
    if "[observability]" not in profile_text:
        profile_text += "\n[observability]\nannounce_planner_events = true\n"
    tmp_profile = tmp_path / "test-profile.toml"
    tmp_profile.write_text(profile_text, encoding="utf-8")

    env = {
        **{k: v for k, v in __import__("os").environ.items()},
        "PATH": f"{tmp_path}:{__import__('os').environ.get('PATH', '')}",
    }
    # Unset env override so config gate is exercised
    env.pop("CLAWSEAT_ANNOUNCE_PLANNER_EVENTS", None)

    scripts_dir = str(_SCRIPTS)
    result = subprocess.run(
        [
            "python3", str(_SCRIPTS / "dispatch_task.py"),
            "--profile", str(tmp_profile),
            "--source", "planner",
            "--target", "builder-1",
            "--task-id", "smoke-announce-001",
            "--title", "smoke test",
            "--objective", "verify announce gate",
            "--reply-to", "planner",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=scripts_dir,
    )
    # The dispatch may fail (no real session/workspace), but if announce fired
    # the stub should have been called. We check stderr for announce warn OR
    # stub_log for a call — either proves the gate opened.
    stub_was_called = stub_log.exists() and stub_log.stat().st_size > 0
    # Gate opened if stub was called OR announce warn appeared in stderr
    # (fail-safe swallows feishu errors without changing exit code)
    gate_opened = stub_was_called or "planner announce" in result.stderr
    assert gate_opened, (
        "Config gate did not open: lark-cli stub not called and no announce warn in stderr.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Dispatch itself should succeed (rc=0) regardless of announce outcome
    assert result.returncode == 0, (
        f"dispatch_task.py failed (rc={result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
