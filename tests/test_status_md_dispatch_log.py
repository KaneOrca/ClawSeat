from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import _task_io


_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "skills" / "gstack-harness" / "scripts"


def _status_doc(entries: list[str] | None = None) -> str:
    body = "\n".join(entries or [])
    return (
        "# test — STATUS\n\n"
        "## phase\n\n"
        "phase=ready\n\n"
        "## dispatch log (append-only, last 20)\n\n"
        f"{body}\n"
    )


def _dispatch_log_entries(text: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index("## dispatch log (append-only, last 20)") + 1
    end = len(lines)
    for idx in range(start, len(lines)):
        if idx > start and lines[idx].startswith("## "):
            end = idx
            break
    return [
        line
        for line in lines[start:end]
        if line.strip() and line.strip() != "(none)"
    ]


def _make_profile(tmp_path: Path, *, status_text: str | None = None) -> tuple[Path, Path]:
    tasks = tmp_path / "tasks" / "install"
    workspaces = tmp_path / "workspaces" / "install"
    handoffs = tasks / "patrol" / "handoffs"
    status = tasks / "STATUS.md"
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text(status_text if status_text is not None else _status_doc(), encoding="utf-8")

    profile = tmp_path / "profile.toml"
    profile.write_text(
        f"""\
version = 1
profile_name = "test-profile"
template_name = "gstack-harness"
project_name = "install"
repo_root = "{_REPO}"
tasks_root = "{tasks}"
project_doc = "{tasks / "PROJECT.md"}"
tasks_doc = "{tasks / "TASKS.md"}"
status_doc = "{status}"
send_script = "/bin/echo"
status_script = "/bin/echo"
patrol_script = "/bin/echo"
agent_admin = "/bin/echo"
workspace_root = "{workspaces}"
handoff_dir = "{handoffs}"
heartbeat_owner = "koder"
heartbeat_transport = "tmux"
active_loop_owner = "planner"
default_notify_target = "planner"
heartbeat_receipt = "{workspaces / "koder" / "HEARTBEAT_RECEIPT.toml"}"
seats = ["planner", "builder"]
heartbeat_seats = []

[seat_roles]
planner = "planner-dispatcher"
builder = "builder"

[dynamic_roster]
materialized_seats = ["planner", "builder"]
runtime_seats = ["planner", "builder"]
""",
        encoding="utf-8",
    )
    return profile, status


def _run_dispatch(profile: Path, task_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS / "dispatch_task.py"),
            "--profile",
            str(profile),
            "--source",
            "planner",
            "--target",
            "builder",
            "--task-id",
            task_id,
            "--title",
            f"test {task_id}",
            "--objective",
            "no-op objective",
            "--reply-to",
            "planner",
            "--no-notify",
        ],
        capture_output=True,
        text=True,
        cwd=str(_SCRIPTS),
    )


def _run_complete(profile: Path, task_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS / "complete_handoff.py"),
            "--profile",
            str(profile),
            "--source",
            "builder",
            "--target",
            "planner",
            "--task-id",
            task_id,
            "--summary",
            "no-op done",
            "--status",
            "done",
            "--verdict",
            "APPROVED",
            "--commit",
            "abc1234",
            "--no-notify",
        ],
        capture_output=True,
        text=True,
        cwd=str(_SCRIPTS),
    )


def test_dispatch_appends_line(tmp_path: Path) -> None:
    profile, status = _make_profile(tmp_path)

    result = _run_dispatch(profile, "status-dispatch")

    assert result.returncode == 0, result.stderr
    entries = _dispatch_log_entries(status.read_text(encoding="utf-8"))
    assert len(entries) == 1
    assert entries[0].endswith(": planner dispatched status-dispatch to builder")


def test_complete_appends_ack(tmp_path: Path) -> None:
    profile, status = _make_profile(tmp_path)
    dispatch = _run_dispatch(profile, "status-ack")
    assert dispatch.returncode == 0, dispatch.stderr

    result = _run_complete(profile, "status-ack")

    assert result.returncode == 0, result.stderr
    entries = _dispatch_log_entries(status.read_text(encoding="utf-8"))
    assert entries[-1].endswith(": builder ack status-ack verdict=APPROVED commit=abc1234")


def test_truncation_keeps_last_20(tmp_path: Path) -> None:
    old_entries = [
        f"- 2026-04-26T00:{idx:02d}:00+08:00: planner dispatched old-{idx:02d} to builder"
        for idx in range(22)
    ]
    profile, status = _make_profile(tmp_path, status_text=_status_doc(old_entries))

    result = _run_dispatch(profile, "status-truncate")

    assert result.returncode == 0, result.stderr
    entries = _dispatch_log_entries(status.read_text(encoding="utf-8"))
    assert len(entries) == 20
    assert "old-00" not in "\n".join(entries)
    assert "old-01" not in "\n".join(entries)
    assert "old-02" not in "\n".join(entries)
    assert entries[-1].endswith(": planner dispatched status-truncate to builder")


def test_missing_section_skips(tmp_path: Path) -> None:
    before = "# test — STATUS\n\n## phase\n\nphase=ready\n"
    profile, status = _make_profile(tmp_path, status_text=before)

    result = _run_dispatch(profile, "status-missing-section")

    assert result.returncode == 0
    assert status.read_text(encoding="utf-8") == before
    assert "STATUS.md dispatch log append skipped" in result.stderr
    assert "section missing" in result.stderr


def test_atomic_write(tmp_path: Path, monkeypatch) -> None:
    status = tmp_path / "STATUS.md"
    status.write_text(_status_doc(), encoding="utf-8")
    calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def fake_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        calls.append((src_path, dst_path))
        assert src_path.name == "STATUS.md.tmp"
        assert src_path.exists()
        assert "planner dispatched atomic-task to builder" in src_path.read_text(encoding="utf-8")
        real_replace(src_path, dst_path)

    monkeypatch.setattr(_task_io.os, "replace", fake_replace)

    ok = _task_io.append_status_dispatch_event(
        status,
        source="planner",
        task_id="atomic-task",
        target="builder",
        timestamp="2026-04-26T05:00:00+08:00",
    )

    assert ok is True
    assert calls == [(status.with_name("STATUS.md.tmp"), status)]
    assert "planner dispatched atomic-task to builder" in status.read_text(encoding="utf-8")
