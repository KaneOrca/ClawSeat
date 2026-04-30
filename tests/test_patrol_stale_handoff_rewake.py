from __future__ import annotations

import json
import os
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


def test_re_wake_stale_handoffs_sends_once_and_logs(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write_stale_handoff(home, "stale-one")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs):
        calls.append(cmd)
        return object()

    monkeypatch.setattr(patrol_loop.subprocess, "run", fake_run)

    assert patrol_loop.re_wake_stale_handoffs("demo", threshold_hours=2) == 1
    assert len(calls) == 1
    assert calls[0][0:4] == ["bash", str(home / "ClawSeat" / "core" / "shell-scripts" / "send-and-verify.sh"), "--project", "demo"]
    assert calls[0][4] == "builder"
    assert "[stale-handoff-rewake] stale-one dispatched 3h ago, no response" in calls[0][5]
    assert "stale-one" in (home / ".agents" / "logs" / "stale-handoff-rewake.log").read_text(encoding="utf-8")

    assert patrol_loop.re_wake_stale_handoffs("demo", threshold_hours=2) == 0
    assert len(calls) == 1


def test_re_wake_stale_handoffs_caps_each_cycle_at_five(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    for index in range(6):
        _write_stale_handoff(home, f"stale-{index}")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs):
        calls.append(cmd)
        return object()

    monkeypatch.setattr(patrol_loop.subprocess, "run", fake_run)

    assert patrol_loop.re_wake_stale_handoffs("demo", threshold_hours=2) == 5
    assert len(calls) == 5


def test_patrol_loop_emits_stale_handoff_marker() -> None:
    text = (SCRIPTS / "patrol_loop.py").read_text(encoding="utf-8")
    assert "[STALE-HANDOFF-REWAKE:project=" in text
