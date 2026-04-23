from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


_REPO = Path(__file__).resolve().parents[1]
_LAUNCHER = _REPO / "core" / "launchers" / "agent-launcher.sh"


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_codex_xcode_exec_agent_injects_xcode_best_base_url_fallback(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)

    secret = fake_home / ".agent-runtime" / "secrets" / "codex" / "xcode.env"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("OPENAI_API_KEY=sk-codex-xcode\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    _write_executable(
        bin_dir / "codex",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "login" ]]; then
  cat >/dev/null
  exit 0
fi
printf 'OPENAI_BASE_URL=%s\n' "${OPENAI_BASE_URL:-}"
printf 'OPENAI_API_BASE=%s\n' "${OPENAI_API_BASE:-}"
printf 'CLAWSEAT_PROVIDER=%s\n' "${CLAWSEAT_PROVIDER:-}"
""",
    )

    workdir = tmp_path / "workspace"
    workdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop("OPENAI_BASE_URL", None)
    env.pop("OPENAI_API_BASE", None)
    env.update(
        {
            "HOME": str(fake_home),
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "CLAWSEAT_PROVIDER": "xcode-best",
        }
    )

    result = subprocess.run(
        [
            str(_LAUNCHER),
            "--tool",
            "codex",
            "--auth",
            "xcode",
            "--dir",
            str(workdir),
            "--session",
            "codex-xcode-fallback",
            "--exec-agent",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "OPENAI_BASE_URL=https://api.xcode.best/v1" in result.stdout
    assert "OPENAI_API_BASE=" in result.stdout
    assert "CLAWSEAT_PROVIDER=xcode-best" in result.stdout
