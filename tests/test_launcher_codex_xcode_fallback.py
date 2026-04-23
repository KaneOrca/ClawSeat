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
printf 'ARGS=%s\n' "$*"
printf 'OPENAI_BASE_URL=%s\n' "${OPENAI_BASE_URL:-}"
printf 'OPENAI_API_BASE=%s\n' "${OPENAI_API_BASE:-}"
printf 'CLAWSEAT_PROVIDER=%s\n' "${CLAWSEAT_PROVIDER:-}"
printf 'CONFIG_PATH=%s\n' "${CODEX_HOME:-}/config.toml"
cat "${CODEX_HOME:?}/config.toml"
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
    assert "ARGS=--dangerously-bypass-approvals-and-sandbox -C" in result.stdout
    assert "OPENAI_BASE_URL=https://api.xcode.best/v1" in result.stdout
    assert "OPENAI_API_BASE=" in result.stdout
    assert "CLAWSEAT_PROVIDER=xcode-best" in result.stdout
    assert 'model_provider = "xcodeapi"' in result.stdout
    assert '[model_providers.xcodeapi]' in result.stdout
    assert 'name = "xcodeapi"' in result.stdout
    assert 'base_url = "https://api.xcode.best/v1"' in result.stdout
    assert 'experimental_bearer_token = "sk-codex-xcode"' in result.stdout


def test_codex_xcode_exec_agent_renders_fresh_config_over_existing_symlink(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)

    secret = fake_home / ".agent-runtime" / "secrets" / "codex" / "xcode.env"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("OPENAI_API_KEY=sk-codex-xcode\n", encoding="utf-8")

    workdir = tmp_path / "workspace"
    workdir.mkdir(parents=True, exist_ok=True)
    session_name = "codex-xcode-symlink-reset"
    runtime_codex_home = (
        fake_home
        / ".agent-runtime"
        / "identities"
        / "codex"
        / "api"
        / f"xcode-{session_name}"
        / "codex-home"
    )
    runtime_codex_home.mkdir(parents=True, exist_ok=True)
    foreign_config = tmp_path / "foreign-config.toml"
    foreign_config.write_text('model_provider = "wrong"\n', encoding="utf-8")
    (runtime_codex_home / "config.toml").symlink_to(foreign_config)

    bin_dir = tmp_path / "bin"
    _write_executable(
        bin_dir / "codex",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "login" ]]; then
  cat >/dev/null
  exit 0
fi
cat "${CODEX_HOME:?}/config.toml"
""",
    )

    env = {
        **os.environ,
        "HOME": str(fake_home),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "CLAWSEAT_PROVIDER": "xcode-best",
    }
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
            session_name,
            "--exec-agent",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    config_path = runtime_codex_home / "config.toml"
    assert config_path.exists()
    assert not config_path.is_symlink()
    rendered = config_path.read_text(encoding="utf-8")
    assert 'model_provider = "xcodeapi"' in rendered
    assert '[model_providers.xcodeapi]' in rendered
    assert 'base_url = "https://api.xcode.best/v1"' in rendered
    assert foreign_config.read_text(encoding="utf-8") == 'model_provider = "wrong"\n'


def test_agent_launcher_codex_exec_sites_all_include_yolo_flag() -> None:
    text = _LAUNCHER.read_text(encoding="utf-8")
    needle = 'exec codex --dangerously-bypass-approvals-and-sandbox -C "$workdir"'

    assert text.count(needle) == 4
