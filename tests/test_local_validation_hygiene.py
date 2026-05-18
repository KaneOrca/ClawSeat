"""Tests for cf025: local review/latest validation hygiene.

Covers:
1. node_modules path guard in brief acceptance
2. Dirty-worktree awareness helpers
3. validation-branch-contract.md contains local-first guidance
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "core" / "lib"))

from acceptance_criteria import (  # noqa: E402
    brief_acceptance_ready,
    has_node_modules_path,
    is_dirty_worktree_check,
)


# ---------------------------------------------------------------------------
# has_node_modules_path
# ---------------------------------------------------------------------------

def test_node_modules_detected_in_git_add():
    assert has_node_modules_path("git add node_modules/")

def test_node_modules_detected_in_diff():
    assert has_node_modules_path("git diff --name-only | grep node_modules")

def test_node_modules_detected_in_path():
    assert has_node_modules_path("ls apps/web/node_modules/some-pkg")

def test_node_modules_not_detected_in_clean_command():
    assert not has_node_modules_path("npm test -- --runInBand")

def test_node_modules_not_detected_in_empty():
    assert not has_node_modules_path("")


# ---------------------------------------------------------------------------
# is_dirty_worktree_check
# ---------------------------------------------------------------------------

def test_dirty_check_detects_git_status():
    assert is_dirty_worktree_check("git status")

def test_dirty_check_detects_git_diff_stat():
    assert is_dirty_worktree_check("git diff --stat")

def test_dirty_check_detects_git_diff_cached():
    assert is_dirty_worktree_check("git diff --cached")

def test_dirty_check_detects_ls_files_modified():
    assert is_dirty_worktree_check("git ls-files --modified")

def test_dirty_check_passes_for_test_command():
    assert not is_dirty_worktree_check("npm test")

def test_dirty_check_passes_for_empty():
    assert not is_dirty_worktree_check("")


# ---------------------------------------------------------------------------
# brief_acceptance_ready: node_modules path rejected
# ---------------------------------------------------------------------------

def test_brief_ready_rejects_node_modules_in_command():
    brief = {
        "acceptance_criteria": {
            "mechanical": [
                "git diff --name-only origin/main...HEAD | grep node_modules"
            ]
        },
        "seats_required": ["builder"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert not ready
    assert "node_modules" in reason

def test_brief_ready_accepts_command_without_node_modules():
    brief = {
        "acceptance_criteria": {
            "mechanical": [
                "cd /repo && pnpm test"
            ]
        },
        "seats_required": ["builder"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert ready, f"expected ready; got: {reason}"


# ---------------------------------------------------------------------------
# validation-branch-contract.md: local-first guidance present
# ---------------------------------------------------------------------------

def test_validation_contract_doc_has_local_first_section():
    ref = REPO_ROOT / "core" / "references" / "validation-branch-contract.md"
    assert ref.exists()
    text = ref.read_text(encoding="utf-8")
    assert "local" in text.lower() and "remote push" in text.lower(), (
        "validation-branch-contract.md must document local-first validation "
        "and that remote push is not required for operator testing"
    )

def test_validation_contract_doc_mentions_dirty_worktree():
    ref = REPO_ROOT / "core" / "references" / "validation-branch-contract.md"
    text = ref.read_text(encoding="utf-8")
    assert "dirty" in text.lower() or "git status" in text.lower(), (
        "validation-branch-contract.md must mention dirty-worktree awareness"
    )

def test_validation_contract_doc_local_port():
    ref = REPO_ROOT / "core" / "references" / "validation-branch-contract.md"
    text = ref.read_text(encoding="utf-8")
    assert "15173" in text, "validation-branch-contract.md must document local validation port"
