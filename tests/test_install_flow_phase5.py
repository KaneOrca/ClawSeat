"""Tests for T17: install-flow.md Phase 5 Feishu bridge smoke canonical."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_INSTALL_FLOW = _REPO / "core" / "skills" / "clawseat-install" / "references" / "install-flow.md"
_SKILL_MD = _REPO / "core" / "skills" / "clawseat-install" / "SKILL.md"


def _flow_text() -> str:
    return _INSTALL_FLOW.read_text(encoding="utf-8")


def _skill_text() -> str:
    return _SKILL_MD.read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: Phase 5 section exists in install-flow.md
# ══════════════════════════════════════════════════════════════════════════════

def test_install_flow_has_phase5_feishu_smoke():
    text = _flow_text()
    assert "Phase 5" in text, "install-flow.md must have a Phase 5 section"
    assert "Feishu" in text or "feishu" in text, "Phase 5 must mention Feishu"
    assert "Smoke" in text or "smoke" in text, "Phase 5 must mention smoke test"


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: All 7 steps are present in install-flow.md Phase 5
# ══════════════════════════════════════════════════════════════════════════════

def test_install_flow_phase5_has_7_steps():
    text = _flow_text()
    # Find Phase 5 section
    phase5_start = text.find("## Phase 5")
    assert phase5_start != -1, "Phase 5 section not found"
    # Find next ## heading after Phase 5
    next_section = text.find("\n## ", phase5_start + 1)
    phase5_text = text[phase5_start:next_section] if next_section != -1 else text[phase5_start:]

    # All 7 canonical steps must be present
    step_keywords = [
        ("auth", "Step 5.1 auth check"),
        ("scopes", "Step 5.2 platform scopes"),
        ("group", "Step 5.3 group ID"),
        ("bind", "Step 5.4 project binding"),
        ("requireMention", "Step 5.5 requireMention config"),
        ("smoke", "Step 5.6 smoke test"),
        ("parse", "Step 5.7 verify parse"),
    ]
    for keyword, desc in step_keywords:
        assert keyword.lower() in phase5_text.lower(), (
            f"Phase 5 must contain step keyword '{keyword}' ({desc})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: SKILL.md overview references Phase 5 Feishu smoke (6 phases)
# ══════════════════════════════════════════════════════════════════════════════

def test_skill_md_references_phase5_feishu_smoke():
    text = _skill_text()
    assert "Phase 5" in text, "SKILL.md must reference Phase 5"
    # Should mention either Feishu or smoke in context of Phase 5
    assert "Feishu" in text or "feishu" in text, "SKILL.md must mention Feishu in Phase 5 context"
    # The 6-phase description should appear
    assert "6-phase" in text or "6 phase" in text or "Phase 5 Feishu" in text, (
        "SKILL.md should indicate 6-phase flow or explicitly name Phase 5 Feishu"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: Common Failures table in install-flow.md covers Feishu-specific errors
# ══════════════════════════════════════════════════════════════════════════════

def test_install_flow_common_failures_has_feishu_errors():
    text = _flow_text()
    assert "auth_expired" in text or "auth_needs_refresh" in text, (
        "install-flow.md must document auth_expired/auth_needs_refresh failure"
    )
    assert "group_not_found" in text or "group not found" in text.lower(), (
        "install-flow.md must document group_not_found failure"
    )
    assert "im:message.group_msg:receive" in text, (
        "install-flow.md must document im:message.group_msg:receive scope failure"
    )
