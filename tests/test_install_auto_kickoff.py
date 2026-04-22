from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


_HELPERS_PATH = Path(__file__).with_name("test_install_isolation.py")
_HELPERS_SPEC = importlib.util.spec_from_file_location("test_install_isolation_helpers", _HELPERS_PATH)
assert _HELPERS_SPEC is not None and _HELPERS_SPEC.loader is not None
_HELPERS = importlib.util.module_from_spec(_HELPERS_SPEC)
_HELPERS_SPEC.loader.exec_module(_HELPERS)

_fake_install_root = _HELPERS._fake_install_root
_read_jsonl = _HELPERS._read_jsonl


def _run_install(tmp_path: Path, *, dry_run: bool) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    agent_admin_log = tmp_path / "agent_admin.jsonl"
    iterm_payload_log = tmp_path / "iterm_payload.jsonl"
    args = ["bash", str(root / "scripts" / "install.sh")]
    if dry_run:
        args.append("--dry-run")
    args.extend(["--project", "kickoff50", "--provider", "minimax"])

    result = subprocess.run(
        args,
        input="" if dry_run else "\n",
        capture_output=True,
        text=True,
        timeout=30,
        env={
            **os.environ,
            "HOME": str(home),
            "CLAWSEAT_REAL_HOME": str(home),
            "PATH": f"{root.parent / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "PYTHONPATH": f"{py_stubs}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
            "PYTHON_BIN": sys.executable,
            "LOG_FILE": str(launcher_log),
            "TMUX_LOG_FILE": str(tmux_log),
            "AGENT_ADMIN_LOG": str(agent_admin_log),
            "ITERM_PAYLOAD_LOG": str(iterm_payload_log),
        },
        check=False,
    )
    return result, launcher_log, tmux_log, home


def test_install_dry_run_does_not_send_phase_a_kickoff(tmp_path: Path) -> None:
    result, _, _, _ = _run_install(tmp_path, dry_run=True)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, result.stderr
    assert "Step 9.5: auto-send Phase-A kickoff prompt" not in combined
    assert "读 " not in combined
    assert "spawn engineer seat 要 one-at-a-time" not in combined


def test_install_sends_phase_a_kickoff_after_tui_ready(tmp_path: Path) -> None:
    result, launcher_log, tmux_log, home = _run_install(tmp_path, dry_run=False)

    combined = result.stdout + result.stderr
    expected_brief = home / ".agents" / "tasks" / "kickoff50" / "patrol" / "handoffs" / "ancestor-bootstrap.md"
    guide_path = home / ".agents" / "tasks" / "kickoff50" / "OPERATOR-START-HERE.md"

    assert result.returncode == 0, result.stderr
    assert "Step 9.5: auto-send Phase-A kickoff prompt" in combined
    assert expected_brief.is_file()
    assert guide_path.is_file()
    assert "Phase-A 不让 memory 做同步调研" in guide_path.read_text(encoding="utf-8")

    tmux_output = tmux_log.read_text(encoding="utf-8")
    assert "send-keys -l -t kickoff50-ancestor" in tmux_output
    assert f"读 {expected_brief} 开始 Phase-A。" in tmux_output
    assert "spawn engineer seat 要 one-at-a-time。" in tmux_output

    records = _read_jsonl(launcher_log)
    assert [record["session"] for record in records] == [
        "kickoff50-ancestor",
        "machine-memory-claude",
    ]
