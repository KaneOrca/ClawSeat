"""FR-7: install.sh --repo-root flag routes PROJECT_REPO_ROOT to ancestor launch + project-local.toml."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_INSTALL = _REPO / "scripts" / "install.sh"

# Import helpers from test_install_isolation so we can run non-dry-run tests
# with a fully stubbed fake install root.
_HELPERS_PATH = Path(__file__).with_name("test_install_isolation.py")
_HELPERS_SPEC = importlib.util.spec_from_file_location(
    "test_install_isolation_helpers_repo_root", _HELPERS_PATH
)
assert _HELPERS_SPEC is not None and _HELPERS_SPEC.loader is not None
_HELPERS = importlib.util.module_from_spec(_HELPERS_SPEC)
_HELPERS_SPEC.loader.exec_module(_HELPERS)

_fake_install_root = _HELPERS._fake_install_root
_read_jsonl = _HELPERS._read_jsonl


def _run_dry(tmp_path: Path, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run install.sh --dry-run with a minimal real-HOME sandbox."""
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


# ── dry-run assertions ─────────────────────────────────────────────────────────

def test_repo_root_in_ancestor_dir_flag(tmp_path: Path) -> None:
    """--repo-root passes through to ancestor launch_seat --dir (dry-run verification)."""
    target_dir = tmp_path / "myrepo"
    target_dir.mkdir()
    result = _run_dry(tmp_path, [
        "--project", "testproj",
        "--repo-root", str(target_dir),
        "--dry-run",
    ])
    assert result.returncode == 0, result.stderr
    # dry-run should print the project-local.toml write line
    assert "project-local.toml" in result.stdout, (
        f"Expected 'project-local.toml' in dry-run output:\n{result.stdout}"
    )
    # dry-run should print ancestor launch with --dir pointing to target_dir
    assert f"--dir {target_dir}" in result.stdout, (
        f"Expected '--dir {target_dir}' in dry-run output:\n{result.stdout}"
    )


def test_nonexistent_repo_root_dies_2(tmp_path: Path) -> None:
    result = _run_dry(tmp_path, [
        "--project", "testproj",
        "--repo-root", str(tmp_path / "nonexistent"),
        "--dry-run",
    ])
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}: {result.stderr}"
    assert "repo-root" in result.stderr.lower() or "INVALID_REPO_ROOT" in result.stderr


def test_default_behavior_unchanged_without_repo_root(tmp_path: Path) -> None:
    """Without --repo-root, install succeeds and writes project-local.toml."""
    result = _run_dry(tmp_path, ["--project", "testproj", "--dry-run"])
    assert result.returncode == 0, result.stderr
    assert "project-local.toml" in result.stdout


# ── non-dry-run: actually write project-local.toml and verify content ─────────

def test_repo_root_written_to_project_local_toml_content(tmp_path: Path) -> None:
    """Non-dry-run: project-local.toml repo_root field equals the --repo-root value."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    target_dir = tmp_path / "myrepo"
    target_dir.mkdir()

    result = subprocess.run(
        [
            "bash",
            str(root / "scripts" / "install.sh"),
            "--project", "projfoo",
            "--repo-root", str(target_dir),
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
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "projfoo" / "project-local.toml"
    assert local_toml.exists(), f"project-local.toml not written. stdout:\n{result.stdout}"
    content = local_toml.read_text(encoding="utf-8")
    assert f'repo_root = "{target_dir}"' in content, (
        f"Expected repo_root = \"{target_dir}\" in project-local.toml:\n{content}"
    )


def test_default_repo_root_is_clawseat_root(tmp_path: Path) -> None:
    """Non-dry-run: without --repo-root, project-local.toml uses the clawseat repo root."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)

    result = subprocess.run(
        ["bash", str(root / "scripts" / "install.sh"), "--project", "projbar"],
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
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "projbar" / "project-local.toml"
    assert local_toml.exists(), f"project-local.toml not written. stdout:\n{result.stdout}"
    content = local_toml.read_text(encoding="utf-8")
    # The default PROJECT_REPO_ROOT = REPO_ROOT = the fake root directory
    assert f'repo_root = "{root}"' in content, (
        f"Expected repo_root = \"{root}\" in project-local.toml:\n{content}"
    )
