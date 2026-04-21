"""C2 tests: PROJECT_BINDING.toml as the per-project SSOT."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest import mock

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "core" / "lib"))
sys.path.insert(0, str(_REPO / "core" / "skills" / "gstack-harness" / "scripts"))


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    for key in ("CLAWSEAT_FEISHU_GROUP_ID", "OPENCLAW_FEISHU_GROUP_ID"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    # Re-import so module-level path resolution picks up the override.
    for name in ("project_binding", "real_home", "_feishu", "_utils"):
        sys.modules.pop(name, None)
    yield tmp_path


def _load_pb():
    import project_binding
    importlib.reload(project_binding)
    return project_binding


def _load_feishu():
    import _feishu
    importlib.reload(_feishu)
    return _feishu


# ── Schema / validation ────────────────────────────────────────────────


def test_validate_feishu_group_id_accepts_canonical():
    pb = _load_pb()
    assert pb.validate_feishu_group_id("oc_b0386423ec11582696a3079ab2ab89ba") == \
        "oc_b0386423ec11582696a3079ab2ab89ba"


def test_validate_feishu_group_id_rejects_garbage():
    pb = _load_pb()
    # Each value is already-trimmed; validator strips and then shape-matches.
    for bad in ("", "test-group", "group-123", "oc_", "oc bad", "OC_FOO"):
        with pytest.raises(pb.ProjectBindingError):
            pb.validate_feishu_group_id(bad)


def test_validate_project_name_rejects_bad():
    pb = _load_pb()
    for bad in ("", "  ", "..", "/abs", "proj/subproject", "-leading-dash"):
        with pytest.raises(pb.ProjectBindingError):
            pb.validate_project_name(bad)


# ── Write / read round-trip ────────────────────────────────────────────


def test_bind_and_load_round_trip(_isolated_home, monkeypatch):
    pb = _load_pb()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(_isolated_home))
        path = pb.bind_project(
            project="install",
            feishu_group_id="oc_installgroup0001",
            feishu_bot_account="koder",
            require_mention=False,
            bound_by="ywf",
        )
        assert path.exists()
        assert path.name == "PROJECT_BINDING.toml"
        assert path.parent == _isolated_home / ".agents" / "tasks" / "install"

        binding = pb.load_binding("install")
    assert binding is not None
    assert binding.project == "install"
    assert binding.feishu_group_id == "oc_installgroup0001"
    assert binding.feishu_bot_account == "koder"
    assert binding.require_mention is False
    assert binding.bound_by == "ywf"
    assert binding.bound_at  # auto-filled timestamp


def test_load_returns_none_for_missing(_isolated_home):
    pb = _load_pb()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(_isolated_home))
        assert pb.load_binding("nope") is None


def test_load_refuses_cross_project_binding(_isolated_home):
    """A PROJECT_BINDING.toml whose declared `project` disagrees with the
    directory it lives in is a misconfiguration — must raise, not silently
    succeed with the wrong answer."""
    pb = _load_pb()
    target = _isolated_home / ".agents" / "tasks" / "install" / "PROJECT_BINDING.toml"
    target.parent.mkdir(parents=True)
    target.write_text(
        'project = "cartooner"\n'
        'feishu_group_id = "oc_cartoonergrp999"\n'
    )
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(_isolated_home))
        with pytest.raises(pb.ProjectBindingError) as exc_info:
            pb.load_binding("install")
    assert "install" in str(exc_info.value)
    assert "cartooner" in str(exc_info.value)


def test_rewrite_preserves_extra_keys(_isolated_home):
    """Future schema fields must not be dropped on rewrite."""
    pb = _load_pb()
    target = _isolated_home / ".agents" / "tasks" / "install" / "PROJECT_BINDING.toml"
    target.parent.mkdir(parents=True)
    target.write_text(
        'project = "install"\n'
        'feishu_group_id = "oc_installoriginal"\n'
        'custom_label = "smoke-run"\n'
        'custom_counter = 42\n'
    )
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(_isolated_home))
        binding = pb.load_binding("install")
        assert binding is not None
        assert binding.extras == {"custom_label": "smoke-run", "custom_counter": 42}
        pb.write_binding(binding)
        re_read = pb.load_binding("install")
    assert re_read is not None
    assert re_read.extras == {"custom_label": "smoke-run", "custom_counter": 42}


def test_list_bindings_enumerates_directories(_isolated_home):
    pb = _load_pb()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(_isolated_home))
        pb.bind_project(project="install", feishu_group_id="oc_installproj1234")
        pb.bind_project(project="cartooner", feishu_group_id="oc_cartoonerpj987")
        # Garbage directory that is NOT a binding — must be ignored silently.
        (_isolated_home / ".agents" / "tasks" / "not-a-project").mkdir()
        bindings = pb.list_bindings()
    assert {b.project for b in bindings} == {"install", "cartooner"}


# ── Integration with _feishu.resolve_feishu_group_strict ──────────────


def test_feishu_strict_reads_project_binding(_isolated_home):
    """End-to-end: writing a binding via the library makes the strict
    resolver pick it up as source=project_binding."""
    pb = _load_pb()
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(_isolated_home))
        pb.bind_project(
            project="install", feishu_group_id="oc_installbindingr1",
        )
        feishu = _load_feishu()
        group_id, source = feishu.resolve_feishu_group_strict("install")
    assert group_id == "oc_installbindingr1"
    assert source.startswith("project_binding:")


def test_feishu_strict_without_binding_still_errors(_isolated_home):
    """A newly-created project with no binding and no contract must still
    fail — binding is the preferred source but not the only source."""
    _load_pb()  # ensure path is populated
    with mock.patch("pwd.getpwuid") as m_pwd:
        m_pwd.return_value = mock.Mock(pw_dir=str(_isolated_home))
        feishu = _load_feishu()
        with pytest.raises(feishu.FeishuGroupResolutionError):
            feishu.resolve_feishu_group_strict("no-such-project")
