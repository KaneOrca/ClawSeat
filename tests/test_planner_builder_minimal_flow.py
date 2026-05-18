"""Tests for cf022: planner+builder minimal execution unit flow.

Verifies that ClawSeat supports briefs with seats_required=[builder] (no reviewer)
and that planner guidance reflects the minimal-unit policy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "core" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "core" / "scripts"))

from acceptance_criteria import brief_acceptance_ready  # noqa: E402


# ---------------------------------------------------------------------------
# Brief acceptance: seats_required=[builder] is valid
# ---------------------------------------------------------------------------

def test_brief_with_only_builder_seat_passes_acceptance_ready():
    """seats_required:[builder] without reviewer must not fail brief_acceptance_ready."""
    brief = {
        "acceptance_criteria": {
            "mechanical": ["true"],
            "reviewer": [],
            "operator": [],
        },
        "seats_required": ["builder"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert ready, f"planner+builder minimal brief should be ready; got: {reason}"


def test_brief_with_builder_and_reviewer_still_valid():
    """Adding reviewer must not break acceptance readiness."""
    brief = {
        "acceptance_criteria": {
            "mechanical": ["true"],
            "reviewer": [],
            "operator": [],
        },
        "seats_required": ["builder", "reviewer"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert ready, f"builder+reviewer brief should be ready; got: {reason}"


def test_brief_reviewer_section_empty_does_not_block_acceptance():
    """Empty reviewer list with seats_required=[builder] must not block acceptance."""
    brief = {
        "acceptance_criteria": {
            "mechanical": ["true"],
            "reviewer": [],
        },
        "seats_required": ["builder"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert ready, f"empty reviewer section should not block; got: {reason}"


# ---------------------------------------------------------------------------
# Planner SKILL.md contains the minimal-unit guidance
# ---------------------------------------------------------------------------

def test_planner_skill_contains_minimal_unit_guidance():
    """Planner SKILL.md must state planner+builder is the default minimal unit."""
    skill_path = REPO_ROOT / "core" / "skills" / "planner" / "SKILL.md"
    assert skill_path.exists(), "planner SKILL.md must exist"
    text = skill_path.read_text(encoding="utf-8")
    assert "minimal execution unit" in text.lower() or "minimal unit" in text.lower(), (
        "planner SKILL.md must describe planner+builder as the default minimal unit"
    )


def test_planner_skill_no_longer_blocks_on_missing_reviewer():
    """Planner SKILL.md must NOT instruct blocking on absent reviewer."""
    skill_path = REPO_ROOT / "core" / "skills" / "planner" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    # The old instruction was to "block and ask memory for roster repair"
    # when no reviewer is present. This must not be the only guidance.
    assert "block and ask memory for roster repair" not in text, (
        "planner SKILL.md must not instruct blocking on absent reviewer as default"
    )


def test_planner_skill_contains_parallel_work_guidance():
    """Planner SKILL.md must say planner prepares tests in parallel while builder works."""
    skill_path = REPO_ROOT / "core" / "skills" / "planner" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    assert "parallel" in text.lower(), (
        "planner SKILL.md must mention parallel test/acceptance preparation"
    )


def test_planner_skill_contains_closeout_requirements():
    """Planner SKILL.md must document closeout requirements including review/latest."""
    skill_path = REPO_ROOT / "core" / "skills" / "planner" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    assert "review/latest" in text.lower() or "closeout" in text.lower(), (
        "planner SKILL.md must document closeout requirements including review/latest merge status"
    )


# ---------------------------------------------------------------------------
# Reviewer escalation: still triggered for high-risk
# ---------------------------------------------------------------------------

def test_planner_skill_preserves_reviewer_escalation_for_high_risk():
    """Reviewer escalation must still be documented for security/privacy/filesystem."""
    skill_path = REPO_ROOT / "core" / "skills" / "planner" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    # One of these risk categories must be mentioned
    assert any(kw in text.lower() for kw in ("security", "privacy", "filesystem", "high-risk")), (
        "planner SKILL.md must document reviewer escalation for high-risk tasks"
    )


# ---------------------------------------------------------------------------
# Planner→memory reporting boundary
# ---------------------------------------------------------------------------

def test_planner_skill_contains_memory_reporting_boundary():
    """Planner SKILL.md must document when planner reports to memory."""
    skill_path = REPO_ROOT / "core" / "skills" / "planner" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    # Must mention queue_drained_only or reporting boundary
    assert "queue_drained" in text or "queue drained" in text.lower(), (
        "planner SKILL.md must document queue-drained-only reporting boundary"
    )


def test_planner_skill_no_intermediate_memory_reports():
    """Planner SKILL.md must say ordinary dispatch/rework do not trigger memory reports."""
    skill_path = REPO_ROOT / "core" / "skills" / "planner" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    # Should mention NOT reporting for intermediate states
    assert "does not" in text.lower() or "not report" in text.lower() or "never_notify" in text.lower(), (
        "planner SKILL.md must clarify that ordinary dispatch/rework do not go to memory"
    )


# ---------------------------------------------------------------------------
# Seed script: reinstall produces reviewer-optional config
# ---------------------------------------------------------------------------

def test_seed_minimal_produces_reviewer_optional_config():
    """seed_multi_team_minimal.py must produce reviewer_required_when_builders_gte >= 4."""
    seed_path = REPO_ROOT / "core" / "scripts" / "seed_multi_team_minimal.py"
    assert seed_path.exists(), "seed_multi_team_minimal.py must exist"
    text = seed_path.read_text(encoding="utf-8")
    # reviewer_required_when_builders_gte must be 4 or higher (reviewer optional for 1-3 builders)
    import re
    m = re.search(r"reviewer_required_when_builders_gte:\s*(\d+)", text)
    assert m, "seed must contain reviewer_required_when_builders_gte"
    threshold = int(m.group(1))
    assert threshold >= 4, (
        f"reviewer_required_when_builders_gte must be >=4 for planner+builder minimal flow; got {threshold}"
    )


def test_seed_minimal_has_reviewer_fallback_planner():
    """seed_multi_team_minimal.py must set reviewer_fallback: planner."""
    seed_path = REPO_ROOT / "core" / "scripts" / "seed_multi_team_minimal.py"
    text = seed_path.read_text(encoding="utf-8")
    assert "reviewer_fallback" in text and "planner" in text, (
        "seed must set reviewer_fallback: planner for the minimal unit"
    )
