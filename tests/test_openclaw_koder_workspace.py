from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


_REPO = Path(__file__).resolve().parents[1]
_HARNESS_SCRIPTS = _REPO / "core" / "skills" / "gstack-harness" / "scripts"
_INSTALL_SCRIPTS = _REPO / "core" / "skills" / "clawseat-install" / "scripts"

for _path in (str(_HARNESS_SCRIPTS), str(_INSTALL_SCRIPTS), str(_REPO)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import init_koder
import migrate_profile
import render_console
import start_seat
from _common import load_profile
from core.scripts.agent_admin_store import StoreHandlers, StoreHooks


def _write_profile(tmp_path: Path) -> Path:
    profile_path = tmp_path / "install-profile.toml"
    tasks_root = tmp_path / "tasks" / "install"
    workspace_root = tmp_path / "workspaces" / "install"
    handoff_dir = tasks_root / "patrol" / "handoffs"
    profile_path.write_text(
        "\n".join(
            [
                'version = 1',
                'profile_name = "install-openclaw-test"',
                'template_name = "gstack-harness"',
                'project_name = "install"',
                f'repo_root = "{_REPO}"',
                f'tasks_root = "{tasks_root}"',
                f'project_doc = "{tasks_root / "PROJECT.md"}"',
                f'tasks_doc = "{tasks_root / "TASKS.md"}"',
                f'status_doc = "{tasks_root / "STATUS.md"}"',
                f'send_script = "{_REPO / "core" / "shell-scripts" / "send-and-verify.sh"}"',
                f'status_script = "{tasks_root / "patrol" / "check-status.sh"}"',
                f'patrol_script = "{tasks_root / "patrol" / "patrol-supervisor.sh"}"',
                f'agent_admin = "{_REPO / "core" / "scripts" / "agent_admin.py"}"',
                f'workspace_root = "{workspace_root}"',
                f'handoff_dir = "{handoff_dir}"',
                'heartbeat_owner = "koder"',
                'active_loop_owner = "planner"',
                'default_notify_target = "planner"',
                f'heartbeat_receipt = "{workspace_root / "koder" / "HEARTBEAT_RECEIPT.toml"}"',
                'seats = ["koder", "planner", "reviewer-1"]',
                'heartbeat_seats = ["koder"]',
                '',
                '[seat_roles]',
                'koder = "frontstage-supervisor"',
                'planner = "planner-dispatcher"',
                'reviewer-1 = "reviewer"',
                '',
                '[dynamic_roster]',
                'enabled = true',
                f'session_root = "{tmp_path / "sessions"}"',
                'bootstrap_seats = ["koder"]',
                'default_start_seats = ["koder", "planner"]',
                'compat_legacy_seats = false',
                '',
            ]
        ),
        encoding="utf-8",
    )
    return profile_path


def _store_handlers(tmp_path: Path) -> StoreHandlers:
    return StoreHandlers(
        StoreHooks(
            error_cls=RuntimeError,
            project_cls=SimpleNamespace,
            engineer_cls=SimpleNamespace,
            session_record_cls=SimpleNamespace,
            projects_root=tmp_path / "projects",
            engineers_root=tmp_path / "engineers",
            sessions_root=tmp_path / "sessions",
            workspaces_root=tmp_path / "workspaces",
            current_project_path=tmp_path / "state" / "current_project",
            templates_root=tmp_path / "templates",
            tool_binaries={},
            default_tool_args={},
            normalize_name=lambda value: value,
            ensure_dir=lambda path: path.mkdir(parents=True, exist_ok=True),
            write_text=lambda *args, **kwargs: None,
            load_toml=lambda path: {},
            q=lambda value: repr(value),
            q_array=lambda values: repr(values),
            identity_name=lambda *args, **kwargs: "identity",
            runtime_dir_for_identity=lambda *args, **kwargs: tmp_path / "runtime",
            secret_file_for=lambda *args, **kwargs: tmp_path / "secret.env",
            session_name_for=lambda *args, **kwargs: "session-name",
        )
    )


def test_init_koder_builds_workspace_from_profile_backend_seats(tmp_path):
    profile_path = _write_profile(tmp_path)
    profile = load_profile(profile_path)

    files = init_koder.build_workspace_files(
        project="install",
        profile_path=profile_path,
        profile=profile,
        feishu_group_id="",
    )

    tools_index = files["TOOLS.md"]
    tools_seat = files["TOOLS/seat.md"]
    agents = files["AGENTS.md"]
    memory = files["MEMORY.md"]
    contract = files["WORKSPACE_CONTRACT.toml"]

    # TOOLS.md is now a slim index — the 禁止 rule is in the hard-rules section.
    assert "禁止运行 `start_seat.py --seat koder`" in tools_index
    assert "`TOOLS/seat.md`" in tools_index  # routes to the seat sub-file

    # The seat command details live in TOOLS/seat.md.
    assert "--seat <planner|reviewer-1>" in tools_seat
    # backend seat list inside seat.md only names the starting-capable seats.
    assert "`planner`, `reviewer-1`" in tools_seat
    assert "`builder-1`" not in tools_seat
    assert "`qa-1`" not in tools_seat

    assert "Only backend seats may be started from this workspace: `planner`, `reviewer-1`" in agents
    # OpenClaw-mode caveat now points at TOOLS.md 强制规则; the literal
    # "never run ..." phrase was deduplicated out of AGENTS.md.
    assert "`koder`" in agents
    assert "强制规则" in agents

    # MEMORY.md no longer embeds the seat roster; it points at the contract.
    assert "`WORKSPACE_CONTRACT.toml`" in memory
    assert "- `builder-1`" not in memory
    # The stale hardcoded status lines are gone.
    assert "bootstrap: pending" not in memory

    assert 'seats = ["koder", "planner", "reviewer-1"]' in contract
    assert 'backend_seats = ["planner", "reviewer-1"]' in contract
    # D1: contract fingerprint lands in every contract now.
    assert 'contract_fingerprint = "' in contract
    assert 'default_backend_start_seats = ["planner"]' in contract
    assert profile.materialized_seats == ["koder", "planner", "reviewer-1"]
    assert profile.bootstrap_seats == ["koder"]


def test_make_local_override_separates_materialized_and_bootstrap_seats(tmp_path):
    profile_path = _write_profile(tmp_path)
    profile = load_profile(profile_path)

    local_override = init_koder.REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "_common.py"
    assert local_override.exists()

    from _common import make_local_override

    local_path = make_local_override(profile, project_name="install", repo_root=_REPO)
    try:
        payload = local_path.read_text(encoding="utf-8")
    finally:
        local_path.unlink(missing_ok=True)

    assert 'seat_order = ["koder", "planner", "reviewer-1"]' in payload
    assert 'materialized_seats = ["koder", "planner", "reviewer-1"]' in payload
    assert 'bootstrap_seats = ["koder"]' in payload
    assert 'default_start_seats = ["koder", "planner"]' in payload


def test_load_profile_defaults_materialized_seats_to_declared_roster(tmp_path):
    profile_path = tmp_path / "starter-profile.toml"
    profile_path.write_text(
        "\n".join(
            [
                'version = 1',
                'profile_name = "starter-openclaw-test"',
                'template_name = "gstack-harness"',
                'project_name = "starter"',
                f'repo_root = "{_REPO}"',
                f'tasks_root = "{tmp_path / "tasks" / "starter"}"',
                f'project_doc = "{tmp_path / "tasks" / "starter" / "PROJECT.md"}"',
                f'tasks_doc = "{tmp_path / "tasks" / "starter" / "TASKS.md"}"',
                f'status_doc = "{tmp_path / "tasks" / "starter" / "STATUS.md"}"',
                f'send_script = "{_REPO / "core" / "shell-scripts" / "send-and-verify.sh"}"',
                f'status_script = "{tmp_path / "tasks" / "starter" / "patrol" / "check-status.sh"}"',
                f'patrol_script = "{tmp_path / "tasks" / "starter" / "patrol" / "patrol-supervisor.sh"}"',
                f'agent_admin = "{_REPO / "core" / "scripts" / "agent_admin.py"}"',
                f'workspace_root = "{tmp_path / "workspaces" / "starter"}"',
                f'handoff_dir = "{tmp_path / "tasks" / "starter" / "patrol" / "handoffs"}"',
                'heartbeat_owner = "koder"',
                'active_loop_owner = "planner"',
                'default_notify_target = "planner"',
                f'heartbeat_receipt = "{tmp_path / "workspaces" / "starter" / "koder" / "HEARTBEAT_RECEIPT.toml"}"',
                'seats = ["koder", "planner"]',
                'heartbeat_seats = ["koder"]',
                '',
                '[seat_roles]',
                'koder = "frontstage-supervisor"',
                'planner = "planner-dispatcher"',
                '',
                '[dynamic_roster]',
                'enabled = true',
                f'session_root = "{tmp_path / "sessions"}"',
                'bootstrap_seats = ["koder"]',
                'default_start_seats = ["koder", "planner"]',
                'compat_legacy_seats = false',
                '',
            ]
        ),
        encoding="utf-8",
    )

    profile = load_profile(profile_path)

    assert profile.materialized_seats == ["koder", "planner"]
    assert profile.bootstrap_seats == ["koder"]
    assert profile.default_start_seats == ["koder", "planner"]


def test_migrate_profile_emits_materialized_seats(tmp_path):
    source = {
        "profile_name": "legacy",
        "description": "legacy profile",
        "send_script": "/tmp/send.sh",
        "agent_admin": "/tmp/agent_admin.py",
        "heartbeat_owner": "koder",
        "active_loop_owner": "planner",
        "default_notify_target": "planner",
        "seats": ["koder", "planner", "builder-1"],
        "seat_roles": {
            "koder": "frontstage-supervisor",
            "planner": "planner-dispatcher",
            "builder-1": "builder",
        },
    }

    lines = migrate_profile.build_lines(
        source,
        project_name="install",
        repo_root=str(_REPO),
        bootstrap_only=False,
    )
    text = "\n".join(lines)

    assert 'materialized_seats = ["koder"]' in text
    assert 'bootstrap_seats = ["koder"]' in text
    assert 'default_start_seats = ["koder"]' in text


def test_render_console_seat_sets_exposes_runtime_collections():
    profile = SimpleNamespace(
        seats=["koder", "planner", "reviewer-1"],
        materialized_seats=["koder", "planner", "reviewer-1"],
        bootstrap_seats=["koder"],
        default_start_seats=["koder", "planner"],
        heartbeat_owner="koder",
    )

    sets = render_console.seat_sets(profile)

    assert sets == {
        "roster": ["koder", "planner", "reviewer-1"],
        "materialized": ["koder", "planner", "reviewer-1"],
        "bootstrap": ["koder"],
        "default_start": ["koder", "planner"],
        "backend": ["planner", "reviewer-1"],
    }


def test_merge_template_local_materializes_declared_roster_without_bootstrap_filter(tmp_path):
    handlers = _store_handlers(tmp_path)
    template = {
        "defaults": {},
        "engineers": [
            {"id": "koder", "tool": "claude", "auth_mode": "oauth", "provider": "anthropic"},
            {"id": "planner", "tool": "claude", "auth_mode": "oauth", "provider": "anthropic"},
            {"id": "reviewer-1", "tool": "codex", "auth_mode": "api", "provider": "xcode-best"},
        ],
    }
    local = {
        "project_name": "install",
        "repo_root": str(_REPO),
        "seat_order": ["koder", "planner", "reviewer-1"],
        "materialized_seats": ["koder", "planner", "reviewer-1"],
        "bootstrap_seats": ["koder"],
    }

    merged = handlers.merge_template_local(template, local)

    assert [engineer["id"] for engineer in merged["engineers"]] == ["koder", "planner", "reviewer-1"]


def test_merge_template_local_allows_full_seat_order_with_subset_materialization(tmp_path):
    handlers = _store_handlers(tmp_path)
    template = {
        "defaults": {},
        "engineers": [
            {"id": "koder", "tool": "claude", "auth_mode": "oauth", "provider": "anthropic"},
            {"id": "planner", "tool": "claude", "auth_mode": "oauth", "provider": "anthropic"},
            {"id": "reviewer-1", "tool": "codex", "auth_mode": "api", "provider": "xcode-best"},
        ],
    }
    local = {
        "project_name": "install",
        "repo_root": str(_REPO),
        "seat_order": ["koder", "planner", "reviewer-1"],
        "materialized_seats": ["koder", "planner"],
        "bootstrap_seats": ["koder"],
    }

    merged = handlers.merge_template_local(template, local)

    assert [engineer["id"] for engineer in merged["engineers"]] == ["koder", "planner"]


def test_find_openclaw_frontstage_contract_only_matches_openclaw_workspace(tmp_path, monkeypatch):
    openclaw_home = tmp_path / ".openclaw"
    workspace = openclaw_home / "workspace-koder"
    workspace.mkdir(parents=True, exist_ok=True)
    contract = workspace / "WORKSPACE_CONTRACT.toml"
    contract.write_text(
        "\n".join(
            [
                'version = 1',
                'seat_id = "koder"',
                'project = "install"',
                '',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(start_seat, "OPENCLAW_HOME", openclaw_home)
    profile = SimpleNamespace(project_name="install", heartbeat_owner="koder")

    detected = start_seat.find_openclaw_frontstage_contract(profile, "koder", cwd=workspace)

    assert detected == contract.resolve()

    local_workspace = tmp_path / ".agents" / "workspaces" / "install" / "koder"
    local_workspace.mkdir(parents=True, exist_ok=True)
    (local_workspace / "WORKSPACE_CONTRACT.toml").write_text(contract.read_text(encoding="utf-8"), encoding="utf-8")

    not_detected = start_seat.find_openclaw_frontstage_contract(profile, "koder", cwd=local_workspace)

    assert not_detected is None


def test_start_seat_main_blocks_openclaw_frontstage_self_start(monkeypatch, capsys):
    args = SimpleNamespace(
        profile="/tmp/install-profile.toml",
        seat="koder",
        reset=False,
        confirm_start=False,
        tool=None,
        auth_mode=None,
        provider=None,
    )
    profile = SimpleNamespace(
        project_name="install",
        heartbeat_owner="koder",
        default_start_seats=["koder", "planner"],
        heartbeat_seats=["koder"],
        seat_roles={"koder": "frontstage-supervisor"},
    )

    monkeypatch.setattr(start_seat, "parse_args", lambda: args)
    monkeypatch.setattr(start_seat, "load_profile", lambda path: profile)
    monkeypatch.setattr(start_seat, "materialize_profile_runtime", lambda loaded_profile: None)
    monkeypatch.setattr(
        start_seat,
        "find_openclaw_frontstage_contract",
        lambda loaded_profile, seat, cwd=None: Path("/tmp/.openclaw/workspace-koder/WORKSPACE_CONTRACT.toml"),
    )

    rc = start_seat.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "openclaw_frontstage_self_start_blocked" in out
    assert "start a backend seat instead" in out
    assert "'planner'" in out
