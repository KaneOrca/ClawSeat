"""Tests for bootstrap-aware preflight phase routing and CLI exit codes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from core import preflight as pf


def _item(name: str, status: pf.PreflightStatus = pf.PreflightStatus.PASS, message: str = "ok"):
    return pf.PreflightItem(name=name, status=status, message=message)


def _passthrough_check(name: str):
    return lambda *args, **kwargs: _item(name)


def test_preflight_default_runtime_checks_runtime_only_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_check_clawseat_root", _passthrough_check("CLAWSEAT_ROOT"))
    monkeypatch.setattr(pf, "_check_python", _passthrough_check("python3"))
    monkeypatch.setattr(pf, "_check_tomllib", _passthrough_check("tomllib"))
    monkeypatch.setattr(
        pf,
        "_check_tmux",
        lambda: (_item("tmux"), _item("tmux_server")),
    )
    monkeypatch.setattr(pf, "_resolve_clawseat_root_from_env", lambda: tmp_path)
    monkeypatch.setattr(pf, "_check_repo_integrity", lambda root: _item("repo_integrity"))
    monkeypatch.setattr(pf, "_check_dynamic_profile", _passthrough_check("dynamic_profile"))
    monkeypatch.setattr(pf, "_check_session_binding_dir", _passthrough_check("session_binding_dir"))
    monkeypatch.setattr(pf, "_check_skills", lambda active_roles=None: [_item("skill_demo")])
    monkeypatch.setattr(
        pf,
        "_check_optional_cli",
        lambda binary, label, install_hint: _item(binary),
    )
    monkeypatch.setattr(pf, "_check_iterm2", lambda: pytest.fail("bootstrap-only check should not run"))
    monkeypatch.setattr(
        pf,
        "_check_iterm2_python_module",
        lambda: pytest.fail("bootstrap-only check should not run"),
    )
    monkeypatch.setattr(
        pf,
        "_check_claude_required",
        lambda: pytest.fail("bootstrap-only check should not run"),
    )

    result = pf.preflight_check("demo")

    names = [item.name for item in result.items]
    assert names[:5] == ["CLAWSEAT_ROOT", "python3", "tomllib", "tmux", "tmux_server"]
    assert "dynamic_profile" in names
    assert "session_binding_dir" in names
    assert "skill_demo" in names
    assert "claude" in names
    assert "codex" in names
    assert "lark-cli" in names
    assert "iterm2" not in names
    assert "iterm2_python" not in names
    assert "claude_required" not in names


def test_preflight_bootstrap_skips_runtime_only_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_check_clawseat_root", _passthrough_check("CLAWSEAT_ROOT"))
    monkeypatch.setattr(pf, "_check_python", _passthrough_check("python3"))
    monkeypatch.setattr(pf, "_check_tomllib", _passthrough_check("tomllib"))
    monkeypatch.setattr(
        pf,
        "_check_tmux",
        lambda: (_item("tmux"), _item("tmux_server")),
    )
    monkeypatch.setattr(pf, "_resolve_clawseat_root_from_env", lambda: tmp_path)
    monkeypatch.setattr(pf, "_check_repo_integrity", lambda root: _item("repo_integrity"))
    monkeypatch.setattr(
        pf,
        "_check_dynamic_profile",
        lambda *args, **kwargs: pytest.fail("runtime-only check should not run"),
    )
    monkeypatch.setattr(
        pf,
        "_check_session_binding_dir",
        lambda *args, **kwargs: pytest.fail("runtime-only check should not run"),
    )
    monkeypatch.setattr(
        pf,
        "_check_skills",
        lambda active_roles=None: pytest.fail("runtime-only check should not run"),
    )
    monkeypatch.setattr(
        pf,
        "_check_optional_cli",
        lambda binary, label, install_hint: _item(binary),
    )
    monkeypatch.setattr(pf, "_check_iterm2", _passthrough_check("iterm2"))
    monkeypatch.setattr(pf, "_check_iterm2_python_module", _passthrough_check("iterm2_python"))
    monkeypatch.setattr(pf, "_check_claude_required", _passthrough_check("claude_required"))

    result = pf.preflight_check("demo", phase="bootstrap")

    names = [item.name for item in result.items]
    assert names[:5] == ["CLAWSEAT_ROOT", "python3", "tomllib", "tmux", "tmux_server"]
    assert "iterm2" in names
    assert "iterm2_python" in names
    assert "claude_required" in names
    assert "dynamic_profile" not in names
    assert "session_binding_dir" not in names
    assert "skill_demo" not in names
    assert "claude" not in names
    assert "codex" in names
    assert "lark-cli" in names


def test_preflight_rejects_invalid_phase(monkeypatch):
    with pytest.raises(ValueError, match="unsupported preflight phase"):
        pf.preflight_check("demo", phase="invalid")


def test_iterm2_python_module_uses_real_home_in_subprocess_env(monkeypatch, tmp_path):
    sandbox_home = str(tmp_path / ".agent-runtime" / "identities" / "test" / "home")
    real_home = tmp_path / "real-user-home"

    monkeypatch.setattr(pf.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("HOME", sandbox_home)
    monkeypatch.setattr(pf, "real_user_home", lambda: real_home)

    recorded: dict[str, object] = {}

    class _Result:
        returncode = 0

    def _fake_run(cmd, capture_output, text, timeout, check, env):
        recorded["cmd"] = cmd
        recorded["env"] = env
        return _Result()

    monkeypatch.setattr(pf.subprocess, "run", _fake_run)

    item = pf._check_iterm2_python_module()

    assert item.status == pf.PreflightStatus.PASS
    assert recorded["cmd"] == [sys.executable, "-c", "import iterm2"]
    assert isinstance(recorded["env"], dict)
    assert recorded["env"]["HOME"] == str(real_home)
    assert recorded["env"]["HOME"] != sandbox_home
    assert recorded["env"]["PATH"] == os.environ["PATH"]


def test_main_returns_nonzero_when_hard_blocked(monkeypatch, capsys):
    result = pf.PreflightResult(
        all_pass=False,
        has_hard_blocked=True,
        has_retryable=False,
        items=[_item("blocked", pf.PreflightStatus.HARD_BLOCKED, "boom")],
        hard_blocked_items=[_item("blocked", pf.PreflightStatus.HARD_BLOCKED, "boom")],
    )
    monkeypatch.setattr(pf, "preflight_check", lambda project, phase="runtime": result)
    monkeypatch.setattr(sys, "argv", ["preflight.py", "--project", "demo", "--phase", "bootstrap"])

    rc = pf.main()
    out = capsys.readouterr().out

    assert rc == 2
    assert "preflight_check: FAIL [demo]" in out
    assert "[✗] blocked: boom" in out
