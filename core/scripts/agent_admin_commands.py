from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class CommandHooks:
    error_cls: type[Exception]
    load_project_or_current: Callable[[str | None], Any]
    resolve_engineer_session: Callable[..., Any]
    provision_session_heartbeat: Callable[..., tuple[bool, str]]
    load_project_sessions: Callable[[str], dict[str, Any]]
    tmux_has_session: Callable[[str], bool]
    load_projects: Callable[[], dict[str, Any]]
    get_current_project_name: Callable[[dict[str, Any]], str | None]
    session_service: Any
    open_monitor_window: Callable[[Any, dict[str, Any], dict[str, Any]], None]
    open_dashboard_window: Callable[[list[Any]], None]
    open_project_tabs_window: Callable[[Any, dict[str, Any], dict[str, Any]], None]
    open_engineer_window: Callable[[Any, Any | None], None]
    load_engineers: Callable[[], dict[str, Any]]


class CommandHandlers:
    def __init__(self, hooks: CommandHooks) -> None:
        self.hooks = hooks

    def session_start_engineer(self, args: Any) -> int:
        session = self.hooks.resolve_engineer_session(args.engineer, project_name=getattr(args, "project", None))
        self.hooks.session_service.start_engineer(session, reset=args.reset)
        try:
            provisioned, detail = self.hooks.provision_session_heartbeat(session)
            if detail:
                print(detail)
        except Exception as exc:
            print(f"heartbeat: {exc}")
        print(session.session)
        return 0

    def session_provision_heartbeat(self, args: Any) -> int:
        session = self.hooks.resolve_engineer_session(args.engineer, project_name=getattr(args, "project", None))
        provisioned, detail = self.hooks.provision_session_heartbeat(
            session,
            force=bool(args.force),
            dry_run=bool(args.dry_run),
        )
        if detail:
            print(detail)
        already_verified = "already verified" in detail.lower() if detail else False
        return 0 if provisioned or args.dry_run or already_verified else 1

    def session_stop_engineer(self, args: Any) -> int:
        session = self.hooks.resolve_engineer_session(args.engineer, project_name=getattr(args, "project", None))
        self.hooks.session_service.stop_engineer(session)
        return 0

    def session_start_project(self, args: Any) -> int:
        project = self.hooks.load_project_or_current(args.project)
        started_ids = self.hooks.session_service.project_autostart_engineer_ids(
            project,
            ensure_monitor=not args.no_monitor,
        )
        self.hooks.session_service.start_project(project, ensure_monitor=not args.no_monitor, reset=args.reset)
        print(",".join(started_ids))
        return 0

    def session_status(self, args: Any) -> int:
        if args.project:
            project = self.hooks.load_project_or_current(args.project)
            project_sessions = self.hooks.load_project_sessions(project.name)
            print(project.monitor_session, "running" if self.hooks.tmux_has_session(project.monitor_session) else "stopped")
            for engineer_id in project.engineers:
                if engineer_id in project_sessions:
                    session = project_sessions[engineer_id]
                    print(session.session, self.hooks.session_service.status(session))
            return 0
        session = self.hooks.resolve_engineer_session(args.engineer, project_name=getattr(args, "project", None))
        print(session.session, self.hooks.session_service.status(session))
        return 0

    def window_open_monitor(self, args: Any) -> int:
        project = self.hooks.load_project_or_current(args.project)
        if not project.monitor_engineers:
            raise self.hooks.error_cls(f"{project.name} has no monitor engineers configured")
        if project.window_mode != "tabs-1up":
            self.hooks.session_service.start_project(project, ensure_monitor=True, reset=False)
        self.hooks.open_monitor_window(project, self.hooks.load_project_sessions(project.name), self.hooks.load_engineers())
        return 0

    def window_open_dashboard(self, args: Any) -> int:
        projects = self.hooks.load_projects()
        current_name = self.hooks.get_current_project_name(projects)
        ordered: list[Any] = []
        if current_name and current_name in projects:
            ordered.append(projects[current_name])
        for name in sorted(projects):
            if current_name and name == current_name:
                continue
            ordered.append(projects[name])
        visible_projects = [project for project in ordered if project.monitor_engineers]
        if not visible_projects:
            raise self.hooks.error_cls("No projects with monitor engineers configured")

        tabs_projects = [project.name for project in visible_projects if project.window_mode == "tabs-1up"]
        if tabs_projects:
            tabs_list = ", ".join(tabs_projects)
            raise self.hooks.error_cls(
                "window open-dashboard does not support tabs-1up projects. "
                f"Use `agent-admin window open-monitor <project>` for: {tabs_list}"
            )

        for project in visible_projects:
            self.hooks.session_service.start_project(project, ensure_monitor=True, reset=False)
        self.hooks.open_dashboard_window(visible_projects)
        return 0

    def window_open_engineer(self, args: Any) -> int:
        session = self.hooks.resolve_engineer_session(args.engineer, project_name=getattr(args, "project", None))
        project = self.hooks.load_project_or_current(session.project)
        if not self.hooks.tmux_has_session(session.session):
            if self.hooks.session_service.seat_requires_launch_confirmation(project, session.engineer_id):
                raise self.hooks.error_cls(
                    f"{project.name}:{session.engineer_id} requires explicit launch confirmation before start. "
                    "Use gstack-harness/scripts/start_seat.py to review the launch summary first, then rerun with --confirm-start."
                )
            self.hooks.session_service.start_engineer(session)
        if project.window_mode == "tabs-1up":
            self.hooks.open_project_tabs_window(
                project,
                self.hooks.load_project_sessions(project.name),
                self.hooks.load_engineers(),
            )
        else:
            self.hooks.open_engineer_window(session, self.hooks.load_engineers().get(session.engineer_id))
        return 0
