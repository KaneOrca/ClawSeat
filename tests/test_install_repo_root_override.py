"""FR-7: install.sh --repo-root flag routes PROJECT_REPO_ROOT to ancestor launch + project-local.toml."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_INSTALL = _REPO / "scripts" / "install.sh"


def _run_install(tmp_path: Path, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "PYTHON_BIN": sys.executable,
        "CLAWSEAT_REAL_HOME": str(tmp_path / "home"),
    }
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["bash", str(_INSTALL)] + extra_args,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_repo_root_in_ancestor_dir_flag(tmp_path: Path) -> None:
    """--repo-root passes through to ancestor launch_seat --dir."""
    target_dir = tmp_path / "myrepo"
    target_dir.mkdir()
    result = _run_install(tmp_path, [
        "--project", "testproj",
        "--repo-root", str(target_dir),
        "--dry-run",
    ])
    assert result.returncode == 0, result.stderr
    # dry-run prints: --dir <path> --session testproj-ancestor
    assert f"--dir {target_dir}" in result.stdout, (
        f"Expected '--dir {target_dir}' in dry-run output:\n{result.stdout}"
    )


def test_nonexistent_repo_root_dies_2(tmp_path: Path) -> None:
    result = _run_install(tmp_path, [
        "--project", "testproj",
        "--repo-root", str(tmp_path / "nonexistent"),
        "--dry-run",
    ])
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}: {result.stderr}"
    assert "repo-root" in result.stderr.lower() or "INVALID_REPO_ROOT" in result.stderr


def test_default_behavior_unchanged_without_repo_root(tmp_path: Path) -> None:
    """Without --repo-root, install succeeds and writes project-local.toml."""
    result = _run_install(tmp_path, [
        "--project", "testproj",
        "--dry-run",
    ])
    assert result.returncode == 0, result.stderr
    # project-local.toml write message must appear in dry-run output
    assert "project-local.toml" in result.stdout
    # The ancestor --dir must be the clawseat REPO_ROOT (not an override)
    assert "--repo-root" not in " ".join(result.stdout.split()[:50])
