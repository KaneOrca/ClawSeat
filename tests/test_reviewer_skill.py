from __future__ import annotations

from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_SKILL = _REPO / "core" / "skills" / "reviewer" / "SKILL.md"


def _text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def test_reviewer_skill_mentions_browser_based_qa_testing() -> None:
    text = _text()
    assert "browser-based UI/QA testing" in text


def test_reviewer_skill_has_qa_mode_and_no_fix_contract() -> None:
    text = _text()
    assert "## QA Testing Mode (browser / multimodal)" in text
    assert "reviewer/findings/<ts>-<slug>.md" in text
    assert "DO NOT fix bugs" in text


def test_reviewer_skill_retains_diff_review_language() -> None:
    text = _text()
    assert "diff review" in text.lower()
