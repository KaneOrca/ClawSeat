from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_cartooner_template_api_key_check_reports_minimax_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    probe = f"""
set -euo pipefail
source "{REPO / 'scripts' / 'install.sh'}" >/dev/null
CLAWSEAT_TEMPLATE_NAME=cartooner-creative
_collect_missing_api_keys
mkdir -p "$HOME/.agents"
printf 'export MINIMAX_API_KEY=mm\\n' > "$HOME/.agents/.env.global"
[[ -z "$(_collect_missing_api_keys)" ]]
"""
    result = subprocess.run(
        ["bash", "-c", probe],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "CLAWSEAT_REAL_HOME": str(home),
            "PYTHON_BIN": sys.executable,
            "OPENAI_API_KEY": "",
            "GEMINI_API_KEY": "",
            "MINIMAX_API_KEY": "",
            "ANTHROPIC_AUTH_TOKEN": "",
            "ANTHROPIC_API_KEY": "",
            "CLAUDE_CODE_OAUTH_TOKEN": "",
        },
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "minimax\tMINIMAX_API_KEY" in result.stdout
    assert "openai\tOPENAI_API_KEY" not in result.stdout
    assert "gemini\tGEMINI_API_KEY" not in result.stdout


def test_noninteractive_missing_cartooner_template_key_exits_before_reinstall_mutation(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project_dir = home / ".agents" / "projects" / "demo"
    project_dir.mkdir(parents=True)
    project_toml = project_dir / "project.toml"
    original = 'name = "demo"\\nrepo_root = "/kept/repo"\\n'
    project_toml.write_text(original, encoding="utf-8")

    result = subprocess.run(
        [
            "bash",
            str(REPO / "scripts" / "install.sh"),
            "--reinstall",
            "--project",
            "demo",
            "--template",
            "cartooner-creative",
            "--provider",
            "oauth",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "CLAWSEAT_REAL_HOME": str(home),
            "PYTHON_BIN": sys.executable,
            "MINIMAX_API_KEY": "",
            "OPENAI_API_KEY": "",
            "GEMINI_API_KEY": "",
            "ANTHROPIC_AUTH_TOKEN": "",
            "ANTHROPIC_API_KEY": "",
            "CLAUDE_CODE_OAUTH_TOKEN": "",
        },
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "missing API keys" in result.stderr
    assert project_toml.read_text(encoding="utf-8") == original
    assert not list(project_dir.glob("project.toml.bak.*"))
