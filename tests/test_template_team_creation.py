from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import agent_admin as aa  # noqa: E402
from agent_admin_commands import CommandHandlers  # noqa: E402


_TEMPLATE = _REPO / "templates" / "team-creation.toml"
_INSTALL = _REPO / "scripts" / "install.sh"
_EXPECTED_SEATS = [
    "memory",
    "builder-image",
    "builder-image-2",
    "builder-av",
    "patrol",
]


@pytest.fixture(autouse=True)
def _caller_dispatch_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile = tmp_path / "caller.toml"
    profile.write_text(
        "\n".join(
            [
                "version = 1",
                'id = "planner"',
                'display_name = "planner"',
                'role = "planner"',
                "dispatch_authority = true",
                "escalation_authority = false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAWSEAT_ENGINEER_PROFILE", str(profile))
    monkeypatch.setenv("CLAWSEAT_ENGINEER_ID", "planner")
    monkeypatch.setenv("CLAWSEAT_SEAT", "planner")


def _load_template() -> dict:
    with _TEMPLATE.open("rb") as handle:
        return tomllib.load(handle)


def _team_creation_project(name: str = "team-demo") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        repo_root=str(_REPO),
        monitor_session=f"{name}-memory",
        engineers=list(_EXPECTED_SEATS),
        monitor_engineers=list(_EXPECTED_SEATS),
        template_name="team-creation",
        declared_skills=["TOOLS/memory.md"],
        seat_overrides={},
        window_mode="split-2",
        monitor_max_panes=5,
        open_detail_windows=False,
        profile_path=str(_REPO / "profiles" / f"{name}.toml"),
    )


def _isolate_store_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aa.STORE_HANDLERS.hooks, "engineers_root", tmp_path / "engineers")
    monkeypatch.setattr(aa.STORE_HANDLERS.hooks, "sessions_root", tmp_path / "sessions")
    monkeypatch.setattr(aa.STORE_HANDLERS.hooks, "workspaces_root", tmp_path / "workspaces")
    monkeypatch.setattr(
        aa.STORE_HANDLERS.hooks,
        "runtime_dir_for_identity",
        lambda tool, auth_mode, identity: tmp_path / "runtime" / identity,
    )
    monkeypatch.setattr(
        aa.STORE_HANDLERS.hooks,
        "secret_file_for",
        lambda tool, provider, engineer_id: tmp_path / "secrets" / tool / provider / f"{engineer_id}.env",
    )
    monkeypatch.setattr(
        aa.STORE_HANDLERS.hooks,
        "identity_name",
        lambda tool, auth_mode, provider, engineer_id, project: f"{tool}.{auth_mode}.{provider}.{project}.{engineer_id}",
    )
    monkeypatch.setattr(
        aa.STORE_HANDLERS.hooks,
        "session_name_for",
        lambda project, engineer_id, tool: f"{project}-{engineer_id}-{tool}",
    )


def _team_creation_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    project_name: str = "team-demo",
) -> tuple[SimpleNamespace, dict[str, aa.Engineer], list[str], list[dict[str, object]]]:
    _isolate_store_paths(tmp_path, monkeypatch)
    project = _team_creation_project(project_name)
    context = aa.project_template_context(project)
    assert context is not None
    profiles, engineer_order, optional_skills = context
    return project, profiles, engineer_order, optional_skills


def _render_agents_md(
    seat_id: str,
    project: SimpleNamespace,
    profiles: dict[str, aa.Engineer],
    engineer_order: list[str],
) -> str:
    engineer = profiles[seat_id]
    session = aa.create_session_record(
        seat_id,
        project,
        engineer.default_tool,
        engineer.default_auth_mode,
        engineer.default_provider,
        monitor=True,
    )
    rendered = aa.render_template_text(
        session.tool,
        session,
        project,
        engineer_override=engineer,
        project_engineers=profiles,
        engineer_order=engineer_order,
    )
    return rendered["AGENTS.md"]


def test_team_creation_template_schema_has_five_seats() -> None:
    data = _load_template()

    assert data["version"] == 1
    assert data["template_name"] == "team-creation"
    assert data["defaults"]["window_mode"] == "split-2"
    assert data["defaults"]["monitor_max_panes"] == 5
    assert data["defaults"]["workspace_tools"] == ["TOOLS/memory.md"]
    assert data["window_layout"]["workers_grid"]["left_main_seat"] == "builder-image"
    assert data["window_layout"]["workers_grid"]["right_seats"] == ["builder-image-2", "builder-av", "patrol"]
    assert [engineer["id"] for engineer in data["engineers"]] == _EXPECTED_SEATS
    assert data["engineers"][0]["role"] == "project-memory"
    assert data["engineers"][1]["tool"] == "codex"
    assert data["engineers"][3]["provider"] == "minimax"
    assert data["engineers"][4]["patrol_authority"] is True


def test_team_creation_project_template_context_loads_five_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, profiles, engineer_order, optional_skills = _team_creation_context(tmp_path, monkeypatch)

    assert list(profiles) == _EXPECTED_SEATS
    assert engineer_order == _EXPECTED_SEATS
    assert isinstance(optional_skills, list)
    assert profiles["memory"].role == "project-memory"
    assert profiles["builder-image"].default_tool == "codex"
    assert profiles["builder-av"].default_auth_mode == "api"
    assert profiles["builder-av"].default_provider == "minimax"
    assert profiles["patrol"].patrol_authority is True
    assert project.template_name == "team-creation"


@pytest.mark.parametrize(
    ("seat_id", "expected_role_fragment", "expected_skill_path", "expected_marker"),
    [
        pytest.param("memory", "project-memory", "core/skills/memory-oracle/SKILL.md", "orphan knowledge holder", id="memory"),
        pytest.param("builder-image", "Role: `builder-image`", "core/skills/builder/SKILL.md", "planner-assigned workflow steps", id="builder-image"),
        pytest.param("builder-image-2", "Role: `builder-image-2`", "core/skills/builder/SKILL.md", "planner-assigned workflow steps", id="builder-image-2"),
        pytest.param("builder-av", "Role: `builder-av`", "core/skills/builder/SKILL.md", "planner-assigned workflow steps", id="builder-av"),
        pytest.param("patrol", "Role: `patrol`", "core/skills/patrol/SKILL.md", "Cron-driven patrol seat", id="patrol"),
    ],
)
def test_team_creation_rendered_workspace_embeds_role_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seat_id: str,
    expected_role_fragment: str,
    expected_skill_path: str,
    expected_marker: str,
) -> None:
    project, profiles, engineer_order, _optional_skills = _team_creation_context(tmp_path, monkeypatch)

    agents_md = _render_agents_md(seat_id, project, profiles, engineer_order)
    assert expected_role_fragment in agents_md
    assert "## Role SKILL (canonical)" in agents_md
    assert expected_skill_path in agents_md
    assert expected_marker in agents_md


def test_team_creation_install_sh_dry_run_accepts_template(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = subprocess.run(
        [
            "bash",
            str(_INSTALL),
            "--project",
            "team-creation-smoke",
            "--template",
            "team-creation",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "CLAWSEAT_REAL_HOME": str(home),
            "PYTHON_BIN": sys.executable,
        },
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "CLAWSEAT_TEMPLATE_NAME=team-creation" in combined
    assert "team-creation" in combined
    assert "INVALID_TEMPLATE" not in combined


def test_team_creation_batch_start_engineer_accepts_all_five_seats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, profiles, _engineer_order, _optional_skills = _team_creation_context(tmp_path, monkeypatch)
    monkeypatch.setattr(CommandHandlers, "_require_dispatch_authority", lambda self, action: None)

    started: list[tuple[str, bool]] = []
    lock = threading.Lock()

    class _FakeSessionService:
        def start_engineer(self, session, reset: bool = False) -> None:  # noqa: ARG002
            with lock:
                started.append((session.engineer_id, reset))

    hooks = MagicMock()
    hooks.error_cls = RuntimeError
    hooks.load_project_or_current.return_value = project
    hooks.resolve_engineer_session.side_effect = (
        lambda engineer_id, project_name=None: aa.create_session_record(
            engineer_id,
            project,
            profiles[engineer_id].default_tool,
            profiles[engineer_id].default_auth_mode,
            profiles[engineer_id].default_provider,
            monitor=True,
        )
    )
    hooks.provision_session_heartbeat.return_value = (True, "")
    hooks.session_service = _FakeSessionService()
    hooks.load_project_sessions.return_value = {}
    hooks.tmux_has_session.return_value = False
    hooks.load_projects.return_value = {}
    hooks.get_current_project_name.return_value = None
    hooks.load_engineers.return_value = profiles
    hooks.open_monitor_window.side_effect = AssertionError("unexpected monitor open")
    hooks.open_dashboard_window.side_effect = AssertionError("unexpected dashboard open")
    hooks.open_project_tabs_window.side_effect = AssertionError("unexpected project tabs open")
    hooks.open_engineer_window.side_effect = AssertionError("unexpected engineer window open")

    handlers = CommandHandlers(hooks)
    rc = handlers.session_batch_start_engineer(
        SimpleNamespace(
            project=project.name,
            engineers=list(_EXPECTED_SEATS),
            reset=False,
            no_iterm=True,
            accept_override=False,
        )
    )

    assert rc == 0
    assert sorted(engineer_id for engineer_id, _ in started) == sorted(_EXPECTED_SEATS)
    assert all(reset is False for _engineer_id, reset in started)
    assert len(started) == len(_EXPECTED_SEATS)


def test_patrol_skill_requires_memory_notifications_and_no_direct_builder_pokes() -> None:
    text = (_REPO / "core" / "skills" / "patrol" / "SKILL.md").read_text(encoding="utf-8")
    assert "review" in text.lower()
    assert "通知 memory" in text
    assert "禁直戳 builder" in text


def test_builder_skill_says_prompt_engineering_is_self_owned() -> None:
    text = (_REPO / "core" / "skills" / "builder" / "SKILL.md").read_text(encoding="utf-8")
    assert "prompt engineering 自负责" in text
