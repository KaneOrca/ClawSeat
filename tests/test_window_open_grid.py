from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "core" / "scripts"))

import agent_admin  # noqa: E402
import agent_admin_window  # noqa: E402
from agent_admin_commands import CommandHandlers, CommandHooks  # noqa: E402


def _project(engineers: list[str], *, name: str = "spawn49") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        engineers=engineers,
        monitor_session=f"project-{name}-monitor",
        repo_root=str(_REPO),
    )


def _handlers(projects: dict[str, SimpleNamespace]) -> CommandHandlers:
    return CommandHandlers(
        CommandHooks(
            error_cls=RuntimeError,
            load_project_or_current=lambda _name: next(iter(projects.values())) if projects else None,
            resolve_engineer_session=lambda *a, **k: None,
            provision_session_heartbeat=lambda *a, **k: (True, ""),
            load_project_sessions=lambda _project: {},
            tmux_has_session=lambda _name: False,
            load_projects=lambda: projects,
            get_current_project_name=lambda _projects: None,
            session_service=SimpleNamespace(),
            open_monitor_window=lambda *a, **k: None,
            open_dashboard_window=lambda *a, **k: None,
            open_project_tabs_window=lambda *a, **k: None,
            open_engineer_window=lambda *a, **k: None,
            load_engineers=lambda: {},
        )
    )


def test_parser_registers_open_grid_flags() -> None:
    parser = agent_admin.build_parser()
    args = parser.parse_args(["window", "open-grid", "spawn49", "--recover", "--open-memory"])

    assert args.command == "window"
    assert args.window_command == "open-grid"
    assert args.project == "spawn49"
    assert args.recover is True
    assert args.open_memory is True


def test_build_grid_payload_uses_project_roster_and_wait_for_seat_commands() -> None:
    project = _project(
        [
            "ancestor",
            "planner",
            "koder",
            "builder",
            "reviewer",
            "qa",
            "designer",
        ]
    )

    payload = agent_admin_window.build_grid_payload(project)

    assert payload["title"] == "clawseat-spawn49"
    commands = {pane["label"]: pane["command"] for pane in payload["panes"]}
    assert commands["ancestor"] == "tmux attach -t '=spawn49-ancestor'"
    assert "koder" not in commands
    for seat in ("planner", "builder", "reviewer", "qa", "designer"):
        assert commands[seat] == f"bash {_REPO / 'scripts' / 'wait-for-seat.sh'} spawn49-{seat}"


def test_open_grid_recover_skips_driver_when_window_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(["ancestor", "planner"])
    focus_calls: list[str] = []
    driver_calls: list[dict] = []

    monkeypatch.setattr(agent_admin_window, "iterm_window_exists", lambda title: title == "clawseat-spawn49")
    monkeypatch.setattr(agent_admin_window, "focus_iterm_window", lambda title: focus_calls.append(title))
    monkeypatch.setattr(
        agent_admin_window,
        "run_iterm_panes_driver",
        lambda payload: driver_calls.append(payload) or {"status": "ok", "window_id": "grid"},
    )

    result = agent_admin_window.open_grid_window(project, recover=True)

    assert result["recovered"] is True
    assert focus_calls == ["clawseat-spawn49"]
    assert driver_calls == []


def test_open_grid_open_memory_emits_second_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(["ancestor", "planner", "builder"])
    payloads: list[dict] = []

    monkeypatch.setattr(agent_admin_window, "iterm_window_exists", lambda title: False)
    monkeypatch.setattr(agent_admin_window, "tmux_has_session", lambda session: session == "machine-memory-claude")
    monkeypatch.setattr(
        agent_admin_window,
        "run_iterm_panes_driver",
        lambda payload: payloads.append(payload) or {"status": "ok", "window_id": payload["title"]},
    )

    result = agent_admin_window.open_grid_window(project, open_memory=True)

    assert [payload["title"] for payload in payloads] == ["clawseat-spawn49", "machine-memory-claude"]
    assert payloads[0]["panes"][0]["command"] == "tmux attach -t '=spawn49-ancestor'"
    assert payloads[1]["panes"][0]["command"] == "tmux attach -t '=machine-memory-claude'"
    assert result["memory"]["status"] == "ok"


def test_open_grid_rejects_unregistered_project() -> None:
    handlers = _handlers({})

    with pytest.raises(RuntimeError, match="project not registered"):
        handlers.window_open_grid(
            SimpleNamespace(project="ghost", recover=False, open_memory=False)
        )


def test_open_grid_empty_roster_warns_and_uses_ancestor_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _project([])
    payloads: list[dict] = []

    monkeypatch.setattr(agent_admin_window, "iterm_window_exists", lambda title: False)
    monkeypatch.setattr(agent_admin_window, "tmux_has_session", lambda session: False)
    monkeypatch.setattr(
        agent_admin_window,
        "run_iterm_panes_driver",
        lambda payload: payloads.append(payload) or {"status": "ok", "window_id": payload["title"]},
    )

    result = agent_admin_window.open_grid_window(project)

    assert result["recovered"] is False
    assert len(payloads) == 1
    assert payloads[0]["title"] == "clawseat-spawn49"
    assert payloads[0]["panes"] == [
        {"label": "ancestor", "command": "tmux attach -t '=spawn49-ancestor'"}
    ]
    assert "ancestor-only grid" in capsys.readouterr().err
