from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "core" / "skills" / "gstack-harness" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import patrol_loop  # noqa: E402


def _write_stale_handoff(home: Path, task_id: str, *, target: str = "builder") -> Path:
    handoffs = home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs"
    handoffs.mkdir(parents=True, exist_ok=True)
    path = handoffs / f"{task_id}__planner__{target}.json"
    path.write_text(
        json.dumps({"task_id": task_id, "source": "planner", "target": target}),
        encoding="utf-8",
    )
    ts = time.time() - 3 * 3600
    os.utime(path, (ts, ts))
    return path


def _assert_task_queue_prefix(message: str, task_id: str) -> None:
    assert message.startswith("[TASK-QUEUE] 你有未处理的 handoff: ")
    assert task_id in message
    assert "请读 TODO.md 头部处理。" in message
    assert re.search(r"\(已 \d+h\)", message)


def _cmd_as_text(cmd: list[str] | tuple[str, ...] | str) -> str:
    return " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)


def test_re_wake_codex_working_skips_rewake(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write_stale_handoff(home, "codex-working")
    calls: list[list[str] | str] = []

    def fake_run(cmd: list[str] | str, **kwargs):
        calls.append(cmd)
        if "capture-pane" in _cmd_as_text(cmd):
            return subprocess.CompletedProcess(cmd, 0, "Working...\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(patrol_loop.subprocess, "run", fake_run)

    assert patrol_loop.re_wake_stale_handoffs("demo", threshold_hours=2) == 0
    assert any("capture-pane" in _cmd_as_text(cmd) for cmd in calls)
    assert not any("send-and-verify.sh" in _cmd_as_text(cmd) for cmd in calls)


def test_re_wake_codex_idle_sends_taskqueue_message(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write_stale_handoff(home, "codex-idle")
    calls: list[list[str] | str] = []

    def fake_run(cmd: list[str] | str, **kwargs):
        calls.append(cmd)
        if "capture-pane" in _cmd_as_text(cmd):
            return subprocess.CompletedProcess(cmd, 0, "Previous output\n› \n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(patrol_loop.subprocess, "run", fake_run)

    assert patrol_loop.re_wake_stale_handoffs("demo", threshold_hours=2) == 1
    send_calls = [cmd for cmd in calls if "send-and-verify.sh" in _cmd_as_text(cmd)]
    assert len(send_calls) == 1
    send_cmd = send_calls[0]
    sent_message = str(send_cmd[-1]) if isinstance(send_cmd, (list, tuple)) else _cmd_as_text(send_cmd)
    _assert_task_queue_prefix(sent_message, "codex-idle")


def test_re_wake_codex_background_terminal_running_skips_rewake(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write_stale_handoff(home, "codex-bg")
    calls: list[list[str] | str] = []

    def fake_run(cmd: list[str] | str, **kwargs):
        calls.append(cmd)
        if "capture-pane" in _cmd_as_text(cmd):
            return subprocess.CompletedProcess(cmd, 0, "background terminal running\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(patrol_loop.subprocess, "run", fake_run)

    assert patrol_loop.re_wake_stale_handoffs("demo", threshold_hours=2) == 0
    assert any("capture-pane" in _cmd_as_text(cmd) for cmd in calls)
    assert not any("send-and-verify.sh" in _cmd_as_text(cmd) for cmd in calls)
