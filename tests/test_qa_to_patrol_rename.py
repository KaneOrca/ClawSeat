from __future__ import annotations

from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]


def test_qa_skill_has_patrol_identity() -> None:
    """qa/SKILL.md already has patrol identity and is rename-ready for T6."""
    content = (_REPO / "core" / "skills" / "qa" / "SKILL.md").read_text(encoding="utf-8")

    assert "patrol" in content.lower() or "cron" in content.lower() or "巡检" in content
