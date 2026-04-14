from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class SessionHooks:
    agentctl_path: str
    load_project: Callable[[str], Any]
    apply_template: Callable[[Any, Any], None]
    reconcile_session_runtime: Callable[[Any], Any]
    ensure_api_secret_ready: Callable[[Any], None]
    load_project_sessions: Callable[[str], dict[str, Any]]
    project_template_context: Callable[[Any], Any]
    load_engineers: Callable[[], dict[str, Any]]
    tmux_has_session: Callable[[str], bool]
    build_monitor_layout: Callable[[Any, dict[str, Any]], None]


class SessionService:
    def __init__(self, hooks: SessionHooks) -> None:
        self.hooks = hooks

    def build_engineer_exec(self, session: Any) -> list[str]:
        if session.wrapper:
            return [session.wrapper]
        return [self.hooks.agentctl_path, "run-engineer", "--project", session.project, session.engineer_id]

    def start_engineer(self, session: Any, reset: bool = False) -> None:
        session = self.hooks.reconcile_session_runtime(session)
        self.hooks.ensure_api_secret_ready(session)
        project = self.hooks.load_project(session.project)
        self.hooks.apply_template(session, project)
        if reset and self.hooks.tmux_has_session(session.session):
            subprocess.run(["tmux", "kill-session", "-t", session.session], check=False)
        if self.hooks.tmux_has_session(session.session):
            return
        cmd = self.build_engineer_exec(session)
        try:
            subprocess.run(
                [
                    "tmux",
                    "new-session",
                    "-d",
                    "-s",
                    session.session,
                    "-c",
                    session.workspace,
                    " ".join(shlex.quote(part) for part in cmd),
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            if not self.hooks.tmux_has_session(session.session):
                raise

    def stop_engineer(self, session: Any) -> None:
        subprocess.run(
            ["tmux", "kill-session", "-t", session.session],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def status(self, session: Any) -> str:
        return "running" if self.hooks.tmux_has_session(session.session) else "stopped"

    def project_engineer_context(self, project: Any) -> tuple[dict[str, Any], list[str]]:
        context = self.hooks.project_template_context(project)
        if context:
            template_profiles, engineer_order, _ = context
            return template_profiles, engineer_order
        engineers = self.hooks.load_engineers()
        return engineers, list(project.engineers)

    def project_autostart_engineer_ids(self, project: Any, *, ensure_monitor: bool = False) -> list[str]:
        engineer_map, engineer_order = self.project_engineer_context(project)
        ordered_ids = [engineer_id for engineer_id in engineer_order if engineer_id in project.engineers]
        if not ordered_ids:
            ordered_ids = list(project.engineers)

        if ensure_monitor and project.window_mode != "tabs-1up":
            visible_ids = [
                engineer_id
                for engineer_id in project.monitor_engineers[: max(1, project.monitor_max_panes)]
                if engineer_id in project.engineers
            ]
            if visible_ids:
                return visible_ids

        frontstage_ids = [
            engineer_id
            for engineer_id in ordered_ids
            if engineer_map.get(engineer_id)
            and engineer_map[engineer_id].patrol_authority
            and engineer_map[engineer_id].remind_active_loop_owner
        ]
        if frontstage_ids:
            return frontstage_ids

        human_facing_ids = [
            engineer_id
            for engineer_id in ordered_ids
            if engineer_map.get(engineer_id) and engineer_map[engineer_id].human_facing
        ]
        if human_facing_ids:
            return human_facing_ids[:1]

        return ordered_ids[:1]

    def start_project(self, project: Any, ensure_monitor: bool = True, reset: bool = False) -> None:
        sessions = self.hooks.load_project_sessions(project.name)
        start_ids = self.project_autostart_engineer_ids(project, ensure_monitor=ensure_monitor)
        for engineer_id in start_ids:
            if engineer_id in sessions:
                self.start_engineer(sessions[engineer_id], reset=reset)
        if (
            ensure_monitor
            and project.window_mode != "tabs-1up"
            and (reset or not self.hooks.tmux_has_session(project.monitor_session))
        ):
            self.hooks.build_monitor_layout(project, sessions)

    def seat_requires_launch_confirmation(self, project: Any, engineer_id: str) -> bool:
        engineer_map, _ = self.project_engineer_context(project)
        engineer = engineer_map.get(engineer_id)
        if engineer is None:
            return True
        return not (engineer.patrol_authority and engineer.remind_active_loop_owner)
