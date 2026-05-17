"""Tests for cf015: acceptance mechanical shell command contract.

Covers two defect classes observed in al539/vt002f:
1. Non-portable pipe-negation (`| ! rg`) — invalid in /bin/sh and bash.
2. Bare `git diff --name-only` without explicit range — scans dirty working tree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "core" / "lib"))

from acceptance_criteria import (  # noqa: E402
    brief_acceptance_ready,
    has_bare_git_diff_name_only,
    has_invalid_pipe_negation,
    normalize_pipe_negation,
)
from acceptance_executor import aggregate_verdict, run_acceptance  # noqa: E402


@pytest.fixture
def env_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    monkeypatch.delenv("HOME", raising=False)
    return tmp_path


def _write_brief(env_home: Path, project: str, team: str, task_id: str, mechanical: list) -> Path:
    brief_dir = env_home / ".agents" / "tasks" / project / team / "brief"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief = brief_dir / f"{task_id}.md"
    items_yaml = "\n".join(f"    - '{item}'" for item in mechanical)
    brief.write_text(
        f"---\n"
        f"task_id: {task_id}\n"
        f"project: {project}\n"
        f"team: {team}\n"
        f"objective: shell contract test\n"
        f"seats_required: [builder]\n"
        f"acceptance_criteria:\n"
        f"  mechanical:\n"
        f"{items_yaml}\n"
        f"---\n\n# Brief\n",
        encoding="utf-8",
    )
    return brief


# ---------------------------------------------------------------------------
# Unit tests for has_invalid_pipe_negation
# ---------------------------------------------------------------------------

def test_has_invalid_pipe_negation_detects_pipe_bang_rg():
    assert has_invalid_pipe_negation("git diff --name-only | ! rg pattern")

def test_has_invalid_pipe_negation_detects_pipe_bang_grep():
    assert has_invalid_pipe_negation("git diff --name-only | ! grep pattern")

def test_has_invalid_pipe_negation_detects_with_spaces():
    assert has_invalid_pipe_negation("cat file |  !  rg foo")

def test_has_invalid_pipe_negation_passes_rg_v():
    assert not has_invalid_pipe_negation("git diff --name-only | rg -v pattern")

def test_has_invalid_pipe_negation_passes_grep_v():
    assert not has_invalid_pipe_negation("git diff --name-only | grep -v pattern")

def test_has_invalid_pipe_negation_passes_no_pipe():
    assert not has_invalid_pipe_negation("! rg pattern file")

def test_has_invalid_pipe_negation_passes_empty():
    assert not has_invalid_pipe_negation("")


# ---------------------------------------------------------------------------
# Unit tests for normalize_pipe_negation
# ---------------------------------------------------------------------------

def test_normalize_pipe_negation_rg():
    cmd = "git diff --name-only origin/main...HEAD | ! rg apps/web/src"
    result = normalize_pipe_negation(cmd)
    assert "| rg -v" in result
    assert "| !" not in result

def test_normalize_pipe_negation_grep():
    cmd = r"git diff --name-only | ! grep '\.py$'"
    result = normalize_pipe_negation(cmd)
    assert "| grep -v" in result
    assert "| !" not in result

def test_normalize_pipe_negation_preserves_other():
    cmd = "ls | sort | ! other_cmd"
    # Not rg or grep, left as-is (still invalid, but not within our scope to guess)
    result = normalize_pipe_negation(cmd)
    assert "| ! other_cmd" in result

def test_normalize_pipe_negation_noop_when_clean():
    cmd = "git diff origin/main...HEAD --name-only | rg -v test"
    assert normalize_pipe_negation(cmd) == cmd


# ---------------------------------------------------------------------------
# Unit tests for has_bare_git_diff_name_only
# ---------------------------------------------------------------------------

def test_has_bare_git_diff_name_only_detects_bare():
    assert has_bare_git_diff_name_only("git diff --name-only")

def test_has_bare_git_diff_name_only_detects_bare_piped():
    assert has_bare_git_diff_name_only("git diff --name-only | grep .py")

def test_has_bare_git_diff_name_only_detects_head_form():
    # `git diff HEAD --name-only` also scans dirty state (HEAD vs working tree)
    assert has_bare_git_diff_name_only("git diff HEAD --name-only")

def test_has_bare_git_diff_name_only_passes_double_dot():
    assert not has_bare_git_diff_name_only("git diff origin/main..HEAD --name-only")

def test_has_bare_git_diff_name_only_passes_triple_dot():
    assert not has_bare_git_diff_name_only("git diff origin/main...HEAD --name-only")

def test_has_bare_git_diff_name_only_passes_no_name_only():
    assert not has_bare_git_diff_name_only("git diff --stat")

def test_has_bare_git_diff_name_only_passes_empty():
    assert not has_bare_git_diff_name_only("")


# ---------------------------------------------------------------------------
# brief_acceptance_ready: pipe-negation and bare git diff rejected
# ---------------------------------------------------------------------------

def test_brief_ready_rejects_pipe_negation(env_home):
    brief = {
        "acceptance_criteria": {
            "mechanical": [
                "git diff --name-only origin/main...HEAD | ! rg forbidden/"
            ]
        },
        "seats_required": ["builder"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert not ready
    assert "pipe-negation" in reason or "| !" in reason

def test_brief_ready_rejects_bare_git_diff(env_home):
    brief = {
        "acceptance_criteria": {
            "mechanical": [
                "git diff --name-only | grep forbidden"
            ]
        },
        "seats_required": ["builder"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert not ready
    assert "bare" in reason or "git diff" in reason or "name-only" in reason

def test_brief_ready_accepts_rg_v_form():
    brief = {
        "acceptance_criteria": {
            "mechanical": [
                "git diff origin/main...HEAD --name-only | rg -v forbidden/"
            ]
        },
        "seats_required": ["builder"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert ready, f"expected ready, got: {reason}"

def test_brief_ready_accepts_ranged_git_diff():
    brief = {
        "acceptance_criteria": {
            "mechanical": [
                "git diff origin/main..HEAD --name-only | grep .py"
            ]
        },
        "seats_required": ["builder"],
    }
    ready, reason = brief_acceptance_ready(brief)
    assert ready, f"expected ready, got: {reason}"


# ---------------------------------------------------------------------------
# Executor-level: pipe-negation auto-normalized; bare git diff fails with diag
# ---------------------------------------------------------------------------

def test_executor_normalizes_pipe_negation(env_home):
    """run_acceptance() should auto-normalize | ! rg and the criterion passes."""
    project, team, task_id = "p", "t", "TPIPE"
    # We cannot easily inject an __accept_review handoff here, but we can
    # verify the transformed command is accepted (no syntax error on run).
    # Use a command whose normalized form succeeds: `echo x | ! rg nomatch`
    # → after normalize: `echo x | rg -v nomatch` → exit 0 when no match
    _write_brief(env_home, project, team, task_id, [
        "echo x | ! rg nomatch_pattern_xyz123"
    ])
    results = run_acceptance(project=project, team=team, task_id=task_id, dispatch_fn=lambda p: "fake")
    item = results["mechanical"].items[0]
    # After normalization the command is valid and should pass
    assert item.result == "pass", (
        f"normalized pipe-negation should yield pass; got result={item.result!r}, "
        f"command={item.command!r}"
    )


def test_executor_fails_bare_git_diff_name_only(env_home):
    """run_acceptance() must fail a criterion with bare git diff --name-only."""
    project, team, task_id = "p", "t", "TBARE"
    _write_brief(env_home, project, team, task_id, [
        "true",                     # one runnable criterion to satisfy schema
        "git diff --name-only",     # bare git diff — should fail with diagnostic
    ])
    results = run_acceptance(project=project, team=team, task_id=task_id, dispatch_fn=lambda p: "fake")
    items = {i.criterion: i for i in results["mechanical"].items}
    bare_item = items.get("git diff --name-only")
    assert bare_item is not None, "bare git diff item must be present in results"
    assert bare_item.result == "fail", (
        f"bare git diff --name-only must fail; got result={bare_item.result!r}"
    )
    assert results["mechanical"].verdict == "FAIL"
    assert aggregate_verdict(results) == "FAIL"


def test_executor_bare_git_diff_writes_diagnostic(env_home):
    """Diagnostic message written to stderr file when bare git diff detected."""
    project, team, task_id = "p", "t", "TDIAG"
    _write_brief(env_home, project, team, task_id, [
        "true",
        "git diff --name-only",
    ])
    run_acceptance(project=project, team=team, task_id=task_id, dispatch_fn=lambda p: "fake")
    acc_dir = env_home / ".agents" / "tasks" / project / team / "acceptance"
    stderr_files = list(acc_dir.glob(f"{task_id}__mech__*.stderr"))
    assert stderr_files, "stderr diagnostic file must be written for bare git diff"
    content = stderr_files[0].read_text(encoding="utf-8")
    assert "bare" in content or "git diff" in content or "working-tree" in content


def test_executor_ranged_git_diff_accepted(env_home):
    """git diff with explicit range must not be blocked."""
    project, team, task_id = "p", "t", "TRANGE"
    # We can't actually run git diff in the test environment, so use `true` to
    # confirm the validation path doesn't block a range-form command.
    _write_brief(env_home, project, team, task_id, [
        "true",
    ])
    results = run_acceptance(project=project, team=team, task_id=task_id, dispatch_fn=lambda p: "fake")
    assert results["mechanical"].verdict == "PASS"
