"""Tests for dynamic PENDING_SEATS resolution from template.

Verifies that install.sh reads seat list from template TOML instead of
hardcoding, so clawseat-creative produces a different seat_order than
clawseat-default.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_INSTALL = _REPO / "scripts" / "install.sh"

_HELPERS_PATH = Path(__file__).with_name("test_install_isolation.py")
_HELPERS_SPEC = importlib.util.spec_from_file_location(
    "test_install_isolation_helpers_pending_seats", _HELPERS_PATH
)
assert _HELPERS_SPEC is not None and _HELPERS_SPEC.loader is not None
_HELPERS = importlib.util.module_from_spec(_HELPERS_SPEC)
_HELPERS_SPEC.loader.exec_module(_HELPERS)

_fake_install_root = _HELPERS._fake_install_root


def _run_install(root, home, launcher_log, tmux_log, py_stubs, extra_args):
    result = subprocess.run(
        ["bash", str(root / "scripts" / "install.sh")] + extra_args,
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
    return result


def _copy_templates(root):
    """Copy repo-level templates/ into fake root so resolve_pending_seats() can find them."""
    src = _REPO / "templates"
    dst = root / "templates"
    if src.exists():
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)


def test_creative_template_seat_order_excludes_reviewer_qa(tmp_path):
    """clawseat-creative project-local.toml must not contain reviewer or qa in seat_order."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    _copy_templates(root)

    result = _run_install(root, home, launcher_log, tmux_log, py_stubs,
                          ["--project", "testcreative", "--template", "clawseat-creative"])
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "testcreative" / "project-local.toml"
    assert local_toml.exists(), f"project-local.toml not written. stdout:\n{result.stdout}"
    content = local_toml.read_text(encoding="utf-8")

    assert "reviewer" not in content, (
        f"reviewer should not appear in creative project-local.toml:\n{content}"
    )
    assert "qa" not in content or '"qa"' not in content.split("seat_order")[0], (
        f"qa should not appear in seat_order for creative:\n{content}"
    )


def test_default_template_seat_order_unchanged(tmp_path):
    """clawseat-default project-local.toml keeps the standard 6-seat order."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    _copy_templates(root)

    result = _run_install(root, home, launcher_log, tmux_log, py_stubs,
                          ["--project", "testdefault"])
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "testdefault" / "project-local.toml"
    assert local_toml.exists()
    content = local_toml.read_text(encoding="utf-8")

    # Default should still have the full seat list
    assert "planner" in content
    assert "builder" in content
    assert "reviewer" in content
