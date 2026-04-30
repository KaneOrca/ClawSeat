from __future__ import annotations

import json
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import seat_clear_watchdog as watchdog  # noqa: E402


def _fake_tmux(tmp_path: Path) -> tuple[Path, Path, Path]:
    pane_file = tmp_path / "pane.txt"
    send_log = tmp_path / "send.log"
    tmux = tmp_path / "tmux"
    tmux.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, os, sys",
                "from pathlib import Path",
                "cmd = sys.argv[1]",
                "if cmd == 'list-sessions':",
                "    print(os.environ.get('FAKE_TMUX_SESSIONS', 'install-planner-gemini'))",
                "elif cmd == 'capture-pane':",
                "    print(Path(os.environ['FAKE_TMUX_PANE']).read_text(encoding='utf-8'), end='')",
                "elif cmd == 'send-keys':",
                "    path = Path(os.environ['FAKE_TMUX_SEND_LOG'])",
                "    with path.open('a', encoding='utf-8') as handle:",
                "        handle.write(json.dumps(sys.argv[1:]) + '\\n')",
                "else:",
                "    raise SystemExit(2)",
            ]
        ),
        encoding="utf-8",
    )
    tmux.chmod(0o755)
    return tmux, pane_file, send_log


def _setup_env(tmp_path, monkeypatch, pane_text: str) -> tuple[Path, Path]:
    home = tmp_path / "home"
    (home / ".agents" / "projects" / "install").mkdir(parents=True)
    runtime_root = tmp_path / "runtime"
    tmux, pane_file, send_log = _fake_tmux(tmp_path)
    pane_file.write_text(pane_text, encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAWSEAT_REAL_HOME", raising=False)
    monkeypatch.setenv("CLAWSEAT_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setenv("FAKE_TMUX_PANE", str(pane_file))
    monkeypatch.setenv("FAKE_TMUX_SEND_LOG", str(send_log))
    monkeypatch.setenv("FAKE_TMUX_SESSIONS", "install-planner-gemini")
    return tmux, send_log


def _sent_commands(send_log: Path) -> list[list[str]]:
    if not send_log.exists():
        return []
    return [json.loads(line) for line in send_log.read_text(encoding="utf-8").splitlines()]


def test_watchdog_clear_marker_sends_once_and_records_seen(tmp_path, monkeypatch) -> None:
    tmux, send_log = _setup_env(tmp_path, monkeypatch, "done\n[CLEAR-REQUESTED]\n")

    assert watchdog.main(["--once", "--tmux-bin", str(tmux)]) == 0
    assert _sent_commands(send_log) == [["send-keys", "-t", "install-planner-gemini", "/clear", "Enter"]]
    seen_files = list((tmp_path / "runtime" / "watchdog").glob("*.seen"))
    assert seen_files

    assert watchdog.main(["--once", "--tmux-bin", str(tmux)]) == 0
    assert _sent_commands(send_log) == [["send-keys", "-t", "install-planner-gemini", "/clear", "Enter"]]


def test_watchdog_skips_when_pane_is_thinking(tmp_path, monkeypatch) -> None:
    tmux, send_log = _setup_env(tmp_path, monkeypatch, "Working...\n[CLEAR-REQUESTED]\n")

    assert watchdog.main(["--once", "--tmux-bin", str(tmux)]) == 0

    assert _sent_commands(send_log) == []


def test_watchdog_compact_marker_sends_compact(tmp_path, monkeypatch) -> None:
    tmux, send_log = _setup_env(tmp_path, monkeypatch, "context heavy\n[COMPACT-REQUESTED]\n")

    assert watchdog.main(["--once", "--tmux-bin", str(tmux)]) == 0

    assert _sent_commands(send_log) == [["send-keys", "-t", "install-planner-gemini", "/compact", "Enter"]]
