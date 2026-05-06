"""CX: dispatch_task records optional expected_base_sha for completion validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "skills" / "gstack-harness" / "scripts"
_DISPATCH = _SCRIPTS / "dispatch_task.py"


def _run(*cmd: str, cwd: Path | str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_DISPATCH), *cmd],
        capture_output=True,
        text=True,
        cwd=str(cwd or _SCRIPTS),
        check=False,
    )


def _write_profile(tmp_path: Path, repo_root: Path) -> tuple[Path, Path]:
    tasks = tmp_path / "tasks"
    handoffs = tmp_path / "handoffs"
    workspaces = tmp_path / "workspaces"
    tasks.mkdir()
    (tasks / "planner").mkdir()
    (tasks / "builder").mkdir()
    handoffs.mkdir()
    workspaces.mkdir()
    profile = tmp_path / "profile.toml"
    profile.write_text(
        f"""\
version = 1
profile_name = \"test-profile\"
project_name = \"test\"
template_name = \"gstack-harness\"
repo_root = \"{repo_root}\"
tasks_root = \"{tasks}\"
workspace_root = \"{workspaces}\"
handoff_dir = \"{handoffs}\"
project_doc = \"{tasks}/PROJECT.md\"
tasks_doc = \"{tasks}/TASKS.md\"
status_doc = \"{tasks}/STATUS.md\"
send_script = \"/bin/echo\"
status_script = \"/bin/echo\"
patrol_script = \"/bin/echo\"
agent_admin = \"/bin/echo\"
heartbeat_receipt = \"{workspaces}/koder/HEARTBEAT_RECEIPT.toml\"
heartbeat_transport = \"tmux\"
default_notify_target = \"planner\"
heartbeat_owner = \"koder\"
heartbeat_seats = []
active_loop_owner = \"planner\"
seats = [\"planner\", \"builder\"]

[seat_roles]
planner = \"planner-dispatcher\"
builder = \"builder\"

[dynamic_roster]
materialized_seats = [\"planner\", \"builder\"]
""",
        encoding="utf-8",
    )
    return profile, handoffs


def _init_repo(repo_root: Path) -> str:
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(repo_root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo_root), "config", "user.name", "ci"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "ci@example.com"],
        check=True,
    )
    (repo_root / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_root), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "init", "-q"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_root), "checkout", "-q", "-b", "main"], check=True)
    head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(repo_root), "update-ref", "refs/remotes/clawseat/main", head],
        check=True,
    )
    return head


def _dispatch(profile: Path, task_id: str) -> subprocess.CompletedProcess[str]:
    return _run(
        "--profile", str(profile),
        "--source", "planner",
        "--target", "builder",
        "--task-id", task_id,
        "--title", f"test {task_id}",
        "--objective", "run",
        "--test-policy", "UPDATE",
        "--reply-to", "planner",
        "--no-notify",
    )


def test_dispatch_records_expected_base_sha_when_git_main_known(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    expected = _init_repo(repo_root)
    profile, handoffs = _write_profile(tmp_path, repo_root)

    result = _dispatch(profile, "TASK-BASE-1")
    assert result.returncode == 0, result.stderr

    receipt = handoffs / "TASK-BASE-1__planner__builder.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["expected_base_sha"] == expected


def test_dispatch_skips_expected_base_sha_when_git_main_missing(tmp_path: Path) -> None:
    profile, handoffs = _write_profile(tmp_path, tmp_path / "missing-repo")
    result = _dispatch(profile, "TASK-BASE-2")
    assert result.returncode == 0, result.stderr

    receipt = handoffs / "TASK-BASE-2__planner__builder.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert "expected_base_sha" not in payload
