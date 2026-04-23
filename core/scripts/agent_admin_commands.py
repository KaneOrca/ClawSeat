from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import agent_admin_window as window_ops


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

    def session_reseed_sandbox(self, args: Any) -> int:
        project = self.hooks.load_project_or_current(getattr(args, "project", None))
        engineer_ids = list(getattr(args, "engineers", []) or [])
        if getattr(args, "all", False):
            engineer_ids = list(project.engineers)
        if not engineer_ids:
            raise self.hooks.error_cls(
                "session reseed-sandbox requires --all or one or more engineer ids"
            )

        changed: list[str] = []
        for engineer_id in engineer_ids:
            session = self.hooks.resolve_engineer_session(engineer_id, project_name=project.name)
            try:
                updated = self.hooks.session_service.reseed_sandbox_user_tool_dirs(session)
            except Exception as exc:  # noqa: BLE001 - surface a readable CLI error
                raise self.hooks.error_cls(
                    f"reseed-sandbox failed for {session.session}: {exc}"
                ) from exc
            if updated:
                changed.append(f"{session.engineer_id}: {', '.join(updated)}")

        if changed:
            print("\n".join(changed))
        else:
            print(f"no sandbox tool dirs needed reseed for {project.name}")
        return 0

    def session_batch_start_engineer(self, args: Any) -> int:
        """Atomically start N seats: parallel tmux, then single iTerm window.

        Replaces the shell idiom `for seat in ...; do session start-engineer
        $seat &; done; wait; window open-monitor <project>` — which is easy
        to get wrong (forgetting `wait` races Phase 2 against Phase 1's
        still-starting tmux sessions, causing open_project_tabs_window to
        skip not-yet-ready seats and leaving partial tabs).

        Phase 1 uses a thread pool so concurrent start_engineer calls share
        Python process state (no subprocess-to-subprocess coordination).
        start_engineer itself is per-seat in every mutation (per-seat
        session.toml, per-seat workspace, per-seat tmux session name) so
        running it in parallel is safe.

        Phase 2 is a single `open_monitor_window` call — one osascript, one
        atomic AppleScript block. No concurrency during Phase 2 means no
        iTerm current-window race even without the fix in
        agent_admin_window.py.
        """
        import concurrent.futures
        import sys

        engineer_ids = list(getattr(args, "engineers", []) or [])
        if not engineer_ids:
            raise self.hooks.error_cls(
                "batch-start-engineer requires one or more engineer ids"
            )
        # Dedupe while preserving order so the operator's intent reads
        # left-to-right but we never ask tmux to start the same session twice.
        seen: set[str] = set()
        ordered: list[str] = []
        for eid in engineer_ids:
            if eid not in seen:
                seen.add(eid)
                ordered.append(eid)
        engineer_ids = ordered

        project_name = getattr(args, "project", None)
        reset = bool(getattr(args, "reset", False))
        skip_iterm = bool(getattr(args, "no_iterm", False))

        # Resolve all sessions up front so we fail fast on typos (bad seat
        # id) before we touch tmux. The resolve step also normalises engineer
        # names for downstream hooks.
        sessions_to_start: list[Any] = []
        for eid in engineer_ids:
            sessions_to_start.append(
                self.hooks.resolve_engineer_session(eid, project_name=project_name)
            )

        # Phase 1 — parallel tmux start.
        def _start_one(session: Any) -> tuple[str, Exception | None]:
            try:
                self.hooks.session_service.start_engineer(session, reset=reset)
                return (session.engineer_id, None)
            except Exception as exc:  # noqa: BLE001 - collect, don't abort pool
                return (session.engineer_id, exc)

        failures: list[tuple[str, Exception]] = []
        started: list[Any] = []
        max_workers = min(len(sessions_to_start), 8)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_start_one, s): s for s in sessions_to_start
            }
            # concurrent.futures.wait blocks until every future is done —
            # this IS the `wait` that shell operators had to remember.
            for fut in concurrent.futures.as_completed(futures):
                session = futures[fut]
                _eid, err = fut.result()
                if err is None:
                    started.append(session)
                    print(f"batch-start-engineer: {session.session} started")
                else:
                    failures.append((session.engineer_id, err))
                    print(
                        f"batch-start-engineer: {session.engineer_id} FAILED — {err}",
                        file=sys.stderr,
                    )

        # Best-effort heartbeat provisioning for started Claude sessions. We
        # do this sequentially after tmux Phase 1 because heartbeat itself
        # writes per-seat state and is not the hot path.
        for session in started:
            try:
                _provisioned, detail = self.hooks.provision_session_heartbeat(session)
                if detail:
                    print(detail)
            except Exception as exc:  # noqa: BLE001 - heartbeat is non-fatal
                print(f"heartbeat ({session.engineer_id}): {exc}", file=sys.stderr)

        if failures:
            failed_ids = [eid for eid, _ in failures]
            raise self.hooks.error_cls(
                f"batch-start-engineer: {len(failures)}/{len(engineer_ids)} "
                f"seats failed to start: {failed_ids}. "
                "Not opening iTerm window; fix the failing seats then re-run."
            )

        # Phase 2 — single atomic open-monitor.
        if skip_iterm:
            print("batch-start-engineer: --no-iterm set, skipping Phase 2")
            return 0

        project = self.hooks.load_project_or_current(project_name)
        if not project.monitor_engineers:
            print(
                f"batch-start-engineer: project '{project.name}' has no "
                "monitor_engineers; skipping iTerm window. Started tmux "
                "sessions remain alive — attach manually if needed.",
                file=sys.stderr,
            )
            return 0
        if project.window_mode != "tabs-1up":
            # For non-tabs modes (e.g. project-monitor) we defer to the same
            # path window_open_monitor uses, which may also start a monitor
            # session. Safe to share the code.
            self.hooks.session_service.start_project(
                project, ensure_monitor=True, reset=False
            )
        self.hooks.open_monitor_window(
            project,
            self.hooks.load_project_sessions(project.name),
            self.hooks.load_engineers(),
        )
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
        self.hooks.session_service.stop_engineer(session, close_iterm_tab=not getattr(args, "keep_iterm_tab", False))
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

    def window_open_grid(self, args: Any) -> int:
        projects = self.hooks.load_projects()
        project = projects.get(args.project)
        if project is None:
            raise self.hooks.error_cls(f"project not registered: {args.project}")
        window_ops.open_grid_window(
            project,
            recover=bool(getattr(args, "recover", False)),
            open_memory=bool(getattr(args, "open_memory", False)),
        )
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

    def window_reseed_pane(self, args: Any) -> int:
        project = self.hooks.load_project_or_current(getattr(args, "project", None))
        result = window_ops.reseed_pane(project, args.seat)
        print(f"reseeded {result['project']}/{result['seat_id']}")
        return 0
