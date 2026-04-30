"""Tests for Memory Feishu message format emitted by memory-stop-hook."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_HOOK = _REPO / "scripts" / "hooks" / "memory-stop-hook.sh"

pytestmark = pytest.mark.skipif(not _HOOK.exists(), reason="memory-stop-hook.sh not landed yet")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _make_wrappers(tmp_path: Path, *, tmux_rc: int = 0, python_rc: int = 0) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls_log = tmp_path / "calls.log"

    tmux_wrapper = """#!/usr/bin/env bash
set -eu
: "${CALLS_LOG:?}"
if [ "${1:-}" = "display-message" ]; then
  printf '%s\\n' "${TMUX_DISPLAY_MESSAGE:-mock-session}"
  exit 0
fi
printf 'tmux\\t%s\\n' "$*" >> "$CALLS_LOG"
exit "${TMUX_RC:-0}"
"""

    lark_wrapper = """#!/usr/bin/env bash
set -eu
: "${CALLS_LOG:?}"
python3 - "$@" <<'PY'
import json
import os
import sys

with open(os.environ["CALLS_LOG"], "a", encoding="utf-8") as handle:
    handle.write("lark\\t")
    handle.write(json.dumps(sys.argv[1:], ensure_ascii=False))
    handle.write("\\n")
PY
exit "${LARK_CLI_RC:-0}"
"""

    python_wrapper = """#!/usr/bin/env bash
set -eu
: "${CALLS_LOG:?}"
is_memory_deliver=0
for arg in "$@"; do
  case "$arg" in
    *memory_deliver.py)
      is_memory_deliver=1
      ;;
  esac
done
if [ "$is_memory_deliver" -eq 1 ]; then
  printf 'python\\t%s\\n' "$*" >> "$CALLS_LOG"
  exit "${PYTHON_RC:-0}"
fi
exec "___REAL_PYTHON___" "$@"
"""

    real_python = sys.executable
    python_wrapper = python_wrapper.replace("___REAL_PYTHON___", real_python.replace('"', '\\"'))

    _write_executable(bin_dir / "tmux", tmux_wrapper)
    _write_executable(bin_dir / "lark-cli", lark_wrapper)
    _write_executable(bin_dir / "python", python_wrapper)
    _write_executable(bin_dir / "python3", python_wrapper)
    return bin_dir, calls_log


def _run_hook(
    tmp_path: Path,
    payload: dict[str, object],
    *,
    tmux_rc: int = 0,
    python_rc: int = 0,
    transcript_content: str = "",
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bin_dir, calls_log = _make_wrappers(tmp_path, tmux_rc=tmux_rc, python_rc=python_rc)
    home = tmp_path / "home"
    (home / ".agents" / "tasks" / "install" / "PROJECT_BINDING.toml").parent.mkdir(parents=True, exist_ok=True)
    (home / ".agents" / "tasks" / "install" / "PROJECT_BINDING.toml").write_text(
        'project = "install"\nfeishu_group_id = "oc_mock_group"\n',
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env.get('PATH', '')}",
            "HOME": str(home),
            "CALLS_LOG": str(calls_log),
            "TMUX_RC": str(tmux_rc),
            "PYTHON_RC": str(python_rc),
            "TMUX_DISPLAY_MESSAGE": "install-memory-claude",
            "CLAUDE_PROJECT_DIR": str(_REPO),
            "LARK_CLI_RC": "0",
            "CLAWSEAT_FEISHU_ENABLED": "1",
        }
    )
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(transcript_content, encoding="utf-8")

    payload = {
        "session_id": "session-123",
        "transcript_path": str(transcript),
        "cwd": str(_REPO),
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        **payload,
    }
    proc = subprocess.run(
        ["bash", str(_HOOK)],
        input=json.dumps(payload, ensure_ascii=False) + "\n",
        text=True,
        capture_output=True,
        cwd=_REPO,
        env=env,
        check=False,
    )
    calls = calls_log.read_text(encoding="utf-8").splitlines() if calls_log.exists() else []
    return proc, calls


def _extract_lark_args(calls: list[str]) -> list[str] | None:
    # Preferred: parse the final lark-cli send message content.
    for line in calls:
        if not line.startswith("lark\t"):
            continue
        args = json.loads(line.split("\t", 1)[1])
        if args:
            return args

    return None


def _extract_lark_content(calls: list[str]) -> str:
    args = _extract_lark_args(calls)
    if args is not None:
        for index, arg in enumerate(args):
            if arg == "--content" and index + 1 < len(args):
                return args[index + 1]

    # Fallback: parse the same formatted message sent to memory_deliver.
    for line in calls:
        if "memory_deliver.py" not in line:
            continue
        content = line.split("\t", 1)[1]
        match = content.split("--response-inline", 1)
        if len(match) != 2:
            continue
        payload_part = match[1].split("--summary", 1)[0].strip()
        payload = json.loads(payload_part)
        return payload["answer"]

    raise AssertionError("No formatted message content found in hook calls")


def test_feishu_message_format_pass(tmp_path: Path) -> None:
    proc, calls = _run_hook(
        tmp_path,
        {
            "last_assistant_message": (
                "任务执行 PASS，结果可用。 "
                "[DELIVER:seat=planner task_id=MEMORY-QUERY-998 verdict=PASS summary=清洗流水线] "
            ),
        },
        transcript_content="task_id: MEMORY-QUERY-998\nproject: install\n",
    )
    assert proc.returncode == 0

    content = _extract_lark_content(calls)
    lark_args = _extract_lark_args(calls)
    assert lark_args is not None
    assert "--as" in lark_args
    assert lark_args[lark_args.index("--as") + 1] == "user"
    assert content.startswith("[Memory] ✅")
    assert "— Memory | install | " in content


def test_feishu_message_format_blocked(tmp_path: Path) -> None:
    proc, calls = _run_hook(
        tmp_path,
        {
            "last_assistant_message": (
                "任务卡住，需要你判断：\n"
                "A. 继续执行自动修复\n"
                "B. 暂停等待人工\n"
                "[DELIVER:seat=planner task_id=MEMORY-QUERY-999 verdict=BLOCKED summary=数据清洗冲突] "
            ),
        },
        transcript_content="task_id: MEMORY-QUERY-999\nproject: install\n",
    )
    assert proc.returncode == 0

    content = _extract_lark_content(calls)
    lark_args = _extract_lark_args(calls)
    assert lark_args is not None
    assert "--as" in lark_args
    assert lark_args[lark_args.index("--as") + 1] == "user"
    assert content.startswith("[Memory] 🔴 需要决策:")
    assert "A. 继续执行自动修复" in content
    assert "B. 暂停等待人工" in content
