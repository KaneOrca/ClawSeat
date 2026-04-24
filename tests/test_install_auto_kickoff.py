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


def _run_install(
    tmp_path: Path,
    *,
    dry_run: bool,
    pane_snapshots: list[str] | None = None,
    steady_pane_text: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path, Path]:
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    agent_admin_log = tmp_path / "agent_admin.jsonl"
    iterm_payload_log = tmp_path / "iterm_payload.jsonl"
    agentctl_log = tmp_path / "agentctl.log"
    pane_dir = tmp_path / "tmux-panes"
    brief_path = home / ".agents" / "tasks" / "kickoff50" / "patrol" / "handoffs" / "ancestor-bootstrap.md"
    if pane_snapshots is not None or steady_pane_text is not None:
        pane_dir.mkdir(parents=True, exist_ok=True)
        session_name = "kickoff50-ancestor"
        for index, pane_text in enumerate(pane_snapshots or [], start=1):
            (pane_dir / f"{session_name}.{index}.txt").write_text(
                pane_text.replace("{BRIEF_PATH}", str(brief_path)),
                encoding="utf-8",
            )
        if steady_pane_text is not None:
            (pane_dir / f"{session_name}.txt").write_text(
                steady_pane_text.replace("{BRIEF_PATH}", str(brief_path)),
                encoding="utf-8",
            )
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
            "AGENTCTL_LOG": str(agentctl_log),
            "TMUX_LOG_FILE": str(tmux_log),
            "AGENT_ADMIN_LOG": str(agent_admin_log),
            "ITERM_PAYLOAD_LOG": str(iterm_payload_log),
            "TMUX_PANE_DIR": str(pane_dir),
        },
        check=False,
    )
    return result, launcher_log, tmux_log, home, agentctl_log


def test_install_dry_run_does_not_send_phase_a_kickoff(tmp_path: Path) -> None:
    result, _, _, _, agentctl_log = _run_install(tmp_path, dry_run=True)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, result.stderr
    assert "Step 9.5: auto-send Phase-A kickoff prompt" not in combined
    assert "读 " not in combined
    assert "spawn engineer seat 要 one-at-a-time" not in combined
    assert "IF ANCESTOR IS IDLE, COPY AND PASTE THIS:" not in combined
    assert not agentctl_log.exists()


def test_install_sends_phase_a_kickoff_after_tui_ready(tmp_path: Path) -> None:
    brief_stub = (
        "读 {BRIEF_PATH} 开始 Phase-A。"
        "按 brief 顺序执行 B0-B7，每步向我汇报或 CLI prompt 我确认。不要 fan-out specialist seat；"
        "spawn engineer seat 要 one-at-a-time。"
    )
    result, launcher_log, tmux_log, home, agentctl_log = _run_install(
        tmp_path,
        dry_run=False,
        pane_snapshots=[
            "",
            "Browser didn't open? Use the url below to sign in",
            "Type your message",
            brief_stub,
        ],
        steady_pane_text=brief_stub,
    )

    combined = result.stdout + result.stderr
    expected_brief = home / ".agents" / "tasks" / "kickoff50" / "patrol" / "handoffs" / "ancestor-bootstrap.md"
    guide_path = home / ".agents" / "tasks" / "kickoff50" / "OPERATOR-START-HERE.md"
    kickoff = (
        f"读 {expected_brief} 开始 Phase-A。按 brief 顺序执行 B0-B7，每步向我汇报或 CLI prompt 我确认。"
        "不要 fan-out specialist seat；spawn engineer seat 要 one-at-a-time。"
    )

    assert result.returncode == 0, result.stderr
    assert "Step 9.5: auto-send Phase-A kickoff prompt" in combined
    assert "Phase-A kickoff delivered to kickoff50-ancestor" in combined
    # Banner marker (Round-8 rewrite): bilingual header + "copy between the lines"
    # fences the kickoff block instead of the old "IF ANCESTOR IS IDLE" line.
    assert "PHASE-A KICKOFF (copy between the lines" in combined
    assert "ClawSeat install complete / 安装已完成" in combined
    assert kickoff in combined
    assert expected_brief.is_file()
    assert guide_path.is_file()
    assert "Phase-A 不让 memory 做同步调研" in guide_path.read_text(encoding="utf-8")
    assert "session-name ancestor --project kickoff50" in agentctl_log.read_text(encoding="utf-8")

    tmux_output = tmux_log.read_text(encoding="utf-8")
    assert tmux_output.index("capture-pane -t =kickoff50-ancestor") < tmux_output.index("send-keys -l -t kickoff50-ancestor")
    assert "send-keys -l -t kickoff50-ancestor" in tmux_output
    assert tmux_output.count("send-keys -l -t kickoff50-ancestor") == 1
    assert kickoff in tmux_output
    assert "spawn engineer seat 要 one-at-a-time。" in tmux_output

    records = _read_jsonl(launcher_log)
    assert [record["session"] for record in records] == [
        "kickoff50-ancestor",
        "machine-memory-claude",
    ]


def test_install_keeps_manual_fallback_when_auto_send_times_out(tmp_path: Path) -> None:
    result, _, tmux_log, home, _ = _run_install(
        tmp_path,
        dry_run=False,
        steady_pane_text="Quick safety check:",
    )

    combined = result.stdout + result.stderr
    expected_brief = home / ".agents" / "tasks" / "kickoff50" / "patrol" / "handoffs" / "ancestor-bootstrap.md"
    kickoff = (
        f"读 {expected_brief} 开始 Phase-A。按 brief 顺序执行 B0-B7，每步向我汇报或 CLI prompt 我确认。"
        "不要 fan-out specialist seat；spawn engineer seat 要 one-at-a-time。"
    )

    assert result.returncode == 0, result.stderr
    assert "Auto-send could not verify kickoff delivery to kickoff50-ancestor." in combined
    # Banner marker (Round-8 rewrite): see sibling test for full coverage.
    # Manual-fallback path still prints the fenced kickoff block for copy-paste.
    assert "PHASE-A KICKOFF (copy between the lines" in combined
    assert "ClawSeat install complete / 安装已完成" in combined
    assert kickoff in combined
    # Round-8 Step 9.5 now emits an explicit warn when auto-send skips or fails
    # (previously `|| true` swallowed it silently).
    assert "Phase-A kickoff auto-send skipped or failed" in combined

    tmux_output = tmux_log.read_text(encoding="utf-8")
    assert "capture-pane -t =kickoff50-ancestor" in tmux_output
    assert "send-keys -l -t kickoff50-ancestor" not in tmux_output


def test_install_accepts_claude_spinner_as_active_kickoff_response(tmp_path: Path) -> None:
    result, _, tmux_log, _, _ = _run_install(
        tmp_path,
        dry_run=False,
        pane_snapshots=["Type your message"],
        steady_pane_text="✶ Whisking…",
    )

    combined = result.stdout + result.stderr

    assert result.returncode == 0, result.stderr
    assert "Step 9.5: auto-send Phase-A kickoff prompt" in combined
    assert "Phase-A kickoff submitted to kickoff50-ancestor" in combined
    assert "Auto-send could not verify kickoff delivery" not in combined

    tmux_output = tmux_log.read_text(encoding="utf-8")
    assert "send-keys -l -t kickoff50-ancestor" in tmux_output
