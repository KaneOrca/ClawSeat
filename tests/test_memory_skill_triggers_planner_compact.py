from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MEMORY_SKILL = REPO / "core" / "skills" / "memory-oracle" / "SKILL.md"


def test_memory_skill_has_planner_context_compaction() -> None:
    text = MEMORY_SKILL.read_text(encoding="utf-8")
    section_match = re.search(
        r"## Planner Context 主动压缩(?P<section>.*?)(?:\n## |\Z)",
        text,
        flags=re.S,
    )
    assert section_match is not None
    section = section_match.group("section")

    assert "compaction_hint=yes" in section
    assert "Planner" in section or "planner" in section.lower()
    assert "tmux capture-pane" in section
    assert "send-and-verify.sh --project <p> planner \"/compact\"" in section
    assert "Wait 3" in section or "等待 3 秒" in section
    assert "[compacted planner @ <ts>]" in section
