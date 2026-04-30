from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PLANNER_SKILL = REPO / "core" / "skills" / "planner" / "SKILL.md"


def test_planner_skill_has_compaction_hint_in_post_delivery_relay() -> None:
    text = PLANNER_SKILL.read_text(encoding="utf-8")

    section_match = re.search(
        r"## Post-DELIVERY Relay to Memory(?P<section>.*?)(?:\n## |\Z)",
        text,
        flags=re.S,
    )
    assert section_match is not None
    section = section_match.group("section")

    assert "compaction_hint" in section
    assert "compaction_reason" in section
    assert "ready-for-merge" in section
    assert re.search(
        r"ready-for-merge\s+-\s*verdict\s+[^\n]+-\s*branch\s+[^\n]+\s+commit\s+[^\n]+\s+sweep\s+[^\n]+\s+-\s*compaction_hint=<yes\|no>\(<[^>]+>\)",
        section,
    )
    assert "已处理 N 步,context 估计 >70%" in section
    assert "本 task 含大量 file read / sweep output" in section
    assert "单步小改,context 占用低" in section
