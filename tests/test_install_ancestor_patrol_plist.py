from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


_HELPERS_PATH = Path(__file__).with_name("test_install_isolation.py")
_HELPERS_SPEC = importlib.util.spec_from_file_location("test_install_isolation_helpers", _HELPERS_PATH)
assert _HELPERS_SPEC is not None and _HELPERS_SPEC.loader is not None
_HELPERS = importlib.util.module_from_spec(_HELPERS_SPEC)
_HELPERS_SPEC.loader.exec_module(_HELPERS)

_fake_install_root = _HELPERS._fake_install_root


def test_install_writes_and_bootstraps_ancestor_patrol_plist(tmp_path: Path) -> None:
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    launchctl_log = tmp_path / "launchctl.log"
    plutil_log = tmp_path / "plutil.log"

    result = subprocess.run(
        ["bash", str(root / "scripts" / "install.sh"), "--project", "patrol50", "--provider", "minimax"],
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
            "LAUNCHCTL_LOG_FILE": str(launchctl_log),
            "PLUTIL_LOG_FILE": str(plutil_log),
        },
        check=False,
    )

    assert result.returncode == 0, result.stderr

    plist_path = home / "Library" / "LaunchAgents" / "com.clawseat.patrol50.ancestor-patrol.plist"
    assert plist_path.is_file()
    plist_text = plist_path.read_text(encoding="utf-8")

    assert "com.clawseat.patrol50.ancestor-patrol" in plist_text
    assert "session-name ancestor --project 'patrol50'" in plist_text
    assert str(root / "core" / "shell-scripts" / "send-and-verify.sh") in plist_text
    assert "{PROJECT}" not in plist_text
    assert "{CADENCE_SECONDS}" not in plist_text
    assert "{CLAWSEAT_ROOT}" not in plist_text
    assert "{LOG_DIR}" not in plist_text
    assert "{TOOL}" not in plist_text
    assert "={PROJECT}-ancestor-{TOOL}" not in plist_text
    assert (home / ".agents" / "tasks" / "patrol50" / "patrol" / "logs").is_dir()

    launchctl_lines = launchctl_log.read_text(encoding="utf-8").splitlines()
    assert f"bootout gui/{os.getuid()}/com.clawseat.patrol50.ancestor-patrol" in launchctl_lines
    assert f"bootstrap gui/{os.getuid()} {plist_path}" in launchctl_lines

    plutil_lines = plutil_log.read_text(encoding="utf-8").splitlines()
    assert plutil_lines == [f"-lint {plist_path}"]


def test_install_dry_run_reports_ancestor_patrol_launchagent(tmp_path: Path) -> None:
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)

    result = subprocess.run(
        ["bash", str(root / "scripts" / "install.sh"), "--dry-run", "--project", "patrol51", "--provider", "minimax"],
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

    combined = result.stdout + result.stderr
    plist_path = home / "Library" / "LaunchAgents" / "com.clawseat.patrol51.ancestor-patrol.plist"

    assert result.returncode == 0, result.stderr
    assert f"[dry-run] render {root / 'core' / 'templates' / 'ancestor-patrol.plist.in'} -> {plist_path}" in combined
    assert f"[dry-run] launchctl bootstrap gui/{os.getuid()} {plist_path}" in combined
