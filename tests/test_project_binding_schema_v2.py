from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "core" / "lib"))
sys.path.insert(0, str(_REPO / "core" / "scripts"))


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAWSEAT_REAL_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in list(sys.modules):
        if name == "project_binding" or name == "real_home" or name.startswith("agent_admin"):
            sys.modules.pop(name, None)
    yield tmp_path


def _load_pb():
    import project_binding

    importlib.reload(project_binding)
    return project_binding


def _load_agent_admin():
    import agent_admin

    importlib.reload(agent_admin)
    return agent_admin


def test_v2_write_emits_new_fields_and_omits_legacy_alias():
    pb = _load_pb()
    binding = pb.ProjectBinding(
        project="install",
        feishu_group_id="oc_installgroup0001",
        feishu_sender_app_id="cli_a96abcca2e78dbc2",
        feishu_sender_mode="bot",
        openclaw_koder_agent="yu",
        require_mention=True,
        bound_by="ancestor",
    )

    text = binding.as_toml()

    assert "version = 2" in text
    assert 'feishu_sender_app_id = "cli_a96abcca2e78dbc2"' in text
    assert 'feishu_sender_mode = "bot"' in text
    assert 'openclaw_koder_agent = "yu"' in text
    assert "feishu_bot_account" not in text
    assert binding.feishu_bot_account == "cli_a96abcca2e78dbc2"


def test_legacy_bot_account_cli_maps_to_sender_app_id():
    pb = _load_pb()
    target = Path(pb.bindings_root()) / "install" / "PROJECT_BINDING.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        'version = 1\n'
        'project = "install"\n'
        'feishu_group_id = "oc_installgroup0001"\n'
        'feishu_bot_account = "cli_a96abcca2e78dbc2"\n'
        'bound_at = "2026-04-22T00:00:00+00:00"\n',
        encoding="utf-8",
    )

    binding = pb.load_binding("install")

    assert binding is not None
    assert binding.version == 2
    assert binding.feishu_sender_app_id == "cli_a96abcca2e78dbc2"
    assert binding.openclaw_koder_agent == ""
    assert binding.feishu_bot_account == "cli_a96abcca2e78dbc2"


def test_legacy_bot_account_non_cli_maps_to_openclaw_koder_agent():
    pb = _load_pb()
    target = Path(pb.bindings_root()) / "install" / "PROJECT_BINDING.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        'version = 1\n'
        'project = "install"\n'
        'feishu_group_id = "oc_installgroup0002"\n'
        'feishu_bot_account = "yu"\n'
        'bound_at = "2026-04-22T00:00:00+00:00"\n',
        encoding="utf-8",
    )

    binding = pb.load_binding("install")

    assert binding is not None
    assert binding.version == 2
    assert binding.feishu_sender_app_id == ""
    assert binding.openclaw_koder_agent == "yu"
    assert binding.feishu_bot_account == "yu"


def test_parser_and_deprecated_cli_alias_route_to_v2_fields(capsys):
    agent_admin = _load_agent_admin()
    parser = agent_admin.build_parser()

    parsed = parser.parse_args([
        "project",
        "bind",
        "--project",
        "install",
        "--feishu-group",
        "oc_installgroup0003",
        "--feishu-sender-app-id",
        "cli_a96abcca2e78dbc2",
        "--feishu-sender-mode",
        "user",
        "--openclaw-koder-agent",
        "yu",
    ])

    assert parsed.feishu_sender_app_id == "cli_a96abcca2e78dbc2"
    assert parsed.feishu_sender_mode == "user"
    assert parsed.openclaw_koder_agent == "yu"
    assert parsed.feishu_bot_account is None

    legacy = parser.parse_args([
        "project",
        "bind",
        "--project",
        "install",
        "--feishu-group",
        "oc_installgroup0004",
        "--feishu-bot-account",
        "cli_a96abcca2e78dbc2",
    ])

    assert legacy.feishu_bot_account == "cli_a96abcca2e78dbc2"

    with mock.patch("project_binding.fetch_chat_metadata", return_value=("Install Squad", False)):
        rc = agent_admin.cmd_project_bind(
            SimpleNamespace(
                project="install",
                feishu_group="oc_installgroup0004",
                feishu_sender_app_id="",
                feishu_sender_mode="auto",
                openclaw_koder_agent="",
                feishu_bot_account="cli_a96abcca2e78dbc2",
                require_mention=True,
                bound_by="ancestor",
            )
        )

    captured = capsys.readouterr()
    assert rc == 0
    assert "warning: --feishu-bot-account is deprecated" in captured.err

    binding = _load_pb().load_binding("install")
    assert binding is not None
    assert binding.feishu_sender_app_id == "cli_a96abcca2e78dbc2"
    assert binding.openclaw_koder_agent == ""
    assert binding.feishu_sender_mode == "auto"
    assert binding.feishu_group_id == "oc_installgroup0004"
