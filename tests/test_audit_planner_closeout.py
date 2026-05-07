from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "core" / "skills" / "memory-oracle" / "scripts" / "audit_planner_closeout.py"


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
    (path.parent / "tasks" / "STATUS.md").write_text("# status\n", encoding="utf-8")
    (path.parent / "tasks" / "PROJECT.md").write_text("# project\n", encoding="utf-8")
    (path.parent / "tasks" / "TASKS.md").write_text("# tasks\n", encoding="utf-8")
    return path


def _write_delivery(planner_workspace_dir: Path, task_id: str) -> Path:
    delivery = planner_workspace_dir / "DELIVERY.md"
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


def test_audit_all_artifacts_present(tmp_path: Path) -> None:
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
        planner_workspace_dir=str(tmp_path / "workspaces" / "planner"),
    )
    _write_handoff(tmp_path / "handoffs", "DJ-A1")
    _write_delivery(tmp_path / "workspaces" / "planner", "DJ-A1")

    result = _run(profile, "DJ-A1")

    assert result.returncode == 0, result.stdout
    assert "all 3 artifacts present" in result.stdout


def test_audit_consumed_missing(tmp_path: Path) -> None:
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
        planner_workspace_dir=str(tmp_path / "workspaces" / "planner"),
    )
    (tmp_path / "handoffs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "handoffs" / "DJ-A2__planner__memory.json").write_text("{}", encoding="utf-8")
    _write_delivery(tmp_path / "workspaces" / "planner", "DJ-A2")

    result = _run(profile, "DJ-A2")

    assert result.returncode != 0
    assert ".consumed missing" in result.stdout


def test_audit_receipt_missing(tmp_path: Path) -> None:
    profile = _write_profile(
        tmp_path / "profile.toml",
        handoff_dir=str(tmp_path / "handoffs"),
        workspace_root=str(tmp_path / "workspaces"),
        planner_workspace_dir=str(tmp_path / "workspaces" / "planner"),
    )
    (tmp_path / "handoffs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "handoffs" / "DJ-A3__memory__planner.json.consumed").write_text("consumed\n", encoding="utf-8")
    _write_delivery(tmp_path / "workspaces" / "planner", "DJ-A3")

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
    _write_delivery(tmp_path / "workspaces" / "planner", "DJ-OTHER")

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
    _write_delivery(home / "workspaces" / "planner", "DJ-A5")

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
    _write_delivery(tmp_path / "workspaces" / "planner", "DJ-A6")

    result = _run(profile, "DJ-A6")

    assert result.returncode == 0, result.stdout
    assert "all 3 artifacts present" in result.stdout
