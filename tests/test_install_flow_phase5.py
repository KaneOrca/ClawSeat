"""Tests for install-flow.md phase structure (6-phase canonical: P0-P5).

Historically Phase 5 held the Feishu bridge smoke (7-step canonical). In
the operator-driven overlay flow (F6, 2026-04), Phase 5 is the handoff
step ("ancestor goes standby; operator talks to koder directly") and the
Feishu bridge smoke moved to Phase 4. The file name is kept for git
history continuity.
"""
from __future__ import annotations

from pathlib import Path


_REPO = Path(__file__).resolve().parent.parent
_INSTALL_FLOW = _REPO / "core" / "skills" / "clawseat-install" / "references" / "install-flow.md"
_SKILL_MD = _REPO / "core" / "skills" / "clawseat-install" / "SKILL.md"


def _flow_text() -> str:
    return _INSTALL_FLOW.read_text(encoding="utf-8")


def _skill_text() -> str:
    return _SKILL_MD.read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: Phase 5 is now the Handoff step (ancestor standby)
# ══════════════════════════════════════════════════════════════════════════════

def test_install_flow_phase5_is_handoff():
    text = _flow_text()
    assert "Phase 5" in text, "install-flow.md must have a Phase 5 section"
    p5_start = text.find("## Phase 5")
    next_heading = text.find("\n## ", p5_start + 1)
    p5 = text[p5_start:next_heading] if next_heading != -1 else text[p5_start:]
    # Phase 5 must mention handoff / standby / koder-takes-over
    assert "Handoff" in p5 or "handoff" in p5 or "standby" in p5.lower(), (
        "Phase 5 must be the handoff phase (ancestor goes standby; operator talks to koder)"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: Phase 4 owns the Feishu bridge smoke, delivered via planner
# ══════════════════════════════════════════════════════════════════════════════

def test_install_flow_phase4_has_feishu_smoke_via_planner():
    text = _flow_text()
    assert "Phase 4" in text, "install-flow.md must have a Phase 4 section"
    p4_start = text.find("## Phase 4")
    next_heading = text.find("\n## ", p4_start + 1)
    p4 = text[p4_start:next_heading] if next_heading != -1 else text[p4_start:]

    required = [
        ("planner", "Phase 4 starts planner"),
        ("smoke", "Phase 4 runs the Feishu smoke test"),
        ("bind_project_to_group", "Phase 4 binds the project to a Feishu group"),
        ("send_delegation_report", "Phase 4 dispatches via send_delegation_report (through planner)"),
        ("koder", "Phase 4 verifies koder receives the smoke"),
    ]
    for keyword, reason in required:
        assert keyword.lower() in p4.lower(), (
            f"Phase 4 must mention '{keyword}': {reason}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: SKILL.md references the 6-phase canonical flow (P0-P5)
# ══════════════════════════════════════════════════════════════════════════════

def test_skill_md_references_canonical_6_phase_flow():
    text = _skill_text()
    # Must name all six phases
    for phase in ("Phase 0", "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"):
        assert phase in text, f"SKILL.md must reference '{phase}'"
    # Must explicitly mention the 6-phase structure
    assert "6-phase" in text or "6 phase" in text or "P0" in text, (
        "SKILL.md must explicitly describe the 6-phase flow"
    )
    # Feishu is still covered (just moved to P4)
    assert "Feishu" in text or "feishu" in text, (
        "SKILL.md must mention Feishu in the phase summary"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: Common Failures still covers Feishu-specific errors
# ══════════════════════════════════════════════════════════════════════════════

def test_install_flow_common_failures_has_feishu_errors():
    text = _flow_text()
    assert "auth_expired" in text or "auth_needs_refresh" in text, (
        "install-flow.md must document auth_expired / auth_needs_refresh failure"
    )
    assert "group_not_found" in text or "group not found" in text.lower(), (
        "install-flow.md must document group_not_found failure"
    )
    assert "im:message.group_msg:receive" in text, (
        "install-flow.md must document im:message.group_msg:receive scope failure"
    )
