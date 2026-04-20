"""Tests for core/preflight.py."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core import preflight as mod


def _write_dynamic_profile(
    path: Path,
    *,
    project: str = "install",
    include_schema: bool = True,
) -> Path:
    lines = [
        'version = 1',
        f'profile_name = "{project}"',
        f'project_name = "{project}"',
        "",
        "[dynamic_roster]",
        "enabled = true",
        'session_root = "~/.agents/sessions"',
    ]
    if include_schema:
        lines.extend(
            [
                'materialized_seats = ["koder", "planner"]',
                'bootstrap_seats = ["koder"]',
                'default_start_seats = ["koder", "planner"]',
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_openclaw_workspace(openclaw_home: Path, profile_path: Path, *, project: str = "install") -> None:
    workspace = openclaw_home / "workspace-koder"
    workspace.mkdir(parents=True, exist_ok=True)
    for name in ("IDENTITY.md", "SOUL.md", "AGENTS.md", "TOOLS.md", "MEMORY.md"):
        (workspace / name).write_text(f"# {name}\n", encoding="utf-8")
    (workspace / "WORKSPACE_CONTRACT.toml").write_text(
        "\n".join(
            [
                'version = 1',
                'seat_id = "koder"',
                f'project = "{project}"',
                f'profile = "{profile_path}"',
                'backend_seats = ["planner"]',
                'default_backend_start_seats = ["planner"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _install_openclaw_skills(fake_root: Path, openclaw_home: Path) -> None:
    for skill_name in set(mod.REQUIRED_OPENCLAW_GLOBAL_SKILLS) | set(mod.REQUIRED_OPENCLAW_KODER_SKILLS):
        source = fake_root / "core" / "skills" / skill_name
        source.mkdir(parents=True, exist_ok=True)
        (source / "SKILL.md").write_text(f"# {skill_name}\n", encoding="utf-8")
    for skill_name in mod.REQUIRED_OPENCLAW_GLOBAL_SKILLS:
        destination = openclaw_home / "skills" / skill_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to((fake_root / "core" / "skills" / skill_name).resolve())
    for skill_name in mod.REQUIRED_OPENCLAW_KODER_SKILLS:
        destination = openclaw_home / "workspace-koder" / "skills" / skill_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to((fake_root / "core" / "skills" / skill_name).resolve())


@pytest.fixture()
def fake_clawseat(tmp_path: Path) -> Path:
    markers = [
        "core/scripts/agent_admin.py",
        "core/harness_adapter.py",
        "core/adapter/clawseat_adapter.py",
        "core/skills/gstack-harness/scripts/_common.py",
        "adapters/harness/tmux-cli/adapter.py",
    ]
    for marker in markers:
        target = tmp_path / marker
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# stub\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def mock_skill_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod,
        "_check_skills",
        lambda: [mod.PreflightItem("skill_stub", mod.PreflightStatus.PASS, "ok")],
    )


def _patch_runtime_tools(monkeypatch: pytest.MonkeyPatch, *, backend_cli: str = "codex") -> None:
    def fake_which(name: str) -> str | None:
        available = {
            "python3": "/usr/bin/python3",
            "tmux": "/opt/homebrew/bin/tmux",
            "node": "/opt/homebrew/bin/node",
            "openclaw": "/opt/homebrew/bin/openclaw",
            backend_cli: f"/opt/homebrew/bin/{backend_cli}",
            "brew": "/opt/homebrew/bin/brew",
        }
        return available.get(name)

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["python3", "-c"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="(3, 12)", stderr="")
        if cmd and cmd[0] == "tmux":
            return subprocess.CompletedProcess(cmd, 0, stdout="0: 1 windows\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr("subprocess.run", fake_run)


def test_preflight_all_pass_local(
    monkeypatch: pytest.MonkeyPatch,
    fake_clawseat: Path,
    tmp_path: Path,
    mock_skill_check: None,
) -> None:
    monkeypatch.setenv("CLAWSEAT_ROOT", str(fake_clawseat))
    monkeypatch.setattr(mod, "_try_resolve_clawseat_root", lambda: fake_clawseat)
    _patch_runtime_tools(monkeypatch, backend_cli="claude")

    profile = _write_dynamic_profile(tmp_path / "profiles" / "test-profile-dynamic.toml", project="test")
    monkeypatch.setattr(mod, "_dynamic_profile_path", lambda _project: profile)

    sessions_root = tmp_path / "sessions"
    (sessions_root / "test").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SESSIONS_ROOT", str(sessions_root))

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    (tmp_path / ".gstack" / "repos" / "gstack" / ".agents" / "skills").mkdir(parents=True, exist_ok=True)

    result = mod.preflight_check("test")

    assert result.all_pass is True
    assert result.has_hard_blocked is False
    assert result.has_retryable is False


def test_openclaw_runtime_all_pass_with_single_backend_cli(
    monkeypatch: pytest.MonkeyPatch,
    fake_clawseat: Path,
    tmp_path: Path,
    mock_skill_check: None,
) -> None:
    openclaw_home = tmp_path / ".openclaw"
    profile = _write_dynamic_profile(tmp_path / "profiles" / "install-profile-dynamic.toml")
    _write_openclaw_workspace(openclaw_home, profile)
    _install_openclaw_skills(fake_clawseat, openclaw_home)

    monkeypatch.setenv("CLAWSEAT_ROOT", str(fake_clawseat))
    monkeypatch.setattr(mod, "_try_resolve_clawseat_root", lambda: fake_clawseat)
    monkeypatch.setattr(mod, "CANONICAL_OPENCLAW_REPO", fake_clawseat)
    monkeypatch.setenv("OPENCLAW_HOME", str(openclaw_home))
    monkeypatch.setattr(mod, "_dynamic_profile_path", lambda _project: profile)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    (tmp_path / ".gstack" / "repos" / "gstack" / ".agents" / "skills").mkdir(parents=True, exist_ok=True)

    sessions_root = tmp_path / "sessions"
    (sessions_root / "install").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SESSIONS_ROOT", str(sessions_root))

    _patch_runtime_tools(monkeypatch, backend_cli="codex")

    result = mod.preflight_check("install", runtime="openclaw")
    item_names = [item.name for item in result.items]

    assert result.all_pass is True
    assert any(
        item.name == "backend_cli" and item.status == mod.PreflightStatus.PASS
        for item in result.items
    )
    assert "claude" not in item_names
    assert "codex" not in item_names
    assert "gemini" not in item_names


def test_openclaw_runtime_requires_canonical_checkout(
    monkeypatch: pytest.MonkeyPatch,
    fake_clawseat: Path,
    tmp_path: Path,
) -> None:
    canonical_root = tmp_path / ".clawseat"
    for marker in (
        "core/scripts/agent_admin.py",
        "core/harness_adapter.py",
    ):
        target = canonical_root / marker
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# stub\n", encoding="utf-8")
    monkeypatch.setenv("CLAWSEAT_ROOT", str(fake_clawseat))
    monkeypatch.setattr(mod, "CANONICAL_OPENCLAW_REPO", canonical_root)

    item = mod._check_clawseat_root(runtime="openclaw")

    assert item.status == mod.PreflightStatus.HARD_BLOCKED
    assert str(canonical_root) in item.message


def test_install_profile_missing_materialized_schema_is_retryable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile = _write_dynamic_profile(
        tmp_path / "profiles" / "install-profile-dynamic.toml",
        include_schema=False,
    )
    monkeypatch.setattr(mod, "_dynamic_profile_path", lambda _project: profile)

    item = mod._check_dynamic_profile("install", runtime="openclaw")

    assert item.status == mod.PreflightStatus.RETRYABLE
    assert "materialized_seats" in item.message


def test_auto_fix_openclaw_skill_bundle_runs_installer(
    monkeypatch: pytest.MonkeyPatch,
    fake_clawseat: Path,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(mod, "_resolve_clawseat_root_from_env", lambda: fake_clawseat)

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    item = mod.PreflightItem(
        name="openclaw_skill_bundle",
        status=mod.PreflightStatus.RETRYABLE,
        message="drift",
        fix_command="repair",
    )

    fixed = mod.auto_fix(item, "install", runtime="openclaw")

    assert fixed.status == mod.PreflightStatus.PASS
    assert any("install_openclaw_bundle.py" in part for part in calls[0])


def test_auto_fix_workspace_koder_uses_init_koder_for_missing_contract(
    monkeypatch: pytest.MonkeyPatch,
    fake_clawseat: Path,
    tmp_path: Path,
) -> None:
    profile = _write_dynamic_profile(tmp_path / "profiles" / "install-profile-dynamic.toml")
    openclaw_home = tmp_path / ".openclaw"
    calls: list[list[str]] = []

    monkeypatch.setattr(mod, "_resolve_clawseat_root_from_env", lambda: fake_clawseat)
    monkeypatch.setattr(mod, "_dynamic_profile_path", lambda _project: profile)
    monkeypatch.setenv("OPENCLAW_HOME", str(openclaw_home))

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    item = mod.PreflightItem(
        name="workspace_koder",
        status=mod.PreflightStatus.RETRYABLE,
        message="missing",
        fix_command="repair",
    )

    fixed = mod.auto_fix(item, "install", runtime="openclaw")

    assert fixed.status == mod.PreflightStatus.PASS
    assert any("init_koder.py" in part for part in calls[0])


def test_tmux_not_installed_is_hard_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)

    install_item, server_item = mod._check_tmux()

    assert install_item.status == mod.PreflightStatus.HARD_BLOCKED
    assert server_item.status == mod.PreflightStatus.HARD_BLOCKED


def test_optional_claude_cli_is_warning_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)

    item = mod._check_optional_cli(
        "claude",
        "Claude Code CLI",
        "npm install -g @anthropic-ai/claude-code",
    )

    assert item.status == mod.PreflightStatus.WARNING
