from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


HELPERS_PATH = Path(__file__).with_name("test_install_isolation.py")
HELPERS_SPEC = importlib.util.spec_from_file_location("test_install_seed_helpers", HELPERS_PATH)
assert HELPERS_SPEC is not None and HELPERS_SPEC.loader is not None
HELPERS = importlib.util.module_from_spec(HELPERS_SPEC)
HELPERS_SPEC.loader.exec_module(HELPERS)

_fake_install_root = HELPERS._fake_install_root


def _run_install(tmp_path: Path, *extra: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    minimax_template = home / ".agent-runtime" / "secrets" / "claude" / "minimax.env"
    minimax_template.parent.mkdir(parents=True, exist_ok=True)
    minimax_template.write_text(
        "ANTHROPIC_AUTH_TOKEN=minimax-token\nANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "bash",
            str(root / "scripts" / "install.sh"),
            "--project",
            "seedcase",
            "--template",
            "clawseat-creative",
            "--provider",
            "minimax",
            *extra,
        ],
        input="\n",
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
        },
        check=False,
    )
    return result, home


def test_seed_template_driven_copies_deepseek_planner_secret(tmp_path: Path) -> None:
    result, home = _run_install(tmp_path)
    assert result.returncode == 0, result.stderr
    planner_secret = home / ".agents" / "secrets" / "claude" / "deepseek" / "planner.env"
    assert planner_secret.is_file()
    assert "deepseek-v4-pro" in planner_secret.read_text(encoding="utf-8")


def test_seed_template_driven_copies_minimax_patrol_secret(tmp_path: Path) -> None:
    result, home = _run_install(tmp_path)
    assert result.returncode == 0, result.stderr
    patrol_secret = home / ".agents" / "secrets" / "claude" / "minimax" / "patrol.env"
    assert patrol_secret.is_file()
    assert "minimax-token" in patrol_secret.read_text(encoding="utf-8")


def test_seed_all_api_provider_overrides_api_workers(tmp_path: Path) -> None:
    result, home = _run_install(tmp_path, "--all-api-provider", "deepseek")
    assert result.returncode == 0, result.stderr
    patrol_secret = home / ".agents" / "secrets" / "claude" / "deepseek" / "patrol.env"
    assert patrol_secret.is_file()
    assert not (home / ".agents" / "secrets" / "claude" / "minimax" / "patrol.env").exists()
