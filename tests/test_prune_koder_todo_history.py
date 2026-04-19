"""Tests for T16 Item 4: prune_koder_todo_history.py migration script.

Covers:
  5. test_dry_run_identifies_stale_entries
  6. test_yes_flag_prunes_and_backs_up
  7. test_idempotent_second_run_noop
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "core" / "skills" / "clawseat-install" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import prune_koder_todo_history as pkt


# ── fixture helpers ───────────────────────────────────────────────────────────

_HEADER = "# Queue: koder\n\n"

_STALE_BLOCK_1 = """\
## [completed] task-alpha
task_id: task-alpha
title: Alpha task
dispatched_at: 2026-04-01T00:00:00+00:00

Alpha content.

"""

_STALE_BLOCK_2 = """\
## [completed] task-beta
task_id: task-beta
title: Beta task
dispatched_at: 2026-04-02T00:00:00+00:00

Beta content.

"""

_LIVE_BLOCK = """\
## [queued] task-gamma
task_id: task-gamma
title: Gamma task — live, not consumed yet
dispatched_at: 2026-04-03T00:00:00+00:00

Gamma content.

"""


def _make_todo(tmp_path: Path, blocks: list[str]) -> Path:
    todo = tmp_path / "TODO.md"
    todo.write_text(_HEADER + "".join(blocks), encoding="utf-8")
    return todo


def _make_handoffs(tmp_path: Path, *task_ids: str) -> Path:
    hdir = tmp_path / "handoffs"
    hdir.mkdir(parents=True, exist_ok=True)
    for tid in task_ids:
        (hdir / f"{tid}__planner__koder.json").write_text(json.dumps({"task_id": tid}))
        (hdir / f"{tid}__planner__koder__consumed.json").write_text(json.dumps({"task_id": tid}))
    return hdir


# ══════════════════════════════════════════════════════════════════════════════
# Test 5: dry-run identifies stale entries, does not modify TODO.md
# ══════════════════════════════════════════════════════════════════════════════

def test_dry_run_identifies_stale_entries(tmp_path, capsys):
    todo = _make_todo(tmp_path, [_STALE_BLOCK_1, _STALE_BLOCK_2, _LIVE_BLOCK])
    original_text = todo.read_text(encoding="utf-8")
    handoffs = _make_handoffs(tmp_path, "task-alpha", "task-beta")

    result = pkt.prune_todo(todo, [handoffs], dry_run=True)

    assert result["stale_count"] == 2
    # File must not be modified
    assert todo.read_text(encoding="utf-8") == original_text
    out = capsys.readouterr().out
    assert "task-alpha" in out or "2" in out


# ══════════════════════════════════════════════════════════════════════════════
# Test 6: --yes prunes stale entries, creates backup, retains live entry
# ══════════════════════════════════════════════════════════════════════════════

def test_yes_flag_prunes_and_backs_up(tmp_path):
    todo = _make_todo(tmp_path, [_STALE_BLOCK_1, _STALE_BLOCK_2, _LIVE_BLOCK])
    handoffs = _make_handoffs(tmp_path, "task-alpha", "task-beta")

    result = pkt.prune_todo(todo, [handoffs], dry_run=False)

    assert result["written"] is True
    assert result["backup_path"] is not None
    bak = Path(result["backup_path"])
    assert bak.exists(), "backup file should exist"

    new_text = todo.read_text(encoding="utf-8")
    assert "task-gamma" in new_text
    assert "task-alpha" not in new_text
    assert "task-beta" not in new_text


# ══════════════════════════════════════════════════════════════════════════════
# Test 7: idempotent — second run finds no stale entries to prune
# ══════════════════════════════════════════════════════════════════════════════

def test_idempotent_second_run_noop(tmp_path):
    todo = _make_todo(tmp_path, [_STALE_BLOCK_1, _LIVE_BLOCK])
    handoffs = _make_handoffs(tmp_path, "task-alpha")

    # First run prunes task-alpha
    result1 = pkt.prune_todo(todo, [handoffs], dry_run=False)
    assert result1["stale_count"] == 1
    text_after_first = todo.read_text(encoding="utf-8")

    # Second run: no stale entries remain
    result2 = pkt.prune_todo(todo, [handoffs], dry_run=False)
    assert result2["stale_count"] == 0
    assert result2["written"] is False
    # File unchanged
    assert todo.read_text(encoding="utf-8") == text_after_first
