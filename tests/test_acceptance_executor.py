"""Tests for core/lib/acceptance_executor.py — v3 Phase 2."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "core" / "lib"))

from acceptance_executor import (  # noqa: E402
    AcceptanceError,
    aggregate_verdict,
    route_operator,
    route_reviewer,
    run_acceptance,
    run_mechanical,
    _resolve_task_worktree,
    _get_main_worktree_root,
    _redirect_cd_to_worktree,
)


def _write_brief(tmp_path: Path, project: str, team: str, task_id: str, brief_yaml: str) -> Path:
    brief_dir = tmp_path / ".agents" / "tasks" / project / team / "brief"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief = brief_dir / f"{task_id}.md"
    brief.write_text(f"---\n{brief_yaml}\n---\n\n# body\n", encoding="utf-8")
    return brief


@pytest.fixture
def env_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    monkeypatch.delenv("HOME", raising=False)
    return tmp_path


def test_mechanical_pass(env_home, tmp_path):
    _write_brief(env_home, "p", "t", "T1", """
task_id: T1
project: p
team: t
objective: "smoke"
seats_required: [builder]
acceptance_criteria:
  mechanical:
    - "true"
    - "echo hello"
""")
    results = run_acceptance(project="p", team="t", task_id="T1")
    assert results["mechanical"].verdict == "PASS"
    assert len(results["mechanical"].items) == 2
    assert all(i.result == "pass" for i in results["mechanical"].items)
    assert aggregate_verdict(results) == "PASS"


def test_mechanical_fail_propagates(env_home, tmp_path):
    _write_brief(env_home, "p", "t", "T2", """
task_id: T2
project: p
team: t
objective: "fail test"
seats_required: [builder]
acceptance_criteria:
  mechanical:
    - "true"
    - "false"
""")
    results = run_acceptance(project="p", team="t", task_id="T2")
    assert results["mechanical"].verdict == "FAIL"
    assert aggregate_verdict(results) == "FAIL"


def test_mechanical_captures_stdout_stderr(env_home, tmp_path):
    _write_brief(env_home, "p", "t", "T3", """
task_id: T3
project: p
team: t
objective: "capture"
seats_required: [builder]
acceptance_criteria:
  mechanical:
    - "echo good-stdout && echo bad-stderr >&2"
""")
    results = run_acceptance(project="p", team="t", task_id="T3")
    item = results["mechanical"].items[0]
    assert item.result == "pass"
    assert Path(item.stdout_path).read_text().strip() == "good-stdout"
    assert Path(item.stderr_path).read_text().strip() == "bad-stderr"


def test_reviewer_route_writes_dispatch_packet(env_home, tmp_path):
    _write_brief(env_home, "p", "t", "T4", """
task_id: T4
project: p
team: t
objective: "review"
seats_required: [builder, reviewer]
acceptance_criteria:
  mechanical: ["true"]
  reviewer:
    - "check code style"
    - "verify balance math"
""")
    results = run_acceptance(project="p", team="t", task_id="T4")
    assert results["reviewer"].verdict == "PENDING"
    packet_path = env_home / ".agents" / "tasks" / "p" / "t" / "acceptance" / "T4__reviewer.dispatch.json"
    packet = json.loads(packet_path.read_text())
    assert packet["reviewer_seat"] == "t-reviewer"
    assert len(packet["items"]) == 2
    assert "check code style" in packet["items"]


def test_operator_route_writes_pending_file(env_home, tmp_path):
    _write_brief(env_home, "p", "t", "T5", """
task_id: T5
project: p
team: t
objective: "image audit"
seats_required: [designer-image]
acceptance_criteria:
  mechanical: ["true"]
  operator:
    - "operator confirms card art style matches STS aesthetic"
    - "operator confirms boss intent telegraphing is clear"
""")
    results = run_acceptance(project="p", team="t", task_id="T5")
    assert results["operator"].verdict == "PENDING"
    pending = json.loads(
        (env_home / ".agents" / "tasks" / "p" / "t" / "acceptance" / "T5__operator.pending.json").read_text()
    )
    assert len(pending["questions"]) == 2
    assert pending["questions"][0]["answer"] is None


def test_aggregate_pending_when_mechanical_pass_but_others_pending(env_home, tmp_path):
    _write_brief(env_home, "p", "t", "T6", """
task_id: T6
project: p
team: t
objective: "mixed"
seats_required: [builder, reviewer]
acceptance_criteria:
  mechanical: ["true"]
  reviewer: ["check x"]
  operator: ["check y"]
""")
    results = run_acceptance(project="p", team="t", task_id="T6")
    assert results["mechanical"].verdict == "PASS"
    assert aggregate_verdict(results) == "PENDING"


def test_empty_mechanical_now_fails_schema(env_home, tmp_path):
    """Post-retest #2: empty mechanical no longer vacuously PASSes.
    Schema enforces minItems:1; executor raises AcceptanceError early.
    """
    _write_brief(env_home, "p", "t", "T7", """
task_id: T7
project: p
team: t
objective: "docs only"
seats_required: [builder]
acceptance_criteria:
  mechanical: []
""")
    with pytest.raises(AcceptanceError, match="mechanical"):
        run_acceptance(project="p", team="t", task_id="T7")


def test_missing_brief_raises(env_home, tmp_path):
    with pytest.raises(AcceptanceError, match="brief not found"):
        run_acceptance(project="p", team="t", task_id="DOES-NOT-EXIST")


def test_phase2A_rejects_brief_cli_mismatch(env_home, tmp_path):
    """Phase 2 fix #A: brief frontmatter must match CLI args."""
    _write_brief(env_home, "p", "t", "TMIS", """
task_id: OTHER
project: other-project
team: otherteam
objective: "mismatch test"
seats_required: [builder]
acceptance_criteria:
  mechanical: ["true"]
""")
    with pytest.raises(AcceptanceError, match="brief vs CLI mismatch"):
        run_acceptance(project="p", team="t", task_id="TMIS")


def test_phase2B_writes_consolidated_mechanical_log(env_home, tmp_path):
    """Phase 2 fix #B: __mechanical.log consolidated file written per spec §4.7.1."""
    _write_brief(env_home, "p", "t", "TLOG", """
task_id: TLOG
project: p
team: t
objective: "log test"
seats_required: [builder]
acceptance_criteria:
  mechanical:
    - "echo line1"
    - "false"
""")
    run_acceptance(project="p", team="t", task_id="TLOG")
    log_path = env_home / ".agents" / "tasks" / "p" / "t" / "acceptance" / "TLOG__mechanical.log"
    assert log_path.exists(), "consolidated mechanical.log must be written"
    content = log_path.read_text(encoding="utf-8")
    assert "Verdict: FAIL" in content
    assert "echo line1" in content
    assert "line1" in content  # captured stdout appears in consolidated log
    assert "Criterion #0" in content
    assert "Criterion #1" in content


def test_phase2C_reviewer_dispatch_called_when_items_present(env_home, tmp_path):
    """Phase 2 fix #C: reviewer route invokes dispatch_fn with packet."""
    _write_brief(env_home, "p", "t", "TREV", """
task_id: TREV
project: p
team: t
objective: "review dispatch"
seats_required: [reviewer]
acceptance_criteria:
  mechanical: ["true"]
  reviewer:
    - "audit balance"
""")
    captured = []

    def fake_dispatch(packet):
        captured.append(packet)
        return f"dispatched: fake-seq"

    results = run_acceptance(project="p", team="t", task_id="TREV", dispatch_fn=fake_dispatch)
    assert results["reviewer"].verdict == "PENDING"
    assert len(captured) == 1, "reviewer dispatch_fn must be invoked"
    assert captured[0]["task_id"] == "TREV"
    assert "audit balance" in captured[0]["items"]
    # Item dispatch_receipt records the call result
    assert "dispatched" in results["reviewer"].items[0].dispatch_receipt


def test_phase2C_reviewer_dispatch_skips_gracefully_no_profile(env_home, tmp_path):
    """When profile missing, executor must NOT hang; records skipped reason."""
    _write_brief(env_home, "p", "t", "TREVN", """
task_id: TREVN
project: p
team: t
objective: "no profile"
seats_required: [reviewer]
acceptance_criteria:
  mechanical: ["true"]
  reviewer: ["check"]
""")
    # Use default dispatch_fn (real one) — profile won't exist under tmp_path
    results = run_acceptance(project="p", team="t", task_id="TREVN")
    assert results["reviewer"].verdict == "PENDING"
    receipt = results["reviewer"].items[0].dispatch_receipt or ""
    assert "skipped" in receipt or "profile not found" in receipt, (
        f"expected graceful skip when profile missing, got: {receipt!r}"
    )


def test_receipts_persisted(env_home, tmp_path):
    _write_brief(env_home, "p", "t", "T8", """
task_id: T8
project: p
team: t
objective: "receipts"
seats_required: [builder]
acceptance_criteria:
  mechanical: ["true"]
""")
    run_acceptance(project="p", team="t", task_id="T8")
    acceptance_dir = env_home / ".agents" / "tasks" / "p" / "t" / "acceptance"
    assert (acceptance_dir / "T8__mechanical.json").exists()
    assert (acceptance_dir / "T8__reviewer.json").exists()
    assert (acceptance_dir / "T8__operator.json").exists()
    mech_receipt = json.loads((acceptance_dir / "T8__mechanical.json").read_text())
    assert mech_receipt["verdict"] == "PASS"
    assert mech_receipt["summary"]["pass"] == 1


# ---------------------------------------------------------------------------
# cf018: worktree CWD auto-resolution
# ---------------------------------------------------------------------------

def _write_dispatch_receipt(
    env_home: Path,
    project: str,
    task_id: str,
    worktree_path: Path,
) -> Path:
    """Write a fake dispatch receipt with expected_worktree_path."""
    handoffs = env_home / ".agents" / "tasks" / project / "patrol" / "handoffs"
    handoffs.mkdir(parents=True, exist_ok=True)
    receipt_path = handoffs / f"{task_id}__planner__builder.json"
    receipt_path.write_text(
        json.dumps({
            "kind": "dispatch",
            "task_id": task_id,
            "source": "planner",
            "target": "builder",
            "expected_worktree_path": str(worktree_path),
        }),
        encoding="utf-8",
    )
    return receipt_path


def test_resolve_task_worktree_returns_path_when_exists(env_home, tmp_path):
    """_resolve_task_worktree returns the dispatch-receipt worktree when it exists."""
    agents_root = env_home / ".agents"
    wt = tmp_path / "task-wt"
    wt.mkdir()
    _write_dispatch_receipt(env_home, "p", "TWR1", wt)
    resolved = _resolve_task_worktree("TWR1", agents_root, "p")
    assert resolved == wt


def test_resolve_task_worktree_returns_none_when_absent(env_home, tmp_path):
    """_resolve_task_worktree returns None when worktree path does not exist."""
    agents_root = env_home / ".agents"
    wt = tmp_path / "missing-wt"  # does not exist
    _write_dispatch_receipt(env_home, "p", "TWR2", wt)
    resolved = _resolve_task_worktree("TWR2", agents_root, "p")
    assert resolved is None


def test_resolve_task_worktree_returns_none_when_no_receipt(env_home):
    """_resolve_task_worktree returns None when no handoffs exist."""
    agents_root = env_home / ".agents"
    resolved = _resolve_task_worktree("TWR_NONE", agents_root, "p")
    assert resolved is None


def test_run_acceptance_uses_task_worktree_not_main(env_home, tmp_path):
    """cf018 regression: acceptance must run mechanical commands in task worktree.

    Creates two directories: a fake 'main worktree' (no sentinel) and a
    fake 'task worktree' (has sentinel). Brief command checks the sentinel.
    Without the fix the command would run in the Python process CWD and fail;
    with the fix it runs in the task worktree and passes.
    """
    project, team, task_id = "p", "t", "TCF018"

    # Task worktree has a sentinel file
    task_wt = tmp_path / "task-wt"
    task_wt.mkdir()
    (task_wt / "SENTINEL_cf018").write_text("present", encoding="utf-8")

    # Write dispatch receipt pointing at task_wt
    _write_dispatch_receipt(env_home, project, task_id, task_wt)

    # Brief: verify sentinel exists (passes only in task worktree)
    _write_brief(env_home, project, team, task_id, f"""
task_id: {task_id}
project: {project}
team: {team}
objective: worktree CWD test
seats_required: [builder]
acceptance_criteria:
  mechanical:
    - "test -f SENTINEL_cf018"
""")

    # run_acceptance with no explicit cwd — must auto-resolve to task_wt
    results = run_acceptance(project=project, team=team, task_id=task_id, dispatch_fn=lambda p: "fake")
    item = results["mechanical"].items[0]
    assert item.result == "pass", (
        f"acceptance must run in task worktree where SENTINEL_cf018 exists; "
        f"got result={item.result!r} — worktree CWD was not resolved"
    )
    assert results["mechanical"].verdict == "PASS"


# ---------------------------------------------------------------------------
# cf018 REPAIR: absolute cd prefix redirect
# ---------------------------------------------------------------------------

def test_redirect_cd_to_worktree_rewrites_main_root(tmp_path):
    """_redirect_cd_to_worktree rewrites cd to main root → task worktree."""
    main_root = tmp_path / "main"
    task_wt = tmp_path / "task-wt"
    cmd = f"cd {main_root} && npm test"
    result = _redirect_cd_to_worktree(cmd, main_root, task_wt)
    assert str(task_wt) in result
    assert str(main_root) not in result
    assert "npm test" in result


def test_redirect_cd_to_worktree_rewrites_subdir(tmp_path):
    """_redirect_cd_to_worktree rewrites cd to main subdir → task worktree subdir."""
    main_root = tmp_path / "main"
    task_wt = tmp_path / "task-wt"
    cmd = f"cd {main_root}/apps/web && pnpm test"
    result = _redirect_cd_to_worktree(cmd, main_root, task_wt)
    assert f"{task_wt}/apps/web" in result
    assert str(main_root) not in result


def test_redirect_cd_to_worktree_leaves_unrelated_path(tmp_path):
    """_redirect_cd_to_worktree leaves cd to unrelated absolute path intact."""
    main_root = tmp_path / "main"
    task_wt = tmp_path / "task-wt"
    cmd = "cd /usr/local/bin && ls"
    result = _redirect_cd_to_worktree(cmd, main_root, task_wt)
    assert result == cmd


def test_redirect_cd_to_worktree_leaves_relative_cmd(tmp_path):
    """_redirect_cd_to_worktree leaves commands without absolute cd unchanged."""
    main_root = tmp_path / "main"
    task_wt = tmp_path / "task-wt"
    cmd = "npm test"
    assert _redirect_cd_to_worktree(cmd, main_root, task_wt) == cmd


def test_get_main_worktree_root_returns_none_for_plain_dir(tmp_path):
    """_get_main_worktree_root returns None when no .git file present."""
    assert _get_main_worktree_root(tmp_path) is None


def test_acceptance_uses_task_worktree_for_absolute_cd_command(env_home, tmp_path):
    """cf018 REPAIR regression: absolute cd to main root must redirect to task worktree.

    al541-shaped scenario: mechanical command is 'cd /main/repo && test -f SENTINEL'.
    Sentinel exists only in task worktree. Without redirect → FAIL; with → PASS.
    We use _redirect_cd_to_worktree directly via run_mechanical with explicit
    main_root injection to avoid needing a real git worktree in tests.
    """
    from pathlib import Path
    from acceptance_executor import run_mechanical, RouteResult

    # Set up task worktree with sentinel
    task_wt = tmp_path / "task-wt"
    task_wt.mkdir()
    (task_wt / "SENTINEL_al541").write_text("present", encoding="utf-8")

    # Fake main root (no sentinel here)
    main_root = tmp_path / "main-repo"
    main_root.mkdir()

    acc_dir = env_home / ".agents" / "tasks" / "p" / "t" / "acceptance"
    brief = {
        "acceptance_criteria": {
            "mechanical": [f"cd {main_root} && test -f SENTINEL_al541"]
        }
    }

    # Without redirect: runs in main_root → fails (no sentinel)
    result_no_redirect = run_mechanical(
        brief, acc_dir, "TAL541_no", cwd=None,
        pre_split_mech=[f"cd {main_root} && test -f SENTINEL_al541"],
    )
    assert result_no_redirect.verdict == "FAIL", (
        "without worktree redirect, command should fail (sentinel not in main root)"
    )

    # With redirect applied manually (simulating the full pipeline):
    # The redirect rewrites 'cd /main-repo &&...' to 'cd /task-wt &&...'
    redirected_cmd = _redirect_cd_to_worktree(
        f"cd {main_root} && test -f SENTINEL_al541", main_root, task_wt
    )
    assert str(task_wt) in redirected_cmd

    result_with_redirect = run_mechanical(
        brief, acc_dir, "TAL541_yes", cwd=task_wt,
        pre_split_mech=[redirected_cmd],
    )
    assert result_with_redirect.verdict == "PASS", (
        "with worktree redirect, command must pass (sentinel found in task worktree)"
    )
