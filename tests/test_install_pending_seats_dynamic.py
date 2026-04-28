"""Tests for dynamic PENDING_SEATS resolution from template.

Verifies that install.sh reads seat list from template TOML instead of
hardcoding, so creative and engineering produce different seat_order values.
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


def test_creative_template_seat_order_excludes_reviewer(tmp_path):
    """clawseat-creative project-local.toml has the 5-seat creative roster."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    _copy_templates(root)

    result = _run_install(root, home, launcher_log, tmux_log, py_stubs,
                          ["--project", "testcreative", "--template", "clawseat-creative"])
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "testcreative" / "project-local.toml"
    assert local_toml.exists(), f"project-local.toml not written. stdout:\n{result.stdout}"
    content = local_toml.read_text(encoding="utf-8")

    assert 'seat_order = ["memory", "planner", "builder", "patrol", "designer"]' in content
    assert "reviewer" not in content, (
        f"reviewer should not appear in creative project-local.toml:\n{content}"
    )


def test_creative_template_builder_is_codex_designer_is_gemini(tmp_path):
    """clawseat-creative: builder override uses codex, designer uses gemini."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    _copy_templates(root)

    result = _run_install(root, home, launcher_log, tmux_log, py_stubs,
                          ["--project", "harnesstest", "--template", "clawseat-creative"])
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "harnesstest" / "project-local.toml"
    assert local_toml.exists()
    content = local_toml.read_text(encoding="utf-8")

    # Find the builder override block (lines between id = "builder" and next [[overrides]])
    lines = content.splitlines()
    in_builder = False
    in_designer = False
    builder_lines: list[str] = []
    designer_lines: list[str] = []
    for line in lines:
        if '[[overrides]]' in line:
            in_builder = False
            in_designer = False
        if 'id = "builder"' in line:
            in_builder = True
        if 'id = "designer"' in line:
            in_designer = True
        if in_builder:
            builder_lines.append(line)
        if in_designer:
            designer_lines.append(line)

    builder_text = "\n".join(builder_lines)
    designer_text = "\n".join(designer_lines)

    assert "codex" in builder_text, (
        f"builder override should specify codex:\n{builder_text}\n\nFull TOML:\n{content}"
    )
    assert "gemini" in designer_text, (
        f"designer override should specify gemini:\n{designer_text}\n\nFull TOML:\n{content}"
    )


def test_creative_codex_gemini_seats_have_no_model_override(tmp_path):
    """builder(codex) and designer(gemini) overrides must NOT have a model field."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    _copy_templates(root)

    result = _run_install(root, home, launcher_log, tmux_log, py_stubs,
                          ["--project", "modeltest", "--template", "clawseat-creative",
                           "--provider", "minimax", "--api-key", "sk-test"])
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "modeltest" / "project-local.toml"
    assert local_toml.exists()
    content = local_toml.read_text(encoding="utf-8")

    # Parse per-seat sections
    lines = content.splitlines()
    in_builder = in_designer = False
    builder_lines: list[str] = []
    designer_lines: list[str] = []
    for line in lines:
        if '[[overrides]]' in line:
            in_builder = in_designer = False
        if 'id = "builder"' in line:
            in_builder = True
        if 'id = "designer"' in line:
            in_designer = True
        if in_builder:
            builder_lines.append(line)
        if in_designer:
            designer_lines.append(line)

    builder_text = "\n".join(builder_lines)
    designer_text = "\n".join(designer_lines)

    assert "model" not in builder_text, (
        f"codex builder override must not have model field:\n{builder_text}"
    )
    assert "model" not in designer_text, (
        f"gemini designer override must not have model field:\n{designer_text}"
    )


def test_engineering_patrol_seat_gets_template_model(tmp_path):
    """clawseat-engineering: patrol (claude/api/minimax) override must carry model = MiniMax-M2.7-highspeed
    from the template TOML, not the ancestor's selected model."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    _copy_templates(root)

    # Use anthropic provider for ancestor; patrol seat should still get its own model.
    result = _run_install(root, home, launcher_log, tmux_log, py_stubs,
                          ["--project", "engmodeltest", "--template", "clawseat-engineering"])
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "engmodeltest" / "project-local.toml"
    assert local_toml.exists()
    content = local_toml.read_text(encoding="utf-8")

    lines = content.splitlines()
    in_patrol = False
    patrol_lines: list[str] = []
    for line in lines:
        if "[[overrides]]" in line:
            in_patrol = False
        if 'id = "patrol"' in line:
            in_patrol = True
        if in_patrol:
            patrol_lines.append(line)

    patrol_text = "\n".join(patrol_lines)
    assert "MiniMax-M2.7-highspeed" in patrol_text, (
        f"patrol override must carry template-specified model MiniMax-M2.7-highspeed:\n{patrol_text}"
        f"\n\nFull TOML:\n{content}"
    )


def test_engineering_template_seat_order_includes_reviewer(tmp_path):
    """clawseat-engineering project-local.toml keeps the 6-seat engineering order."""
    root, home, launcher_log, tmux_log, py_stubs = _fake_install_root(tmp_path)
    _copy_templates(root)

    result = _run_install(root, home, launcher_log, tmux_log, py_stubs,
                          ["--project", "testengineering", "--template", "clawseat-engineering"])
    assert result.returncode == 0, result.stderr

    local_toml = home / ".agents" / "tasks" / "testengineering" / "project-local.toml"
    assert local_toml.exists()
    content = local_toml.read_text(encoding="utf-8")

    assert 'seat_order = ["memory", "planner", "builder", "reviewer", "patrol", "designer"]' in content
