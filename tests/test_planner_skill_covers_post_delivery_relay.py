from __future__ import annotations

import re
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]


def test_planner_skill_documents_post_delivery_relay_to_memory() -> None:
    text = (_REPO / "core" / "skills" / "planner" / "SKILL.md").read_text(encoding="utf-8")
    section_match = re.search(
        r"## Post-DELIVERY Relay to Memory(?P<section>.*?)(?:\n## |\Z)",
        text,
        flags=re.S,
    )

    assert section_match is not None
    section = section_match.group("section")
    assert "ready-for-merge" in section
    assert re.search(r"Update .*planner/DELIVERY\.md", section, flags=re.I | re.S)
    assert re.search(r"send-and-verify(?:\.sh)?.*memory", section, flags=re.I | re.S)
    assert len(re.findall(r"^\d+\.", section, flags=re.M)) >= 4
