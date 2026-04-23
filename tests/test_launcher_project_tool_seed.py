from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "core" / "launchers" / "agent-launcher.sh"


def _seed_project_root(project_root: Path) -> None:
    (project_root / ".lark-cli").mkdir(parents=True, exist_ok=True)
    (project_root / ".lark-cli" / "config.json").write_text("project-lark", encoding="utf-8")
    (project_root / "Library" / "Application Support" / "iTerm2").mkdir(parents=True, exist_ok=True)
    (project_root / "Library" / "Application Support" / "iTerm2" / "state.txt").write_text(
        "iterm-state",
        encoding="utf-8",
    )
    (project_root / "Library" / "Preferences").mkdir(parents=True, exist_ok=True)
    (project_root / "Library" / "Preferences" / "com.googlecode.iterm2.plist").write_text(
        "prefs",
        encoding="utf-8",
    )
    (project_root / ".config" / "gemini").mkdir(parents=True, exist_ok=True)
    (project_root / ".config" / "gemini" / "settings.json").write_text(
        "gemini-settings",
        encoding="utf-8",
    )
    (project_root / ".gemini").mkdir(parents=True, exist_ok=True)
    (project_root / ".gemini" / "auth.json").write_text("gemini-auth", encoding="utf-8")
    (project_root / ".config" / "codex").mkdir(parents=True, exist_ok=True)
    (project_root / ".config" / "codex" / "config.toml").write_text("model = 'gpt-5.4'", encoding="utf-8")
    (project_root / ".codex").mkdir(parents=True, exist_ok=True)
    (project_root / ".codex" / "auth.json").write_text("codex-auth", encoding="utf-8")


def _run_seed_helper(runtime_home: Path, project_name: str, project_root: Path) -> None:
    env = {
        **os.environ,
        "HOME": str(runtime_home.parent.parent),
        "CLAWSEAT_AGENT_LAUNCHER_LIBRARY_ONLY": "1",
        "CLAWSEAT_PROJECT": project_name,
        "CLAWSEAT_TOOLS_ISOLATION": "per-project",
        "CLAWSEAT_PROJECT_TOOL_ROOT": str(project_root),
    }
    snippet = "\n".join(
        [
            "set -euo pipefail",
            f"source {shlex.quote(str(LAUNCHER))}",
            f"seed_user_tool_dirs {shlex.quote(str(runtime_home))} {shlex.quote(project_name)}",
        ]
    )
    result = subprocess.run(
        ["bash", "-c", snippet],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_seed_user_tool_dirs_prefers_project_root_when_explicitly_isolated(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime" / "home"
    project_root = tmp_path / "real_home" / ".agent-runtime" / "projects" / "smoke01"
    runtime_home.mkdir(parents=True)
    project_root.mkdir(parents=True)
    _seed_project_root(project_root)

    _run_seed_helper(runtime_home, "smoke01", project_root)

    for subpath, source_subpath in (
        (".lark-cli", ".lark-cli"),
        (".gemini", ".gemini"),
        (".codex", ".codex"),
        ("Library/Application Support/iTerm2", "Library/Application Support/iTerm2"),
        ("Library/Preferences/com.googlecode.iterm2.plist", "Library/Preferences/com.googlecode.iterm2.plist"),
    ):
        link = runtime_home / subpath
        assert link.is_symlink()
        assert link.readlink() == project_root / source_subpath

    (runtime_home / ".lark-cli" / "roundtrip.txt").write_text("lark-write", encoding="utf-8")
    assert (project_root / ".lark-cli" / "roundtrip.txt").read_text(encoding="utf-8") == "lark-write"

