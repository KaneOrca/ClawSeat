from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "core" / "skills" / "memory-oracle" / "scripts" / "audit_planner_closeout.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("audit_planner_closeout", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_profile(
    path: Path,
    *,
    handoff_dir: str,
    workspace_root: str,
    planner_workspace_dir: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    handoff_root = Path(handoff_dir.replace("$HOME", str(path.parent)).replace("~", str(path.parent)))
    handoff_root.parent.mkdir(parents=True, exist_ok=True)
    workspace_root_path = Path(workspace_root.replace("$HOME", str(path.parent)).replace("~", str(path.parent)))
    workspace_root_path.mkdir(parents=True, exist_ok=True)
    lines = [
        'version = 1',
        'profile_name = "test-profile"',
        'template_name = "gstack-harness"',
        'project_name = "test"',
        f'repo_root = "{REPO}"',
        f'tasks_root = "{path.parent / "tasks"}"',
        f'workspace_root = "{workspace_root}"',
        f'handoff_dir = "{handoff_dir}"',
        f'project_doc = "{path.parent / "tasks" / "PROJECT.md"}"',
        f'tasks_doc = "{path.parent / "tasks" / "TASKS.md"}"',
        f'status_doc = "{path.parent / "tasks" / "STATUS.md"}"',
        'send_script = "/bin/echo"',
        'status_script = "/bin/echo"',
        'patrol_script = "/bin/echo"',
        'agent_admin = "/bin/echo"',
        f'heartbeat_receipt = "{path.parent / "workspaces" / "koder" / "HEARTBEAT_RECEIPT.toml"}"',
        'seats = ["planner", "memory"]',
        'heartbeat_seats = []',
        'active_loop_owner = "planner"',
        'default_notify_target = "planner"',
        'heartbeat_owner = "koder"',
        'heartbeat_transport = "tmux"',
    ]
    if planner_workspace_dir is not None:
        lines.append(f'planner_workspace_dir = "{planner_workspace_dir}"')
    lines.extend(
        [
            '',
            '[seat_roles]',
            'planner = "planner-dispatcher"',
            'memory = "memory"',
            '',
            '[dynamic_roster]',
            'enabled = false',
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for seat in ("planner", "memory", "koder"):
        (path.parent / "workspaces" / seat).mkdir(parents=True, exist_ok=True)
    tasks_dir = path.parent / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "STATUS.md").write_text("# status\n", encoding="utf-8")
    (tasks_dir / "PROJECT.md").write_text("# project\n", encoding="utf-8")
    (tasks_dir / "TASKS.md").write_text("# tasks\n", encoding="utf-8")
    return path


def _write_delivery(delivery_dir: Path, task_id: str) -> Path:
    delivery = delivery_dir / "DELIVERY.md"
    delivery.parent.mkdir(parents=True, exist_ok=True)
    delivery.write_text(
        "\n".join(
            [
                f"task_id: {task_id}",
                "source: planner",
                "reply_to: memory",
                "files: []",
                "tests: []",
                "verdict: PASS",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return delivery


def _write_handoff(handoff_dir: Path, task_id: str) -> None:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / f"{task_id}__memory__planner.json.consumed").write_text("consumed\n", encoding="utf-8")
    (handoff_dir / f"{task_id}__planner__memory.json").write_text("{}", encoding="utf-8")


def _run(profile: str | Path, task_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--profile",
            str(profile),
            "--task-id",
            task_id,
        ],
        capture_output=True,
        text=True,
        cwd=str(SCRIPT.parent),
    )


def test_delivery_parser_skips_heading_first_line(tmp_path: Path) -> None:
    module = _load_script_module()
    delivery = tmp_path / "DELIVERY.md"
    delivery.write_text(
        "\n".join(
            [
                "# Planner DELIVERY: TASK-X",
                "",
                "source: planner",
                "reply_to: memory",
                "task_id: TASK-X",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert module._delivery_task_id(delivery) == "TASK-X"


def test_delivery_parser_returns_none_when_no_task_id(tmp_path: Path) -> None:
    module = _load_script_module()
    delivery = tmp_path / "DELIVERY.md"
    delivery.write_text(
        "\n".join(
            [
                "# Planner DELIVERY: TASK-X",
                "",
                "source: planner",
                "reply_to: memory",
                "verdict: PASS",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert module._delivery_task_id(delivery) is None


def test_delivery_parser_handles_blank_then_task_id(tmp_path: Path) -> None:
    module = _load_script_module()
    delivery = tmp_path / "DELIVERY.md"
    delivery.write_text(
        "\n".join(
            [
                "",
                "",
                "task_id: TASK-Y",
                "source: planner",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert module._delivery_task_id(delivery) == "TASK-Y"


def test_audit_all_artifacts_present(tmp_path: Path) -> None:
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
        planner_workspace_dir=str(tmp_path / "workspaces" / "planner"),
    )
    _write_handoff(tmp_path / "handoffs", "DJ-A1")
    _write_delivery(tmp_path / "tasks" / "planner", "DJ-A1")

    result = _run(profile, "DJ-A1")

    assert result.returncode == 0, result.stdout
    assert "all 3 artifacts present" in result.stdout


def test_audit_consumed_missing_is_diagnostic_not_hard_failure(tmp_path: Path) -> None:
    """CF047: .consumed absence is a diagnostic warning, not a hard failure.

    When planner→memory receipt and DELIVERY are both present, the audit must
    pass (exit 0) even if no incoming planner consumed sidecar exists.
    The .consumed artifact is not reliably produced by all multi-team relay
    paths (e.g. when --enforce-planner-self-closeout is not used).
    """
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
        planner_workspace_dir=str(tmp_path / "workspaces" / "planner"),
    )
    (tmp_path / "handoffs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "handoffs" / "DJ-A2__planner__memory.json").write_text("{}", encoding="utf-8")
    _write_delivery(tmp_path / "tasks" / "planner", "DJ-A2")

    result = _run(profile, "DJ-A2")

    # CF047 relaxation: returncode must be 0 (PASS with diagnostic warning)
    assert result.returncode == 0, f"consumed-missing must not block; got: {result.stdout}"
    assert ".consumed missing" in result.stdout  # diagnostic is still emitted
    assert "diagnostic" in result.stdout         # must be labelled as diagnostic


def test_audit_receipt_missing(tmp_path: Path) -> None:
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
        planner_workspace_dir=str(tmp_path / "workspaces" / "planner"),
    )
    (tmp_path / "handoffs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "handoffs" / "DJ-A3__memory__planner.json.consumed").write_text("consumed\n", encoding="utf-8")
    _write_delivery(tmp_path / "tasks" / "planner", "DJ-A3")

    result = _run(profile, "DJ-A3")

    assert result.returncode != 0
    assert "planner→memory receipt missing" in result.stdout


def test_audit_delivery_stale_task_id(tmp_path: Path) -> None:
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
        planner_workspace_dir=str(tmp_path / "workspaces" / "planner"),
    )
    _write_handoff(tmp_path / "handoffs", "DJ-A4")
    _write_delivery(tmp_path / "tasks" / "planner", "DJ-OTHER")

    result = _run(profile, "DJ-A4")

    assert result.returncode != 0
    assert "planner DELIVERY.md task_id mismatch" in result.stdout


def test_audit_with_tilde_profile_path(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(home))
    _write_profile(
        home / "profile.toml",
        handoff_dir="~/handoffs",
        workspace_root="~/workspaces",
        planner_workspace_dir="~/workspaces/planner",
    )
    _write_handoff(home / "handoffs", "DJ-A5")
    _write_delivery(home / "tasks" / "planner", "DJ-A5")

    result = _run("~/profile.toml", "DJ-A5")

    assert result.returncode == 0, result.stdout
    assert "all 3 artifacts present" in result.stdout


def test_audit_legacy_profile_no_planner_workspace_dir(tmp_path: Path) -> None:
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
    )
    _write_handoff(tmp_path / "handoffs", "DJ-A6")
    _write_delivery(tmp_path / "tasks" / "planner", "DJ-A6")

    result = _run(profile, "DJ-A6")

    assert result.returncode == 0, result.stdout
    assert "all 3 artifacts present" in result.stdout


def test_audit_reads_tasks_delivery_even_with_workspace_copy(tmp_path: Path) -> None:
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
        planner_workspace_dir=str(tmp_path / "workspaces" / "planner"),
    )
    _write_handoff(tmp_path / "handoffs", "DJ-A7")
    _write_delivery(tmp_path / "tasks" / "planner", "DJ-A7")
    stale_workspace_delivery = tmp_path / "workspaces" / "planner" / "DELIVERY.md"
    stale_workspace_delivery.parent.mkdir(parents=True, exist_ok=True)
    stale_workspace_delivery.write_text(
        "\n".join(
            [
                "task_id: DJ-STALE",
                "source: planner",
                "reply_to: memory",
                "verdict: PASS",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run(profile, "DJ-A7")

    assert result.returncode == 0, result.stdout
    assert "all 3 artifacts present" in result.stdout


# ---------------------------------------------------------------------------
# CF046: Team-scoped planner closeout tests
# ---------------------------------------------------------------------------


def _write_team_scoped_profile(
    path: Path,
    *,
    handoff_dir: str,
    workspace_root: str,
    planner_seat: str = "clawseat-core-planner",
) -> Path:
    """Write a profile with a team-scoped planner seat (e.g. clawseat-core-planner)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace_root_path = Path(workspace_root)
    workspace_root_path.mkdir(parents=True, exist_ok=True)
    lines = [
        'version = 1',
        'profile_name = "test-team-profile"',
        'template_name = "gstack-harness"',
        'project_name = "test"',
        f'repo_root = "{REPO}"',
        f'tasks_root = "{path.parent / "tasks"}"',
        f'workspace_root = "{workspace_root}"',
        f'handoff_dir = "{handoff_dir}"',
        f'project_doc = "{path.parent / "tasks" / "PROJECT.md"}"',
        f'tasks_doc = "{path.parent / "tasks" / "TASKS.md"}"',
        f'status_doc = "{path.parent / "tasks" / "STATUS.md"}"',
        'send_script = "/bin/echo"',
        'status_script = "/bin/echo"',
        'patrol_script = "/bin/echo"',
        'agent_admin = "/bin/echo"',
        f'heartbeat_receipt = "{path.parent / "workspaces" / "koder" / "HEARTBEAT_RECEIPT.toml"}"',
        f'seats = ["{planner_seat}", "memory"]',
        'heartbeat_seats = []',
        f'active_loop_owner = "{planner_seat}"',
        f'default_notify_target = "{planner_seat}"',
        'heartbeat_owner = "koder"',
        'heartbeat_transport = "tmux"',
        '',
        '[seat_roles]',
        f'"{planner_seat}" = "planner"',
        '"memory" = "memory"',
        '',
        '[dynamic_roster]',
        'enabled = false',
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for seat in (planner_seat, "memory", "koder"):
        (path.parent / "workspaces" / seat).mkdir(parents=True, exist_ok=True)
    tasks_dir = path.parent / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("STATUS.md", "PROJECT.md", "TASKS.md"):
        (tasks_dir / fname).write_text("# header\n", encoding="utf-8")
    return path


def _write_team_handoff(handoff_dir: Path, task_id: str, planner_seat: str) -> None:
    """Write the two handoff artifacts needed for a team-scoped planner closeout."""
    handoff_dir.mkdir(parents=True, exist_ok=True)
    # .consumed: any specialist delivering to planner (e.g. builder→planner consumed)
    (handoff_dir / f"{task_id}__builder__{planner_seat}.json.consumed").write_text(
        "consumed\n", encoding="utf-8"
    )
    # receipt: planner delivering to memory
    (handoff_dir / f"{task_id}__{planner_seat}__memory.json").write_text(
        "{}", encoding="utf-8"
    )


def _write_team_delivery(delivery_dir: Path, task_id: str) -> Path:
    delivery = delivery_dir / "DELIVERY.md"
    delivery.parent.mkdir(parents=True, exist_ok=True)
    delivery.write_text(
        f"task_id: {task_id}\nsource: planner\nreply_to: memory\n",
        encoding="utf-8",
    )
    return delivery


def _run_team(profile: Path, task_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--profile", str(profile), "--task-id", task_id],
        capture_output=True,
        text=True,
        cwd=str(SCRIPT.parent),
    )


def test_team_scoped_planner_all_artifacts_present(tmp_path: Path) -> None:
    """Team-scoped planner (clawseat-core-planner) closeout must pass with all artifacts."""
    planner_seat = "clawseat-core-planner"
    handoff_dir = tmp_path / "handoffs"
    workspace_root = tmp_path / "workspaces"
    profile = _write_team_scoped_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(handoff_dir),
        workspace_root=str(workspace_root),
        planner_seat=planner_seat,
    )
    _write_team_handoff(handoff_dir, "TS-A1", planner_seat)
    _write_team_delivery(tmp_path / "tasks" / planner_seat, "TS-A1")

    result = _run_team(profile, "TS-A1")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "all 3 artifacts present" in result.stdout


def test_team_scoped_consumed_missing_is_diagnostic_not_hard_failure(tmp_path: Path) -> None:
    """CF047: .consumed absence is diagnostic (non-blocking) for team-scoped planner.

    When planner→memory receipt and DELIVERY are both present, the audit passes
    (exit 0) even without an incoming .consumed sidecar.
    """
    planner_seat = "clawseat-core-planner"
    handoff_dir = tmp_path / "handoffs"
    workspace_root = tmp_path / "workspaces"
    profile = _write_team_scoped_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(handoff_dir),
        workspace_root=str(workspace_root),
        planner_seat=planner_seat,
    )
    handoff_dir.mkdir(parents=True)
    # Only the planner→memory receipt + DELIVERY, no .consumed
    (handoff_dir / f"TS-A2__{planner_seat}__memory.json").write_text("{}", encoding="utf-8")
    _write_team_delivery(tmp_path / "tasks" / planner_seat, "TS-A2")

    result = _run_team(profile, "TS-A2")

    assert result.returncode == 0, f"consumed-missing must not block; got: {result.stdout}"
    assert ".consumed missing" in result.stdout
    assert "diagnostic" in result.stdout


def test_cv007_style_queue_drained_closeout_passes(tmp_path: Path) -> None:
    """CF047 regression: valid queue-drained team-scoped closeout without .consumed sidecar.

    Simulates the CV007 cartooner-vault-planner pattern:
    - builder delivered to planner (.json exists, no .consumed sidecar)
    - planner→memory receipt exists
    - planner DELIVERY.md has correct task_id
    → must PASS (exit 0) with consumed diagnostic, not hard-fail.
    """
    planner_seat = "cartooner-vault-planner"
    handoff_dir = tmp_path / "handoffs"
    workspace_root = tmp_path / "workspaces"
    profile = _write_team_scoped_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(handoff_dir),
        workspace_root=str(workspace_root),
        planner_seat=planner_seat,
    )
    handoff_dir.mkdir(parents=True)
    # Builder→planner delivery exists but NOT consumed (no .consumed sidecar)
    task = "cv007-vault-page-patch-resilience-smoke-20260519"
    (handoff_dir / f"{task}__cartooner-vault-builder-core__{planner_seat}.json").write_text(
        "{}", encoding="utf-8"
    )
    # Planner→memory receipt IS present (final closeout)
    (handoff_dir / f"{task}__{planner_seat}__memory.json").write_text("{}", encoding="utf-8")
    _write_team_delivery(tmp_path / "tasks" / planner_seat, task)

    result = _run_team(profile, task)

    assert result.returncode == 0, (
        f"CV007-style valid closeout must pass; got stdout={result.stdout!r}"
    )
    assert ".consumed missing" in result.stdout  # diagnostic emitted
    assert "diagnostic" in result.stdout         # labelled as diagnostic
    assert "2 authoritative artifacts present" in result.stdout


def test_team_scoped_receipt_missing_is_hard_failure(tmp_path: Path) -> None:
    """Missing planner→memory receipt must still fail for team-scoped planner."""
    planner_seat = "clawseat-core-planner"
    handoff_dir = tmp_path / "handoffs"
    workspace_root = tmp_path / "workspaces"
    profile = _write_team_scoped_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(handoff_dir),
        workspace_root=str(workspace_root),
        planner_seat=planner_seat,
    )
    handoff_dir.mkdir(parents=True)
    # Only the consumed, no planner→memory receipt
    (handoff_dir / f"TS-A3__builder__{planner_seat}.json.consumed").write_text(
        "consumed\n", encoding="utf-8"
    )
    _write_team_delivery(tmp_path / "tasks" / planner_seat, "TS-A3")

    result = _run_team(profile, "TS-A3")

    assert result.returncode != 0
    assert "receipt missing" in result.stdout


def test_team_scoped_delivery_task_id_mismatch_is_hard_failure(tmp_path: Path) -> None:
    """task_id mismatch in DELIVERY.md must still fail for team-scoped planner."""
    planner_seat = "clawseat-core-planner"
    handoff_dir = tmp_path / "handoffs"
    workspace_root = tmp_path / "workspaces"
    profile = _write_team_scoped_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(handoff_dir),
        workspace_root=str(workspace_root),
        planner_seat=planner_seat,
    )
    _write_team_handoff(handoff_dir, "TS-A4", planner_seat)
    _write_team_delivery(tmp_path / "tasks" / planner_seat, "TS-WRONG")  # wrong task_id

    result = _run_team(profile, "TS-A4")

    assert result.returncode != 0
    assert "mismatch" in result.stdout or "missing" in result.stdout


def test_legacy_planner_still_accepted_with_team_scoped_profile(tmp_path: Path) -> None:
    """Legacy planner seat in seat_roles is still supported.

    Regression: even when planner_seat='planner' in seat_roles, artifacts
    under the 'planner' workspace must still pass.
    """
    handoff_dir = tmp_path / "handoffs"
    workspace_root = tmp_path / "workspaces"
    profile = _write_team_scoped_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(handoff_dir),
        workspace_root=str(workspace_root),
        planner_seat="planner",  # legacy seat name
    )
    _write_team_handoff(handoff_dir, "TS-A5", "planner")
    _write_team_delivery(tmp_path / "tasks" / "planner", "TS-A5")

    result = _run_team(profile, "TS-A5")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "all 3 artifacts present" in result.stdout


def test_resolve_planner_seats_team_scoped() -> None:
    """_resolve_planner_seats returns team-scoped seat before legacy fallback."""
    module = _load_script_module()

    class FakeProfile:
        seat_roles = {"clawseat-core-planner": "planner", "memory": "memory"}

    seats = module._resolve_planner_seats(FakeProfile())
    assert "clawseat-core-planner" in seats
    assert "planner" in seats  # legacy fallback always present
    assert seats.index("clawseat-core-planner") < seats.index("planner")


def test_resolve_planner_seats_legacy_only() -> None:
    """_resolve_planner_seats falls back to 'planner' when no seat_roles provided."""
    module = _load_script_module()

    class FakeProfile:
        seat_roles = {}

    seats = module._resolve_planner_seats(FakeProfile())
    assert "planner" in seats


def test_resolve_planner_seats_no_attribute() -> None:
    """_resolve_planner_seats is safe when profile lacks seat_roles attribute."""
    module = _load_script_module()

    class FakeProfile:
        pass

    seats = module._resolve_planner_seats(FakeProfile())
    assert "planner" in seats
