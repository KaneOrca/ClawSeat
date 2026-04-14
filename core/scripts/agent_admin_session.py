from __future__ import annotations

import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable


TMUX_COMMAND_RETRIES = 2
TMUX_COMMAND_TIMEOUT_SECONDS = 8.0
TMUX_COMMAND_RETRY_DELAY_SECONDS = 1.0


class SessionStartError(RuntimeError):
    """Raised when a seat session cannot be created into a verified running tmux state."""


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

    def _run_tmux_with_retry(
        self,
        args: list[str],
        *,
        reason: str,
        check: bool = False,
        retries: int = TMUX_COMMAND_RETRIES,
        timeout: float = TMUX_COMMAND_TIMEOUT_SECONDS,
    ) -> subprocess.CompletedProcess:
        last: subprocess.CompletedProcess | None = None
        for attempt in range(1, retries + 1):
            if not check:
                try:
                    return subprocess.run(
                        ["tmux", *args],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                except subprocess.TimeoutExpired as exc:
                    print(
                        f"tmux_retry: {reason} attempt={attempt}/{retries} timeout={timeout}s",
                        file=sys.stderr,
                    )
                    if attempt >= retries:
                        raise SessionStartError(
                            f"{reason} timeout after {retries} attempt(s) for args={args}"
                        ) from exc
                except OSError as exc:
                    raise SessionStartError(f"{reason} failed before executing tmux: {exc}") from exc
                if attempt < retries:
                    time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)
                    continue
                raise SessionStartError(f"{reason} failed for tmux args={args}")
            try:
                result = subprocess.run(
                    ["tmux", *args],
                    check=check,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if result.returncode == 0:
                    return result
                last = result
            except subprocess.CalledProcessError as exc:
                last = exc
            except subprocess.TimeoutExpired as exc:
                last = None
                print(
                    f"tmux_retry: {reason} attempt={attempt}/{retries} timeout={timeout}s",
                    file=sys.stderr,
                )
                if attempt >= retries:
                    raise SessionStartError(
                        f"{reason} timeout after {retries} attempt(s) for args={args}"
                    ) from exc
            except OSError as exc:
                raise SessionStartError(f"{reason} failed before executing tmux: {exc}") from exc
            else:
                if result.returncode == 0:
                    return result
                print(
                    f"tmux_retry: {reason} attempt={attempt}/{retries} rc={result.returncode}",
                    file=sys.stderr,
                )
            if attempt < retries:
                time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)

        if last is not None:
            detail = (last.stderr or last.stdout or "").strip()
            raise SessionStartError(
                f"{reason} failed after {retries} attempt(s), exit={last.returncode}, detail={detail}, args={args}"
            )
        raise SessionStartError(f"{reason} failed for tmux args={args}")

    def _session_window_state(self, session_name: str) -> str:
        if not self.hooks.tmux_has_session(session_name):
            return "session=missing"
        result = self._run_tmux_with_retry(
            ["list-panes", "-t", session_name, "-F", "#{session_name}|#{pane_id}|#{pane_current_command}"],
            reason=f"snapshot session windows for {session_name}",
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"session={session_name}, panes={result.stdout.strip()}"
        return f"session={session_name}, panes=empty"

    def _assert_session_running(self, session: Any, *, operation: str) -> None:
        if not self.hooks.tmux_has_session(session.session):
            raise SessionStartError(
                f"{operation} failed for '{session.session}': session missing after startup; state={self._session_window_state(session.session)}"
            )
        output = self._run_tmux_with_retry(
            [
                "list-panes",
                "-t",
                session.session,
                "-F",
                "#{pane_id}|#{pane_current_command}",
            ],
            reason=f"{operation} verify panes for {session.session}",
            check=False,
        )
        if output.returncode != 0 or not output.stdout.strip():
            raise SessionStartError(
                f"{operation} failed for '{session.session}': no active panes detected; state={self._session_window_state(session.session)}"
            )

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
            self._run_tmux_with_retry(
                ["kill-session", "-t", session.session],
                reason=f"reset existing session {session.session}",
                check=False,
            )
        if self.hooks.tmux_has_session(session.session):
            self._assert_session_running(session, operation=f"start_engineer idempotent check for {session.session}")
            return
        cmd = self.build_engineer_exec(session)
        quoted_cmd = " ".join(shlex.quote(part) for part in cmd)
        for attempt in range(1, TMUX_COMMAND_RETRIES + 1):
            try:
                self._run_tmux_with_retry(
                    [
                        "new-session",
                        "-d",
                        "-s",
                        session.session,
                        "-c",
                        session.workspace,
                        quoted_cmd,
                    ],
                    reason=f"start engineer {session.session} attempt={attempt}",
                    check=True,
                )
                self._assert_session_running(session, operation=f"start engineer {session.session}")
                break
            except SessionStartError as exc:
                last_error = exc
                if self.hooks.tmux_has_session(session.session):
                    self._run_tmux_with_retry(
                        ["kill-session", "-t", session.session],
                        reason=f"cleanup partial session {session.session}",
                        check=False,
                    )
                if attempt < TMUX_COMMAND_RETRIES:
                    print(
                        f"start_engineer_retry: session={session.session} attempt={attempt}/"
                        f"{TMUX_COMMAND_RETRIES} rc_waiting=retry",
                        file=sys.stderr,
                    )
                    time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)
                    continue
                detail = self._session_window_state(session.session)
                raise SessionStartError(
                    f"start engineer '{session.session}' failed after {TMUX_COMMAND_RETRIES} attempts; "
                    f"window_state={detail}; reason={exc}"
                ) from exc
        # Enable tmux terminal titles so iTerm tabs show session name.
        # set-titles-string '#{session_name}' uses the session identifier as the tab title.
        self._run_tmux_with_retry(
            ["set", "-g", "set-titles", "on"],
            reason=f"enable titles on {session.session}",
            check=False,
        )
        self._run_tmux_with_retry(
            ["set", "-g", "set-titles-string", "#{session_name}"],
            reason=f"set session title on {session.session}",
            check=False,
        )

    def stop_engineer(self, session: Any) -> None:
        self._run_tmux_with_retry(
            ["kill-session", "-t", session.session],
            reason=f"stop engineer {session.session}",
            check=False,
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
            self._start_monitor_with_retry(project, sessions, reset=reset)

    def seat_requires_launch_confirmation(self, project: Any, engineer_id: str) -> bool:
        engineer_map, _ = self.project_engineer_context(project)
        engineer = engineer_map.get(engineer_id)
        if engineer is None:
            return True
        return not (engineer.patrol_authority and engineer.remind_active_loop_owner)

    def _start_monitor_with_retry(self, project: Any, sessions: dict[str, Any], *, reset: bool) -> None:
        last_error: SessionStartError | None = None
        for attempt in range(1, TMUX_COMMAND_RETRIES + 1):
            try:
                if reset and self.hooks.tmux_has_session(project.monitor_session):
                    self._run_tmux_with_retry(
                        ["kill-session", "-t", project.monitor_session],
                        reason=f"recycle monitor session {project.monitor_session}",
                        check=False,
                    )
                if self.hooks.tmux_has_session(project.monitor_session):
                    # Re-run layout from scratch to avoid partial state.
                    self._run_tmux_with_retry(
                        ["kill-session", "-t", project.monitor_session],
                        reason=f"rebuild monitor session {project.monitor_session}",
                        check=False,
                    )
                self.hooks.build_monitor_layout(project, sessions)
                if not self.hooks.tmux_has_session(project.monitor_session):
                    raise SessionStartError(
                        f"monitor session {project.monitor_session} missing after layout build"
                    )
                # Verify monitor session contains at least one pane.
                monitor_state = self._session_window_state(project.monitor_session)
                if ", panes=empty" in monitor_state:
                    raise SessionStartError(f"monitor session empty after layout build: {monitor_state}")
                return
            except Exception as exc:
                wrapped_error = exc if isinstance(exc, SessionStartError) else SessionStartError(str(exc))
                window_state = self._session_window_state(project.monitor_session)
                last_error = SessionStartError(
                    f"monitor session '{project.monitor_session}' error={wrapped_error}; window_state={window_state}"
                )
                if self.hooks.tmux_has_session(project.monitor_session):
                    self._run_tmux_with_retry(
                        ["kill-session", "-t", project.monitor_session],
                        reason=f"cleanup monitor session {project.monitor_session}",
                        check=False,
                    )
                if attempt < TMUX_COMMAND_RETRIES:
                    print(
                        f"start_monitor_retry: project={project.name} attempt={attempt}/{TMUX_COMMAND_RETRIES}",
                        file=sys.stderr,
                    )
                    time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)
                    continue
        raise SessionStartError(
            f"start monitor for {project.name} failed after {TMUX_COMMAND_RETRIES} attempts; reason={last_error}"
        ) from last_error
