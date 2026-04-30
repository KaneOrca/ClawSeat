from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "scripts" / "hooks" / "memory-stop-hook.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_memory_stop_hook_pushes_memory_marker_via_lark_cli(tmp_path: Path) -> None:
    home = tmp_path / "home"
    binding = home / ".agents" / "tasks" / "install" / "PROJECT_BINDING.toml"
    binding.parent.mkdir(parents=True)
    binding.write_text('project = "install"\nfeishu_group_id = "oc_test_group"\n', encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls_log = tmp_path / "calls.log"
    _write_executable(
        bin_dir / "lark-cli",
        """#!/usr/bin/env bash
set -eu
: "${CALLS_LOG:?}"
printf '%q ' "$@" >> "$CALLS_LOG"
printf '\\n' >> "$CALLS_LOG"
""",
    )
    _write_executable(bin_dir / "logger", "#!/usr/bin/env bash\ncat >/dev/null\n")

    message = (
        "[Memory]\n"
        "Task done.\n\n"
        "---\n"
        "_via Memory @ 2026-04-30T16:00:00Z | project=install | session=install-memory | task_id=bj-task | verdict=PASS_"
    )
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "CALLS_LOG": str(calls_log),
        "PYTHON_BIN": sys.executable,
    }
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps({"last_assistant_message": message}, ensure_ascii=False) + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    sent = calls_log.read_text(encoding="utf-8")
    assert "--as user im +messages-send" in sent
    assert "--chat-id oc_test_group" in sent
    assert "[Memory]" in sent
    assert "task_id=bj-task" in sent


def test_memory_stop_hook_skips_memory_marker_without_footer(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps({"last_assistant_message": "[Memory]\nmissing footer"}, ensure_ascii=False) + "\n",
        text=True,
        capture_output=True,
        env={**os.environ, "HOME": str(home), "PYTHON_BIN": sys.executable},
        check=False,
    )
    assert result.returncode == 0
    assert "missing footer" in result.stderr
