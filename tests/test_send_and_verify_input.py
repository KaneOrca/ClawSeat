"""Regression tests for send-and-verify.sh input validation (audit H3).

The script runs `tmux send-keys -l` which presses every byte of the
message literally into a pane. If the message contains CR/LF, tmux will
treat them as Enter/newline and split one logical message into multiple
submits. These tests pin the early-reject path so callers cannot
introduce that class of bug by smuggling control characters through.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "core" / "shell-scripts" / "send-and-verify.sh"

# rc=2 is reserved for INPUT_REJECTED.
REJECT_RC = 2


def _run(session: str, message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), session, message],
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize(
    "bad_char, name",
    [
        ("\n", "LF"),
        ("\r", "CR"),
        ("\x0b", "VT"),
        ("\x0c", "FF"),
    ],
)
def test_message_with_control_char_is_rejected(bad_char: str, name: str) -> None:
    result = _run("koder", f"hello{bad_char}world")
    assert result.returncode == REJECT_RC, (
        f"{name} in message should hit INPUT_REJECTED, got rc={result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "INPUT_REJECTED" in result.stderr
    assert "HARD_BLOCK" in result.stderr


def test_session_name_with_control_char_is_rejected() -> None:
    result = _run("koder\npwned", "hi")
    assert result.returncode == REJECT_RC
    assert "INPUT_REJECTED" in result.stderr
    assert "session" in result.stderr


def test_rejected_session_error_matches_message_with_LF() -> None:
    """Error must point at the right field (session, not message)."""
    result = _run("good-sess", "hi\nmore")
    assert result.returncode == REJECT_RC
    assert "message" in result.stderr


def test_oversized_message_is_rejected() -> None:
    result = _run("koder", "x" * 9000)
    assert result.returncode == REJECT_RC
    assert "exceeds" in result.stderr


def test_usage_message_when_args_missing() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 1
    assert "Usage" in result.stdout


def test_plain_message_passes_validation_and_hits_tmux_layer() -> None:
    """A clean message clears validation. With no live tmux session the
    script will fail later (TMUX_MISSING or SESSION_NOT_FOUND) — the
    point is that it does NOT exit with the reject code."""
    result = _run("nonexistent-session", "hello world")
    assert result.returncode != REJECT_RC, (
        f"clean message was rejected as input (rc={result.returncode}); "
        f"stderr={result.stderr}"
    )
