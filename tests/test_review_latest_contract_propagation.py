"""Tests for cf026: review/latest contract propagation into workspace templates.

Proves that all active tool-path templates include the review/latest validation
contract block so external agents (Claude, Codex, Gemini) see the rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "core" / "templates"

_CONTRACT_MARKER = "Review/Latest Validation Contract"
_LOCAL_MARKER = "review/latest"
_MAIN_PROTECTED_MARKER = "main"


def _template(name: str) -> Path:
    return TEMPLATES_DIR / name


def _assert_has_contract(path: Path) -> None:
    assert path.exists(), f"template not found: {path}"
    text = path.read_text(encoding="utf-8")
    assert _CONTRACT_MARKER in text, (
        f"{path.name}: missing '{_CONTRACT_MARKER}' section"
    )
    assert _LOCAL_MARKER in text, (
        f"{path.name}: missing 'review/latest' reference"
    )
    assert _MAIN_PROTECTED_MARKER in text, (
        f"{path.name}: missing 'main' protection reference"
    )


# ---------------------------------------------------------------------------
# Shared snippet exists
# ---------------------------------------------------------------------------

def test_shared_contract_snippet_exists():
    snippet = TEMPLATES_DIR / "shared" / "review-latest-contract.md.snippet"
    assert snippet.exists(), "shared review-latest-contract.md.snippet must exist"
    text = snippet.read_text(encoding="utf-8")
    assert _CONTRACT_MARKER in text
    assert "review/latest" in text
    assert "memory" in text.lower()


# ---------------------------------------------------------------------------
# Builder templates
# ---------------------------------------------------------------------------

def test_builder_codex_template_has_contract():
    _assert_has_contract(_template("workspace-builder.template.md.codex"))


def test_builder_av_template_has_contract():
    _assert_has_contract(_template("workspace-builder-av.template.md.claude.minimax"))


# ---------------------------------------------------------------------------
# Planner templates
# ---------------------------------------------------------------------------

def test_planner_gemini_template_has_contract():
    _assert_has_contract(_template("workspace-planner.template.md.gemini"))


# ---------------------------------------------------------------------------
# Reviewer templates
# ---------------------------------------------------------------------------

def test_reviewer_template_has_contract():
    _assert_has_contract(_template("workspace-reviewer.template.md"))


# ---------------------------------------------------------------------------
# Memory templates (all three tool variants)
# ---------------------------------------------------------------------------

def test_memory_claude_template_has_contract():
    _assert_has_contract(_template("workspace-memory.template.md.claude"))


def test_memory_codex_template_has_contract():
    _assert_has_contract(_template("workspace-memory.template.md.codex"))


def test_memory_gemini_template_has_contract():
    _assert_has_contract(_template("workspace-memory.template.md.gemini"))


# ---------------------------------------------------------------------------
# Contract content: all required rules present in shared snippet
# ---------------------------------------------------------------------------

def test_shared_snippet_covers_builder_delivery_step():
    snippet = TEMPLATES_DIR / "shared" / "review-latest-contract.md.snippet"
    text = snippet.read_text(encoding="utf-8")
    assert "builder" in text.lower() or "Builder" in text

def test_shared_snippet_covers_planner_merge_step():
    snippet = TEMPLATES_DIR / "shared" / "review-latest-contract.md.snippet"
    text = snippet.read_text(encoding="utf-8")
    assert "planner" in text.lower() or "Planner" in text

def test_shared_snippet_covers_operator_validation():
    snippet = TEMPLATES_DIR / "shared" / "review-latest-contract.md.snippet"
    text = snippet.read_text(encoding="utf-8")
    assert "operator" in text.lower() or "Operator" in text

def test_shared_snippet_remote_push_optional():
    snippet = TEMPLATES_DIR / "shared" / "review-latest-contract.md.snippet"
    text = snippet.read_text(encoding="utf-8")
    assert "optional" in text.lower() or "not required" in text.lower()
