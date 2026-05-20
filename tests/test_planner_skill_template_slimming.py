from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PLANNER_SKILL = (REPO / "core" / "skills" / "planner" / "SKILL.md").read_text(encoding="utf-8")


def test_planner_skill_has_single_operator_language_matching_section() -> None:
    assert PLANNER_SKILL.count("## Operator Language Matching") == 1


def test_planner_skill_excludes_project_local_hot_path_blocks() -> None:
    for token in (
        "### SUPERSEDED claims",
        "### Core UX gate",
        "core_ux_swallow_blocked",
        "SWALLOW PASS DENIED",
    ):
        assert token not in PLANNER_SKILL


def test_planner_skill_links_canonical_protocol_references() -> None:
    assert "communication-protocol.md" in PLANNER_SKILL
    assert "collaboration-rules.md" in PLANNER_SKILL
