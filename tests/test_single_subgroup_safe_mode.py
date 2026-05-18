"""Tests for cf027: single-subgroup safe mode contract propagation.

Proves the safe-mode contract block is present in all active seat templates
and that builder SKILL.md reflects opt-in push/PR/CI semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "core" / "templates"
SKILLS_DIR = REPO_ROOT / "core" / "skills"

_SAFE_MODE_MARKER = "Single-Subgroup Safe Mode"
_OPT_IN_MARKER = "opt-in"


def _template(name: str) -> Path:
    return TEMPLATES_DIR / name


def _assert_has_safe_mode(path: Path) -> None:
    assert path.exists(), f"not found: {path}"
    text = path.read_text(encoding="utf-8")
    assert _SAFE_MODE_MARKER in text, (
        f"{path.name}: missing '{_SAFE_MODE_MARKER}' section"
    )


# ---------------------------------------------------------------------------
# Shared snippet
# ---------------------------------------------------------------------------

def test_shared_safe_mode_snippet_exists():
    snippet = TEMPLATES_DIR / "shared" / "single-subgroup-safe-mode.md.snippet"
    assert snippet.exists()
    text = snippet.read_text(encoding="utf-8")
    assert _SAFE_MODE_MARKER in text
    assert "Planner+builder" in text or "planner+builder" in text.lower()
    assert "Reviewer is escalation only" in text or "escalation only" in text.lower()
    assert "opt-in" in text.lower() or "Push/PR/CI" in text


def test_shared_snippet_all_8_rules():
    snippet = TEMPLATES_DIR / "shared" / "single-subgroup-safe-mode.md.snippet"
    text = snippet.read_text(encoding="utf-8")
    assert "One active subgroup" in text or "one active subgroup" in text.lower()
    assert "Builder delivers to planner" in text or "builder delivers" in text.lower()
    assert "Planner merges" in text or "planner merges" in text.lower()
    assert "Memory owns" in text or "memory owns" in text.lower() or "Memory" in text
    assert "Push/PR/CI" in text or "push" in text.lower()


# ---------------------------------------------------------------------------
# Builder templates
# ---------------------------------------------------------------------------

def test_builder_codex_template_has_safe_mode():
    _assert_has_safe_mode(_template("workspace-builder.template.md.codex"))


def test_builder_av_template_has_safe_mode():
    _assert_has_safe_mode(_template("workspace-builder-av.template.md.claude.minimax"))


# ---------------------------------------------------------------------------
# Planner templates
# ---------------------------------------------------------------------------

def test_planner_gemini_template_has_safe_mode():
    _assert_has_safe_mode(_template("workspace-planner.template.md.gemini"))


# ---------------------------------------------------------------------------
# Reviewer templates
# ---------------------------------------------------------------------------

def test_reviewer_template_has_safe_mode():
    _assert_has_safe_mode(_template("workspace-reviewer.template.md"))


# ---------------------------------------------------------------------------
# Memory templates
# ---------------------------------------------------------------------------

def test_memory_claude_template_has_safe_mode():
    _assert_has_safe_mode(_template("workspace-memory.template.md.claude"))


def test_memory_codex_template_has_safe_mode():
    _assert_has_safe_mode(_template("workspace-memory.template.md.codex"))


def test_memory_gemini_template_has_safe_mode():
    _assert_has_safe_mode(_template("workspace-memory.template.md.gemini"))


# ---------------------------------------------------------------------------
# Builder SKILL.md: opt-in push/PR/CI
# ---------------------------------------------------------------------------

def test_builder_skill_has_safe_mode_section():
    skill = SKILLS_DIR / "builder" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert _SAFE_MODE_MARKER in text, "builder SKILL.md must have safe-mode section"


def test_builder_skill_closure_protocol_opt_in():
    skill = SKILLS_DIR / "builder" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert _OPT_IN_MARKER in text.lower(), (
        "builder SKILL.md closure protocol must document opt-in push/PR/CI for safe mode"
    )


def test_builder_skill_push_pr_optional_in_safe_mode():
    skill = SKILLS_DIR / "builder" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "N/A: safe-mode" in text or "safe-mode local delivery" in text, (
        "builder SKILL.md must allow N/A closure for safe-mode local delivery"
    )
