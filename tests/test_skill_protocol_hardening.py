from __future__ import annotations

from pathlib import Path


def test_reviewer_skill_declares_canonical_verdict_set() -> None:
    text = Path("core/skills/reviewer/SKILL.md").read_text(encoding="utf-8")

    for verdict in (
        "APPROVED",
        "APPROVED_WITH_NITS",
        "CHANGES_REQUESTED",
        "BLOCKED",
        "DECISION_NEEDED",
    ):
        assert f"`{verdict}`" in text

    assert "canonical verdicts" in text.lower()
    assert "FINDINGS-LOGGED" not in text
    assert "PASS/FAIL" not in text


def test_planner_skill_relay_primary_uses_complete_handoff() -> None:
    text = Path("core/skills/planner/SKILL.md").read_text(encoding="utf-8")

    assert "complete_handoff.py --source planner --target memory --task-id <id> --status completed --verdict <V> --notify" in text
    assert "send-and-verify.sh --project <p> memory" not in text
    assert "wake-up only" in text

    for verdict in (
        "APPROVED",
        "APPROVED_WITH_NITS",
        "CHANGES_REQUESTED",
        "BLOCKED",
        "DECISION_NEEDED",
    ):
        assert verdict in text


def test_planner_skill_excludes_project_specific_superseeded_table() -> None:
    text = Path("core/skills/planner/SKILL.md").read_text(encoding="utf-8")

    assert "### SUPERSEDED claims" not in text
    assert "| finding_id | commit_hash | verified_by |" not in text
    assert "Findings without a cited commit hash" not in text
    assert "CH-C1" not in text


def test_builder_skill_includes_closure_protocol_6_line_block() -> None:
    text = Path("core/skills/builder/SKILL.md").read_text(encoding="utf-8")

    assert "Closure Protocol" in text
    assert "6-line block" in text
    assert "git status" in text
    assert "git push" in text
    assert "git log clawseat/" in text
    assert "gh pr view" in text
    assert "git merge-base clawseat/main" in text
