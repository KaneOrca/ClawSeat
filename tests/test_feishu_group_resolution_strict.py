"""C1 guardrail tests: strict project→Feishu-group resolution.

The P0 danger in multi-project mode is not "failed to send" — it is
"guessed the wrong group and sent successfully". These tests lock the
invariant that, when a project is given but has no explicit per-project
binding, resolution MUST fail loudly instead of falling back to the
first group in ~/.openclaw/openclaw.json or the first group seen in
any sessions.json.

The matching pre-C1 code would take a project with no binding and
return e.g. cartooner's group for an install closeout. That silent
guess is exactly what these tests forbid.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest import mock

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "core" / "skills" / "gstack-harness" / "scripts"))


@pytest.fixture()
def clean_env(monkeypatch):
    for key in (
        "CLAWSEAT_REAL_HOME",
        "LARK_CLI_HOME",
        "AGENT_HOME",
        "CLAWSEAT_FEISHU_GROUP_ID",
        "OPENCLAW_FEISHU_GROUP_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


def _reload_feishu():
    for name in ("_feishu", "_utils"):
        sys.modules.pop(name, None)
    import _feishu  # noqa: F401
    importlib.reload(_feishu)
    return _feishu


def _write_openclaw_global(real_home: Path, group_id: str) -> None:
    """Seed a global openclaw.json with one feishu group. Pre-C1 this was
    the silent fallback. Post-C1 it must NOT leak into strict lookups."""
    openclaw = real_home / ".openclaw"
    openclaw.mkdir(parents=True, exist_ok=True)
    (openclaw / "openclaw.json").write_text(
        '{"channels":{"feishu":{"groups":{"%s":{}}}}}' % group_id
    )


def _write_binding(real_home: Path, project: str, group_id: str) -> Path:
    binding_dir = real_home / ".agents" / "tasks" / project
    binding_dir.mkdir(parents=True, exist_ok=True)
    path = binding_dir / "PROJECT_BINDING.toml"
    path.write_text(
        f'project = "{project}"\nfeishu_group_id = "{group_id}"\n'
        'bound_at = "2026-04-21T00:00:00Z"\n'
    )
    return path


def _write_workspace_contract(
    real_home: Path, project: str, seat: str, group_id: str
) -> Path:
    contract_dir = real_home / ".agents" / "workspaces" / project / seat
    contract_dir.mkdir(parents=True, exist_ok=True)
    path = contract_dir / "WORKSPACE_CONTRACT.toml"
    path.write_text(
        f'project = "{project}"\nseat_id = "{seat}"\n'
        f'feishu_group_id = "{group_id}"\n'
    )
    return path


# ── Strict resolver: project required ──────────────────────────────────


def test_strict_requires_non_empty_project(tmp_path, monkeypatch, clean_env):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    feishu = _reload_feishu()
    with pytest.raises(feishu.FeishuGroupResolutionError) as exc_info:
        feishu.resolve_feishu_group_strict("")
    assert "project is required" in str(exc_info.value)

    with pytest.raises(feishu.FeishuGroupResolutionError):
        feishu.resolve_feishu_group_strict(None)  # type: ignore[arg-type]


# ── Strict resolver: env override ──────────────────────────────────────


def test_strict_env_override_wins(tmp_path, monkeypatch, clean_env):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    _write_binding(tmp_path, "install", "oc_install_groupx1")
    monkeypatch.setenv("CLAWSEAT_FEISHU_GROUP_ID", "oc_env_overrides99")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        group_id, source = feishu.resolve_feishu_group_strict("install")
    assert group_id == "oc_env_overrides99"
    assert source.startswith("env:")


def test_strict_rejects_garbage_env_and_falls_through(tmp_path, monkeypatch, clean_env):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    _write_binding(tmp_path, "install", "oc_install_binding1")
    monkeypatch.setenv("CLAWSEAT_FEISHU_GROUP_ID", "not-a-group-id")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        group_id, source = feishu.resolve_feishu_group_strict("install")
    assert group_id == "oc_install_binding1"
    assert source.startswith("project_binding:")


# ── Strict resolver: PROJECT_BINDING.toml ──────────────────────────────


def test_strict_project_binding_matches(tmp_path, monkeypatch, clean_env):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    binding_path = _write_binding(tmp_path, "cartooner", "oc_cartooner_main")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        group_id, source = feishu.resolve_feishu_group_strict("cartooner")
    assert group_id == "oc_cartooner_main"
    assert source == f"project_binding:{binding_path}"


def test_strict_project_binding_mismatched_project_refuses(tmp_path, monkeypatch, clean_env):
    """A PROJECT_BINDING.toml whose declared project != caller's project is
    a misconfiguration. Strict resolver refuses rather than silently accepting."""
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    # Binding file at .../install/PROJECT_BINDING.toml but declares cartooner
    binding_dir = tmp_path / ".agents" / "tasks" / "install"
    binding_dir.mkdir(parents=True)
    (binding_dir / "PROJECT_BINDING.toml").write_text(
        'project = "cartooner"\nfeishu_group_id = "oc_cartooner_group1"\n'
    )
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        with pytest.raises(feishu.FeishuGroupResolutionError) as exc_info:
            feishu.resolve_feishu_group_strict("install")
    assert "declares project=" in str(exc_info.value)


# ── Strict resolver: WORKSPACE_CONTRACT fallback within project ────────


def test_strict_workspace_contract_fallback(tmp_path, monkeypatch, clean_env):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    _write_workspace_contract(tmp_path, "install", "koder", "oc_contract_only1")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        group_id, source = feishu.resolve_feishu_group_strict("install")
    assert group_id == "oc_contract_only1"
    assert source.startswith("workspace_contract:")


# ── Strict resolver: binding beats contract ────────────────────────────


def test_strict_binding_beats_workspace_contract(tmp_path, monkeypatch, clean_env):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    _write_workspace_contract(tmp_path, "install", "koder", "oc_contract_fallback1")
    _write_binding(tmp_path, "install", "oc_binding_wins999")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        group_id, source = feishu.resolve_feishu_group_strict("install")
    assert group_id == "oc_binding_wins999"
    assert source.startswith("project_binding:")


# ── The core C1 regression: no global fallback ─────────────────────────


def test_strict_refuses_to_fall_back_to_global_openclaw_json(
    tmp_path, monkeypatch, clean_env
):
    """If project has no binding, strict resolver MUST raise, even when
    openclaw.json has a group configured globally. This is the exact
    pre-C1 silent-guess path and it must stay dead."""
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    _write_openclaw_global(tmp_path, "oc_global_leak_trap1")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        with pytest.raises(feishu.FeishuGroupResolutionError) as exc_info:
            feishu.resolve_feishu_group_strict("install")
    # Error message surfaces the project name so operators see the mismatch.
    assert "install" in str(exc_info.value)
    # And definitely does NOT have resolved the trap group.
    assert "oc_global_leak_trap1" not in str(exc_info.value)


def test_bc_primary_returns_none_not_global_leak(
    tmp_path, monkeypatch, clean_env
):
    """The backwards-compatible wrapper still returns None for a missing
    project binding — critically NOT the first group from openclaw.json."""
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    _write_openclaw_global(tmp_path, "oc_global_leak_trap2")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        result = feishu.resolve_primary_feishu_group_id(project="install")
    assert result is None


# ── Multi-project isolation ────────────────────────────────────────────


def test_multi_project_isolation(tmp_path, monkeypatch, clean_env):
    """Install and cartooner must each resolve to their own group; a
    request for an unbound third project must fail, not return either."""
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    _write_binding(tmp_path, "install", "oc_install_group001")
    _write_binding(tmp_path, "cartooner", "oc_cartooner_group02")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        assert feishu.resolve_feishu_group_strict("install")[0] == "oc_install_group001"
        assert feishu.resolve_feishu_group_strict("cartooner")[0] == "oc_cartooner_group02"
        with pytest.raises(feishu.FeishuGroupResolutionError):
            feishu.resolve_feishu_group_strict("mystery-project")


# ── send_feishu_user_message surfaces the failure ──────────────────────


def test_send_user_message_without_group_fails_clean(
    tmp_path, monkeypatch, clean_env
):
    """When no group_id and no project binding exist, the helper must
    return status=failed with a clear 'no_project_binding' reason — not
    a silent 'skipped' that hides the misconfiguration."""
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    _write_openclaw_global(tmp_path, "oc_global_leak_trap3")
    feishu = _reload_feishu()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(tmp_path))
        result = feishu.send_feishu_user_message(
            "hello", project="install", pre_check_auth=False
        )
    assert result["status"] == "failed"
    assert result["reason"] == "no_project_binding"
    assert "group_id" not in result
    assert "fix" in result


def test_send_user_message_with_explicit_group_bypasses_resolution(
    tmp_path, monkeypatch, clean_env
):
    """If a caller passes group_id explicitly, strict resolution is skipped
    (the caller took responsibility). Report group_source accordingly."""
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    feishu = _reload_feishu()

    def fake_run(argv, cwd, env):
        return mock.Mock(returncode=0, stdout="ok", stderr="")

    with mock.patch.object(feishu, "run_command_with_env", side_effect=fake_run), \
         mock.patch.object(feishu.shutil, "which", return_value="/usr/bin/lark-cli"):
        result = feishu.send_feishu_user_message(
            "hello",
            group_id="oc_explicit_groupid9",
            project=None,
            pre_check_auth=False,
        )
    assert result["status"] == "sent"
    assert result["group_id"] == "oc_explicit_groupid9"
    assert result["group_source"] == "explicit:group_id"
