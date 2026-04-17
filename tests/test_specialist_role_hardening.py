"""Tests for specialist role_details hard ban on raw tmux send-keys (#6).

Coverage:
  - template.toml contains the hard ban text for builder-1
  - template.toml contains the hard ban text for reviewer-1
  - template.toml contains the hard ban text for qa-1
  - template.toml contains the hard ban text for designer-1
  - hard ban text does NOT contain the softened "unless" escape hatch
  - --user-summary is referenced as the compliant exit
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_TEMPLATE = _REPO / "core" / "templates" / "gstack-harness" / "template.toml"

_HARD_BAN = "NEVER use raw tmux send-keys to notify peer seats. Full stop."
_USER_SUMMARY_REF = "--user-summary"


def _template_text() -> str:
    return _TEMPLATE.read_text(encoding="utf-8")


def test_hard_ban_text_present_in_template():
    assert _HARD_BAN in _template_text(), (
        f"Hard ban text not found in {_TEMPLATE}. "
        "Expected: NEVER use raw tmux send-keys to notify peer seats. Full stop."
    )


def test_no_unless_escape_hatch_in_specialist_ban():
    text = _template_text()
    ban_idx = text.find(_HARD_BAN)
    assert ban_idx >= 0
    surrounding = text[ban_idx: ban_idx + 200]
    assert "unless" not in surrounding.lower(), (
        "Hard ban should not include 'unless' escape hatch: " + surrounding
    )


def test_user_summary_referenced_as_compliant_exit():
    text = _template_text()
    assert _USER_SUMMARY_REF in text, (
        "--user-summary must be referenced in template.toml as the compliant rich text exit"
    )


def test_hard_ban_appears_in_builder_section():
    text = _template_text()
    builder_idx = text.find('id = "builder-1"')
    assert builder_idx >= 0
    next_engineer = text.find('[[engineers]]', builder_idx + 1)
    builder_section = text[builder_idx: next_engineer if next_engineer > 0 else len(text)]
    assert _HARD_BAN in builder_section, "Hard ban missing from builder-1 role_details"


def test_hard_ban_appears_in_reviewer_section():
    text = _template_text()
    reviewer_idx = text.find('id = "reviewer-1"')
    assert reviewer_idx >= 0
    next_engineer = text.find('[[engineers]]', reviewer_idx + 1)
    reviewer_section = text[reviewer_idx: next_engineer if next_engineer > 0 else len(text)]
    assert _HARD_BAN in reviewer_section, "Hard ban missing from reviewer-1 role_details"


def test_hard_ban_appears_in_qa_section():
    text = _template_text()
    qa_idx = text.find('id = "qa-1"')
    assert qa_idx >= 0
    next_engineer = text.find('[[engineers]]', qa_idx + 1)
    qa_section = text[qa_idx: next_engineer if next_engineer > 0 else len(text)]
    assert _HARD_BAN in qa_section, "Hard ban missing from qa-1 role_details"


def test_hard_ban_appears_in_designer_section():
    text = _template_text()
    designer_idx = text.find('id = "designer-1"')
    assert designer_idx >= 0
    next_engineer = text.find('[[engineers]]', designer_idx + 1)
    designer_section = text[designer_idx: next_engineer if next_engineer > 0 else len(text)]
    assert _HARD_BAN in designer_section, "Hard ban missing from designer-1 role_details"
