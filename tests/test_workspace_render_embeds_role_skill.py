"""Root-cause fix verification: bootstrap-rendered workspace files must
embed the canonical role SKILL.md content.

Before 2026-04-24, `agent_admin_template.py` rendered AGENTS.md / CLAUDE.md
/ GEMINI.md purely from engineer.toml fields (mostly empty: `skills=[]`,
a single-line role_details). The authoritative role contract lived in
`core/skills/<role>/SKILL.md` (60-190 lines each) but was never consumed
by the render pipeline — so seats launched with 10-line stub workspaces
and didn't actually know their role.

This test pins the fix: the renderer now appends a `## Role SKILL
(canonical)` section sourced directly from `core/skills/<role>/SKILL.md`,
with `seat_skill_mapping.role_skill_for_seat` handling the seat→role
mapping (e.g. `memory -> memory-oracle`, `builder-1 -> builder`).
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parents[1]
_CORE_SCRIPTS = _REPO / "core" / "scripts"
if str(_CORE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CORE_SCRIPTS))

import agent_admin_template  # noqa: E402


# ── helper-level tests ────────────────────────────────────────────────


def test_load_role_skill_content_strips_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "core" / "skills" / "builder"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: builder
            description: test role
            ---

            # Builder

            身份约束
            1. test constraint
            """
        ),
        encoding="utf-8",
    )
    info = agent_admin_template._load_role_skill_content(tmp_path, "builder")
    assert info is not None
    role, body = info
    assert role == "builder"
    # frontmatter stripped
    assert body.startswith("# Builder"), body[:60]
    assert "description: test role" not in body
    assert "身份约束" in body


def test_load_role_skill_content_handles_no_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "core" / "skills" / "qa"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# QA\n\nbody only.\n", encoding="utf-8")
    info = agent_admin_template._load_role_skill_content(tmp_path, "qa")
    assert info is not None
    role, body = info
    assert role == "qa"
    assert body.startswith("# QA")


def test_load_role_skill_content_returns_none_for_unknown_seat(tmp_path: Path) -> None:
    # No core/skills/* directory at all
    assert agent_admin_template._load_role_skill_content(tmp_path, "not-a-seat") is None


def test_load_role_skill_content_follows_memory_mapping(tmp_path: Path) -> None:
    """`memory` seat -> `memory-oracle` skill per seat_skill_mapping."""
    skill_dir = tmp_path / "core" / "skills" / "memory-oracle"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# memory-oracle\n", encoding="utf-8")
    info = agent_admin_template._load_role_skill_content(tmp_path, "memory")
    assert info is not None
    role, _ = info
    assert role == "memory-oracle"


def test_load_role_skill_content_handles_suffixed_seat_id(tmp_path: Path) -> None:
    """`builder-1` / `reviewer-2` should resolve to their base role skill."""
    skill_dir = tmp_path / "core" / "skills" / "builder"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# builder variant\n", encoding="utf-8")
    info = agent_admin_template._load_role_skill_content(tmp_path, "builder-1")
    assert info is not None
    assert info[0] == "builder"


def test_load_role_skill_content_role_hint_overrides_seat_id_mapping(tmp_path: Path) -> None:
    """role_hint wins over seat-id mapping (creative template: builder seat → creative-builder skill)."""
    # Set up both the generic and the creative-specific skill
    (tmp_path / "core" / "skills" / "builder").mkdir(parents=True)
    (tmp_path / "core" / "skills" / "builder" / "SKILL.md").write_text("# Builder (engineering)\n", encoding="utf-8")
    (tmp_path / "core" / "skills" / "creative-builder").mkdir(parents=True)
    (tmp_path / "core" / "skills" / "creative-builder" / "SKILL.md").write_text(
        "---\nname: creative-builder\n---\n# Creative Builder\n\ncreative skill body\n",
        encoding="utf-8",
    )
    info = agent_admin_template._load_role_skill_content(tmp_path, "builder", role_hint="creative-builder")
    assert info is not None
    role, body = info
    assert role == "creative-builder", f"expected creative-builder, got {role!r}"
    assert "creative skill body" in body
    assert "engineering" not in body


def test_load_role_skill_content_role_hint_falls_back_when_skill_missing(tmp_path: Path) -> None:
    """When role_hint SKILL.md doesn't exist, falls back to seat-id mapping."""
    (tmp_path / "core" / "skills" / "builder").mkdir(parents=True)
    (tmp_path / "core" / "skills" / "builder" / "SKILL.md").write_text("# Builder fallback\n", encoding="utf-8")
    # no creative-builder dir
    info = agent_admin_template._load_role_skill_content(tmp_path, "builder", role_hint="creative-builder")
    assert info is not None
    role, body = info
    assert role == "builder"
    assert "Builder fallback" in body


def test_role_skill_section_lines_empty_when_missing(tmp_path: Path) -> None:
    assert agent_admin_template._role_skill_section_lines(tmp_path, "unknown-seat") == []


def test_role_skill_section_lines_contains_canonical_header(tmp_path: Path) -> None:
    skill_dir = tmp_path / "core" / "skills" / "reviewer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: reviewer\n---\n# Reviewer\n\nVerdict rules here.\n",
        encoding="utf-8",
    )
    lines = agent_admin_template._role_skill_section_lines(tmp_path, "reviewer")
    assert "## Role SKILL (canonical)" in lines
    joined = "\n".join(lines)
    assert "core/skills/reviewer/SKILL.md" in joined
    assert "Verdict rules here." in joined


# ── integration with the real repo's core/skills ──────────────────────


@pytest.mark.parametrize(
    ("seat_id", "expected_role"),
    [
        ("planner", "planner"),
        ("builder", "builder"),
        ("reviewer", "reviewer"),
        ("qa", "qa"),
        ("designer", "designer"),
        ("memory", "memory-oracle"),
        ("ancestor", "clawseat-ancestor"),
    ],
)
def test_real_repo_role_skills_load_for_canonical_seats(seat_id: str, expected_role: str) -> None:
    """All canonical ClawSeat seats must have a loadable role SKILL.md."""
    info = agent_admin_template._load_role_skill_content(_REPO, seat_id)
    assert info is not None, (
        f"seat {seat_id!r} should map to a role skill; missing core/skills/{expected_role}/SKILL.md?"
    )
    role, body = info
    assert role == expected_role
    assert len(body) > 100, f"{expected_role} SKILL.md should not be an empty stub"
    # A rendered role skill must not leak its frontmatter
    assert not body.startswith("---\n"), f"{expected_role} SKILL.md frontmatter not stripped"


@pytest.mark.parametrize(
    ("seat_id", "role_hint", "expected_role", "expected_marker"),
    [
        ("builder", "creative-builder", "creative-builder", "cs-classify"),
        ("designer", "creative-designer", "creative-designer", "cs-score"),
        ("planner", "creative-planner", "creative-planner", "cs-structure"),
    ],
)
def test_real_repo_creative_seats_load_correct_skill_via_role_hint(
    seat_id: str, role_hint: str, expected_role: str, expected_marker: str
) -> None:
    """Creative template seats (builder/designer/planner) must load their
    creative-* SKILL.md when the template role is passed as role_hint."""
    info = agent_admin_template._load_role_skill_content(_REPO, seat_id, role_hint=role_hint)
    assert info is not None, f"creative seat {seat_id!r} with role_hint={role_hint!r} should resolve"
    role, body = info
    assert role == expected_role, f"expected {expected_role!r}, got {role!r}"
    assert expected_marker in body, f"{expected_role} SKILL.md should mention {expected_marker!r}"
    assert not body.startswith("---\n"), "frontmatter must be stripped"


def test_real_repo_role_skill_section_for_qa_includes_contract_marker() -> None:
    """Pin a distinctive QA SKILL.md marker so deleting the contract fails this test."""
    lines = agent_admin_template._role_skill_section_lines(_REPO, "qa")
    joined = "\n".join(lines)
    assert "## Role SKILL (canonical)" in joined
    # QA contract must carry the no-author-new-tests constraint
    assert "不写新 tests" in joined or "write new tests" in joined.lower()


def test_real_repo_role_skill_section_for_planner_includes_contract_marker() -> None:
    lines = agent_admin_template._role_skill_section_lines(_REPO, "planner")
    joined = "\n".join(lines)
    assert "## Role SKILL (canonical)" in joined
    # Planner is dispatcher; SKILL.md states identity constraint
    assert "planner" in joined.lower()
    # Should be non-trivial in size (>500 chars embedded)
    embedded_size = len(joined)
    assert embedded_size > 500, f"planner workspace embed unexpectedly small: {embedded_size}"
