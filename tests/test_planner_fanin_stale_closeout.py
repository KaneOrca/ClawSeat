"""CF041 (rework): Focused tests for planner fan-in stale closeout detection.

Verifies that detect_stale_fanin_closeout() correctly identifies tasks where:
- A builder->planner handoff has been consumed (planner received the delivery)
- Neither the child task_id planner->memory receipt, nor the parent task_id
  planner->memory receipt, nor a task_done PASS in the queue exist

Also verifies non-noisy cases:
- Child consumed + parent planner->memory receipt present → silent (healthy parent closeout)
- Child consumed + child planner->memory receipt present → silent (child-level closeout)
- Child consumed + queue task_done PASS for parent → silent
- Fresh in-progress tasks (no consumed file) → not flagged
- Deliveries to non-planner targets → not flagged
- No subprocess/notification calls made during detection
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "core" / "skills" / "gstack-harness" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from patrol_loop import (  # noqa: E402
    _resolve_parent_task_key,
    _has_task_done_pass,
    detect_stale_fanin_closeout,
)


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


def _write_queue(queue_path: Path, task_id: str, verdict: str = "PASS") -> Path:
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    event = json.dumps({
        "seq": 1,
        "event_type": "task_done",
        "task_id": task_id,
        "actor": "planner@claude",
        "event_ts": "2026-05-19T00:00:00+00:00",
        "verdict": verdict,
    })
    queue_path.write_text(event + "\n", encoding="utf-8")
    return queue_path


# ---------------------------------------------------------------------------
# _resolve_parent_task_key unit tests
# ---------------------------------------------------------------------------

def test_resolve_terminal_builder_suffix():
    """CF-style: {parent}-{date}-builder → {parent}-{date}."""
    key = "cf041-clawseat-planner-fanin-20260519-builder"
    assert _resolve_parent_task_key(key) == "cf041-clawseat-planner-fanin-20260519"


def test_resolve_terminal_reviewer_suffix():
    key = "al084-right-sidebar-chat-20260504-reviewer"
    assert _resolve_parent_task_key(key) == "al084-right-sidebar-chat-20260504"


def test_resolve_terminal_patrol_suffix():
    key = "al119-console-500-cleanup-20260505-patrol"
    assert _resolve_parent_task_key(key) == "al119-console-500-cleanup-20260505"


def test_resolve_role_before_date_reviewer():
    """Cartooner-product style: {base}-reviewer-{date} → {base}-{date}."""
    key = "al093-project-isolated-runtime-agent-live-loop-reviewer-20260504"
    assert _resolve_parent_task_key(key) == "al093-project-isolated-runtime-agent-live-loop-20260504"


def test_resolve_role_before_date_patrol():
    key = "al119-electron-dogfood-console-500-cleanup-patrol-20260505"
    assert _resolve_parent_task_key(key) == "al119-electron-dogfood-console-500-cleanup-20260505"


def test_resolve_no_suffix_unchanged():
    """Task with no child suffix returns unchanged."""
    key = "cf041-clawseat-planner-fanin-20260519"
    assert _resolve_parent_task_key(key) == key


def test_resolve_plain_task_id_unchanged():
    key = "task-without-role"
    assert _resolve_parent_task_key(key) == key


# ---------------------------------------------------------------------------
# _has_task_done_pass unit tests
# ---------------------------------------------------------------------------

def test_has_task_done_pass_true(tmp_path: Path):
    qpath = _write_queue(tmp_path / "tasks.queue.jsonl", "parent-task-X")
    assert _has_task_done_pass([qpath], "parent-task-X") is True


def test_has_task_done_pass_wrong_verdict(tmp_path: Path):
    qpath = _write_queue(tmp_path / "tasks.queue.jsonl", "parent-task-X", verdict="FAIL")
    assert _has_task_done_pass([qpath], "parent-task-X") is False


def test_has_task_done_pass_different_task(tmp_path: Path):
    qpath = _write_queue(tmp_path / "tasks.queue.jsonl", "parent-task-X")
    assert _has_task_done_pass([qpath], "parent-task-Y") is False


def test_has_task_done_pass_empty_list(tmp_path: Path):
    assert _has_task_done_pass([], "any-task") is False


def test_has_task_done_pass_missing_file(tmp_path: Path):
    assert _has_task_done_pass([tmp_path / "nonexistent.jsonl"], "any-task") is False


# ---------------------------------------------------------------------------
# Core stale detection: child consumed + parent NOT closed → stale
# ---------------------------------------------------------------------------

def test_child_consumed_parent_not_closed_is_reported(tmp_path: Path, monkeypatch) -> None:
    """Child builder consumed by planner; no parent planner->memory receipt → stale."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    # child task_id has -builder suffix; parent = "task-A"
    _write_consumed(handoffs, "task-A-builder", "builder-core", "planner")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert len(result) == 1
    assert result[0]["task_id"] == "task-A-builder"
    assert result[0]["parent_task_id"] == "task-A"
    assert "planner_final_missing" in result[0]["hint"]


def test_stale_fanin_hint_contains_planner_final_missing(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-B-builder", "builder-core", "planner")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result
    assert "planner_final_missing" in result[0]["hint"]


def test_stale_fanin_with_qualified_seat_names(tmp_path: Path, monkeypatch) -> None:
    """Qualified seat names like clawseat-core-planner are detected correctly."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(
        handoffs,
        "cf041-fanin-20260519-builder",
        "clawseat-core-builder-core",
        "clawseat-core-planner",
    )

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert len(result) == 1
    assert result[0]["task_id"] == "cf041-fanin-20260519-builder"
    assert result[0]["parent_task_id"] == "cf041-fanin-20260519"


# ---------------------------------------------------------------------------
# Non-noisy: child consumed + parent planner->memory receipt exists → silent
# ---------------------------------------------------------------------------

def test_child_consumed_parent_receipt_present_is_silent(tmp_path: Path, monkeypatch) -> None:
    """Child builder consumed by planner; parent planner->memory receipt exists → silent."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-C-builder", "builder-core", "planner")
    # Parent receipt uses parent task_id (task-C, not task-C-builder)
    _write_receipt(handoffs, "task-C", "planner", "memory")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == [], f"expected empty (parent receipt exists), got {result}"


def test_child_consumed_parent_receipt_qualified_seat_is_silent(tmp_path: Path, monkeypatch) -> None:
    """CF-style: cf041-...-builder consumed; cf041-... parent planner->memory exists → silent."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(
        handoffs,
        "cf041-fanin-20260519-builder",
        "clawseat-core-builder-core",
        "clawseat-core-planner",
    )
    # Parent planner->memory receipt uses parent task_id (no -builder suffix)
    _write_receipt(handoffs, "cf041-fanin-20260519", "clawseat-core-planner", "memory")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == [], f"expected empty (parent receipt exists), got {result}"


def test_child_consumed_child_receipt_present_is_silent(tmp_path: Path, monkeypatch) -> None:
    """Child task_id also closed at child level → silent."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-D-reviewer", "reviewer", "planner")
    # Child receipt exists (planner closed out the child task directly)
    _write_receipt(handoffs, "task-D-reviewer", "planner", "memory")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == []


def test_role_before_date_parent_receipt_present_is_silent(tmp_path: Path, monkeypatch) -> None:
    """Cartooner-product style: {base}-reviewer-{date}; parent {base}-{date} receipt exists → silent."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "al119-cleanup-reviewer-20260505", "reviewer", "planner")
    # Parent receipt uses {base}-{date} (role stripped, date kept)
    _write_receipt(handoffs, "al119-cleanup-20260505", "planner", "memory")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == [], f"expected silent (parent receipt exists), got {result}"


# ---------------------------------------------------------------------------
# Non-noisy: queue task_done PASS for parent → silent
# ---------------------------------------------------------------------------

def test_child_consumed_queue_task_done_pass_is_silent(tmp_path: Path, monkeypatch) -> None:
    """Child consumed; queue has task_done PASS for parent → silent."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-E-builder", "builder-core", "planner")
    qpath = _write_queue(tmp_path / "q.jsonl", "task-E")

    result = detect_stale_fanin_closeout("demo", handoffs_dir=handoffs, queue_paths=[qpath])

    assert result == [], f"expected silent (queue PASS for parent), got {result}"


def test_child_consumed_queue_fail_not_silent(tmp_path: Path, monkeypatch) -> None:
    """Child consumed; queue has task_done FAIL for parent → still stale."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-F-builder", "builder-core", "planner")
    qpath = _write_queue(tmp_path / "q.jsonl", "task-F", verdict="FAIL")

    result = detect_stale_fanin_closeout("demo", handoffs_dir=handoffs, queue_paths=[qpath])

    assert len(result) == 1


# ---------------------------------------------------------------------------
# Non-noisy: fresh in-progress (builder not yet delivered) → quiet
# ---------------------------------------------------------------------------

def test_fresh_inprogress_not_stale(tmp_path: Path, monkeypatch) -> None:
    """No consumed file → builder not yet delivered → not flagged."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    # Only a dispatch receipt, no consumed
    _write_receipt(handoffs, "task-G-builder", "planner", "builder-core")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == []


def test_empty_handoffs_dir_returns_empty(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    handoffs.mkdir(parents=True)

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == []


def test_missing_handoffs_dir_returns_empty(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == []


# ---------------------------------------------------------------------------
# Non-noisy: non-planner target → not flagged
# ---------------------------------------------------------------------------

def test_non_planner_target_not_flagged(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-H", "planner", "memory")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == []


def test_builder_to_reviewer_not_flagged(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-I", "builder-core", "reviewer")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert result == []


# ---------------------------------------------------------------------------
# Mixed tasks: only truly stale reported
# ---------------------------------------------------------------------------

def test_mixed_tasks_only_stale_reported(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"

    # task-J-builder: stale — consumed, parent has no receipt or queue
    _write_consumed(handoffs, "task-J-builder", "builder-core", "planner")

    # task-K-builder: healthy — consumed, parent receipt exists
    _write_consumed(handoffs, "task-K-builder", "builder-core", "planner")
    _write_receipt(handoffs, "task-K", "planner", "memory")

    # task-L-reviewer-20260519: healthy — role-before-date, parent receipt exists
    _write_consumed(handoffs, "task-L-reviewer-20260519", "reviewer", "planner")
    _write_receipt(handoffs, "task-L-20260519", "planner", "memory")

    # task-M: in-flight (no consumed file)
    _write_receipt(handoffs, "task-M-builder", "planner", "builder-core")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])
    task_ids = [r["task_id"] for r in result]

    assert "task-J-builder" in task_ids
    assert "task-K-builder" not in task_ids
    assert "task-L-reviewer-20260519" not in task_ids
    assert "task-M-builder" not in task_ids


def test_dedup_multiple_consumed_files_same_task(tmp_path: Path, monkeypatch) -> None:
    """Multiple .consumed files for the same task_id+target are deduplicated."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-N-builder", "builder-core", "planner")
    alt = handoffs / "task-N-builder__builder-alt__planner.json.consumed"
    alt.write_text("consumed\n", encoding="utf-8")

    result = detect_stale_fanin_closeout("demo", queue_paths=[])

    assert len([r for r in result if r["task_id"] == "task-N-builder"]) == 1


# ---------------------------------------------------------------------------
# No builder-to-memory bypass: function only reads files, never notifies
# ---------------------------------------------------------------------------

def test_function_never_sends_notification(tmp_path: Path, monkeypatch) -> None:
    """detect_stale_fanin_closeout must only inspect files, never trigger wakeups."""
    import subprocess

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    _write_consumed(handoffs, "task-O-builder", "builder-core", "planner")

    calls: list = []
    original_run = subprocess.run

    def _spy(*args, **kwargs):
        calls.append(args)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _spy)

    detect_stale_fanin_closeout("demo", queue_paths=[])

    assert calls == [], f"unexpected subprocess calls: {calls}"
