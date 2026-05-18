"""CF041: Focused tests for planner fan-in stale closeout detection.

Verifies that detect_stale_fanin_closeout() correctly identifies tasks where:
- A builder->planner handoff has been consumed (planner received the delivery)
- But no planner->memory receipt exists (planner final closeout is missing)

Also verifies non-noisy cases:
- Healthy closed tasks (planner->memory receipt present) are silent.
- Fresh in-progress tasks (no consumed file yet) are not flagged.
- Deliveries to non-planner targets (e.g. memory directly) are not flagged.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "core" / "skills" / "gstack-harness" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from patrol_loop import detect_stale_fanin_closeout  # noqa: E402


def _write_consumed(handoffs: Path, task_key: str, source: str, target: str) -> Path:
    handoffs.mkdir(parents=True, exist_ok=True)
    path = handoffs / f"{task_key}__{source}__{target}.json.consumed"
    path.write_text("consumed\n", encoding="utf-8")
    return path


def _write_receipt(handoffs: Path, task_key: str, source: str, target: str) -> Path:
    handoffs.mkdir(parents=True, exist_ok=True)
    path = handoffs / f"{task_key}__{source}__{target}.json"
    path.write_text("{}", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Core stale fan-in detection
# ---------------------------------------------------------------------------


def test_stale_fanin_when_consumed_but_no_memory_receipt(tmp_path: Path, monkeypatch) -> None:
    """Builder delivery consumed but planner->memory receipt absent → stale."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-A", "builder-core", "planner")

    result = detect_stale_fanin_closeout("demo")

    assert len(result) == 1
    assert result[0]["task_id"] == "task-A"
    assert result[0]["planner_seat"] == "planner"


def test_stale_fanin_hint_contains_planner_final_missing(tmp_path: Path, monkeypatch) -> None:
    """Stale fan-in hint must contain 'planner_final_missing'."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-B", "builder-core", "planner")

    result = detect_stale_fanin_closeout("demo")

    assert result
    assert "planner_final_missing" in result[0]["hint"]


def test_stale_fanin_with_qualified_planner_seat_name(tmp_path: Path, monkeypatch) -> None:
    """Works with qualified seat names like clawseat-core-planner."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "cf041-task", "clawseat-core-builder-core", "clawseat-core-planner")

    result = detect_stale_fanin_closeout("demo")

    assert len(result) == 1
    assert result[0]["task_id"] == "cf041-task"
    assert result[0]["planner_seat"] == "clawseat-core-planner"
    assert "planner_final_missing" in result[0]["hint"]


# ---------------------------------------------------------------------------
# Non-noisy: healthy closed task
# ---------------------------------------------------------------------------


def test_healthy_closed_task_is_silent(tmp_path: Path, monkeypatch) -> None:
    """When planner->memory receipt exists alongside consumed file, no stale is reported."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-C", "builder-core", "planner")
    _write_receipt(handoffs, "task-C", "planner", "memory")

    result = detect_stale_fanin_closeout("demo")

    assert result == [], f"expected empty but got {result}"


def test_healthy_qualified_planner_closes_out_silently(tmp_path: Path, monkeypatch) -> None:
    """Qualified planner seat with matching memory receipt produces no stale reports."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-D", "team-builder-core", "team-planner")
    _write_receipt(handoffs, "task-D", "team-planner", "memory")

    result = detect_stale_fanin_closeout("demo")

    assert result == []


# ---------------------------------------------------------------------------
# Non-noisy: fresh in-progress (builder not yet delivered)
# ---------------------------------------------------------------------------


def test_fresh_inprogress_not_stale(tmp_path: Path, monkeypatch) -> None:
    """No consumed file → builder not yet delivered → no stale fan-in."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    # Only a dispatch receipt, no consumed
    _write_receipt(handoffs, "task-E", "planner", "builder-core")

    result = detect_stale_fanin_closeout("demo")

    assert result == []


def test_empty_handoffs_dir_returns_empty(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    handoffs.mkdir(parents=True)

    result = detect_stale_fanin_closeout("demo")

    assert result == []


def test_missing_handoffs_dir_returns_empty(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    result = detect_stale_fanin_closeout("demo")

    assert result == []


# ---------------------------------------------------------------------------
# Non-noisy: non-planner target is not flagged
# ---------------------------------------------------------------------------


def test_non_planner_target_not_flagged(tmp_path: Path, monkeypatch) -> None:
    """A consumed file where target is 'memory' (not planner) must not be flagged."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-F", "planner", "memory")

    result = detect_stale_fanin_closeout("demo")

    assert result == [], f"non-planner target should not be flagged: {result}"


def test_builder_to_reviewer_not_flagged(tmp_path: Path, monkeypatch) -> None:
    """A consumed file where target is 'reviewer' must not be flagged."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-G", "builder-core", "reviewer")

    result = detect_stale_fanin_closeout("demo")

    assert result == []


# ---------------------------------------------------------------------------
# Multiple tasks: mix of stale and healthy
# ---------------------------------------------------------------------------


def test_mixed_tasks_only_stale_reported(tmp_path: Path, monkeypatch) -> None:
    """Among multiple tasks, only the stale one (no memory receipt) is reported."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"

    # task-H: stale — consumed but no memory receipt
    _write_consumed(handoffs, "task-H", "builder-core", "planner")

    # task-I: healthy — consumed AND memory receipt present
    _write_consumed(handoffs, "task-I", "builder-core", "planner")
    _write_receipt(handoffs, "task-I", "planner", "memory")

    # task-J: in-flight — no consumed file
    _write_receipt(handoffs, "task-J", "planner", "builder-core")

    result = detect_stale_fanin_closeout("demo")

    task_ids = [r["task_id"] for r in result]
    assert "task-H" in task_ids
    assert "task-I" not in task_ids
    assert "task-J" not in task_ids


def test_dedup_multiple_consumed_files_same_task(tmp_path: Path, monkeypatch) -> None:
    """Multiple .consumed files for the same task_id+target are deduplicated."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    # Simulate two iteration consumed files for the same task (review rounds)
    _write_consumed(handoffs, "task-K", "builder-core", "planner")
    alt = handoffs / "task-K__builder-alt__planner.json.consumed"
    alt.write_text("consumed\n", encoding="utf-8")

    result = detect_stale_fanin_closeout("demo")

    # Both share the same (task_key, target) dedup key, so only one report
    assert len([r for r in result if r["task_id"] == "task-K"]) == 1


# ---------------------------------------------------------------------------
# No builder-to-memory bypass: function only reads files, never notifies
# ---------------------------------------------------------------------------


def test_function_never_sends_notification(tmp_path: Path, monkeypatch) -> None:
    """detect_stale_fanin_closeout must only inspect files, never trigger wakeups."""
    import subprocess

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-L", "builder-core", "planner")

    # Patch subprocess.run to detect any accidental notification attempt
    calls: list = []
    original_run = subprocess.run

    def _spy(*args, **kwargs):
        calls.append(args)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _spy)

    detect_stale_fanin_closeout("demo")

    # No subprocess calls should have been made by our detection function
    assert calls == [], f"unexpected subprocess calls: {calls}"
