"""Smoke coverage for the 16-module agent_admin control plane and the
21-script gstack-harness runtime (audit H5 + H6).

These aren't deep behavioral tests — they're broad CLI/import smoke
that catches `NameError` / `ImportError` / argparse wiring regressions
the second they hit HEAD. Before this file every module under
`core/scripts/agent_admin_*.py` and
`core/skills/gstack-harness/scripts/*.py` was reachable only through
full-stack integration runs that require tmux + real profiles + Feishu.

Each test either:
- imports the module (catches import-time explosions like bad re-exports)
- invokes the CLI with `--help` (catches argparse regressions)
- exercises a pure function with canned inputs (catches the subset of
  logic that doesn't depend on the runtime)

Deep behavioral tests belong in their own files (test_store_list.py,
test_dispatch_task.py, etc.) when specific features are hardened.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_ADMIN = _REPO / "core" / "scripts"
_HARNESS = _REPO / "core" / "skills" / "gstack-harness" / "scripts"
_MIGRATION = _REPO / "core" / "migration"
for _p in (_ADMIN, _HARNESS, _MIGRATION):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ── H5: control-plane module import + help smoke ────────────────────

ADMIN_MODULES = [
    "agent_admin",
    "agent_admin_commands",
    "agent_admin_config",
    "agent_admin_crud",
    "agent_admin_heartbeat",
    "agent_admin_info",
    "agent_admin_parser",
    "agent_admin_resolve",
    "agent_admin_runtime",
    "agent_admin_session",
    "agent_admin_store",
    "agent_admin_switch",
    "agent_admin_template",
    "agent_admin_window",
    "agent_admin_workspace",
    # agent_admin_legacy and agent_admin_tui are imported lazily/only under
    # CLI flags; skip them here to avoid pulling extra deps.
]


@pytest.mark.parametrize("module_name", ADMIN_MODULES)
def test_admin_module_imports_cleanly(module_name: str) -> None:
    """Import must not raise. Catches cross-module symbol breakage
    (the whole reason `agent_admin` was split into 15 focused files in
    the first place).

    We do NOT drop the cached copy before importing — doing so would
    force a reload and give the module a different object identity for
    its constants (e.g. DEFAULT_PATH), which a sibling test
    `test_tool_binaries_resolution.test_runtime_reuses_config_default_path`
    depends on. The smoke value here is "the module body runs without
    raising", which the first load already proved. Sufficient.
    """
    module = importlib.import_module(module_name)
    assert module is not None


def test_agent_admin_cli_help_runs() -> None:
    """`python agent_admin.py --help` must exit 0 with the usage block.
    Wires every subparser, so a broken argparse signature anywhere in
    the control plane surfaces here."""
    result = subprocess.run(
        [sys.executable, str(_ADMIN / "agent_admin.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout + result.stderr
    # Spot-check a handful of top-level commands known to be wired up.
    for expected in ("project", "engineer", "session", "window"):
        assert expected in out, f"subcommand `{expected}` missing from help"


def test_skill_manager_cli_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(_ADMIN / "skill_manager.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "check" in result.stdout + result.stderr


def test_agent_admin_config_supported_matrix_complete() -> None:
    """SUPPORTED_RUNTIME_MATRIX must cover every known backend CLI so
    provider validation never accidentally drops one."""
    import agent_admin_config as cfg
    for tool in ("claude", "codex", "gemini"):
        assert tool in cfg.SUPPORTED_RUNTIME_MATRIX, tool
        tool_map = cfg.SUPPORTED_RUNTIME_MATRIX[tool]
        assert "oauth" in tool_map, f"{tool} should support oauth"
        assert tool_map["oauth"], f"{tool} oauth should have at least one provider"


def test_agent_admin_store_load_toml_roundtrip(tmp_path: Path) -> None:
    import agent_admin as aa

    p = tmp_path / "t.toml"
    p.write_text('name = "hello"\nvalue = 42\n', encoding="utf-8")
    data = aa.load_toml(p)
    assert data == {"name": "hello", "value": 42}


def test_agent_admin_workspace_renderers_produce_strings() -> None:
    """Pure text renderers live in agent_admin_workspace. They shouldn't
    crash on empty-engineer fixtures."""
    from agent_admin_workspace import render_role_line

    # render_role_line takes a role+engineer dataclass-ish shape; we
    # feed a minimal object. If signature drifts, this will fail.
    import agent_admin as aa
    engineer = aa.Engineer(
        engineer_id="stub",
        display_name="stub",
        role="builder",
    )
    line = render_role_line(engineer)
    assert isinstance(line, str)
    assert "builder" in line


# ── H6: gstack-harness runtime smoke ────────────────────────────────

HARNESS_SCRIPTS_WITH_HELP = [
    "dispatch_task.py",
    "complete_handoff.py",
    "notify_seat.py",
    "verify_handoff.py",
    "provision_heartbeat.py",
    "send_delegation_report.py",
    "render_console.py",
    "bootstrap_harness.py",
    "ack_contract.py",
    "migrate_profile.py",
    "start_seat.py",
]


@pytest.mark.parametrize("script", HARNESS_SCRIPTS_WITH_HELP)
def test_harness_script_help_runs(script: str) -> None:
    """Every CLI entry point must at least show --help without crashing.
    Catches argparse regressions and broken relative imports within
    the harness scripts dir."""
    path = _HARNESS / script
    if not path.exists():
        pytest.skip(f"{script} not present on this branch")
    result = subprocess.run(
        [sys.executable, str(path), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(_HARNESS),
    )
    assert result.returncode == 0, f"{script} --help failed: {result.stderr}"
    assert "usage" in (result.stdout + result.stderr).lower()


HARNESS_SHARED_MODULES = [
    "_utils",
    "_task_io",
    "_feishu",
    "_heartbeat_helpers",
    "_common",
]


@pytest.mark.parametrize("module_name", HARNESS_SHARED_MODULES)
def test_harness_shared_module_imports(module_name: str) -> None:
    # Same "don't force reload" reasoning as the admin-module smoke above.
    module = importlib.import_module(module_name)
    assert module is not None


def test_harness_task_io_renders_todo(tmp_path: Path) -> None:
    """Pure `write_todo` should produce TODO.md content with the
    schema documented in CANONICAL-FLOW.md §9."""
    from _task_io import write_todo

    target = tmp_path / "TODO.md"
    write_todo(
        target,
        task_id="T1",
        project="demo",
        owner="builder-1",
        status="pending",
        title="demo task",
        objective="do things",
        source="planner",
        reply_to="planner",
    )
    body = target.read_text(encoding="utf-8")
    for marker in ("task_id: T1", "project: demo", "owner: builder-1", "status: pending", "# Objective", "# Dispatch"):
        assert marker in body, marker


def test_harness_task_io_appends_consumed_ack_idempotent(tmp_path: Path) -> None:
    from _task_io import append_consumed_ack, find_consumed_ack

    delivery = tmp_path / "DELIVERY.md"
    delivery.write_text("task_id: T2\nstatus: completed\n", encoding="utf-8")
    first = append_consumed_ack(delivery, task_id="T2", source="builder-1")
    second = append_consumed_ack(delivery, task_id="T2", source="builder-1")
    assert first == second, "append_consumed_ack must be idempotent for the same (task, source)"
    assert find_consumed_ack(delivery, task_id="T2", source="builder-1") == first


# ── migration/ layer smoke ──────────────────────────────────────────

MIGRATION_SCRIPTS = [
    "dispatch_task_dynamic.py",
    "notify_seat_dynamic.py",
    "complete_handoff_dynamic.py",
    "render_console_dynamic.py",
]


@pytest.mark.parametrize("script", MIGRATION_SCRIPTS)
def test_migration_script_help_runs(script: str) -> None:
    path = _MIGRATION / script
    if not path.exists():
        pytest.skip(f"{script} not present on this branch")
    result = subprocess.run(
        [sys.executable, str(path), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(_MIGRATION),
    )
    assert result.returncode == 0, f"{script} --help failed: {result.stderr}"
