from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PLANNER = (REPO / "core" / "skills" / "planner" / "SKILL.md").read_text(encoding="utf-8")
MEMORY = (REPO / "core" / "skills" / "memory-oracle" / "SKILL.md").read_text(encoding="utf-8")


def test_planner_skill_keeps_compact_requested_section() -> None:
    assert "## [COMPACT-REQUESTED] for planner" in PLANNER


def test_planner_skill_no_compaction_hint_fields() -> None:
    assert "compaction_hint" not in PLANNER
    assert "compaction_reason" not in PLANNER


def test_memory_skill_no_planner_context_compaction() -> None:
    assert "## Planner Context 主动压缩" not in MEMORY
    assert "compaction_hint=yes" not in MEMORY
