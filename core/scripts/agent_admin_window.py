from __future__ import annotations

import shlex
import subprocess
import sys
import textwrap
import time
from typing import Any


class AgentAdminWindowError(Exception):
    pass


TMUX_COMMAND_RETRIES = 2
TMUX_COMMAND_TIMEOUT_SECONDS = 8.0
TMUX_COMMAND_RETRY_DELAY_SECONDS = 1.0
ITERM_SCRIPT_APPS = ("iTerm", "iTerm2")
ITERM_SCRIPT_RETRIES = 3


def tmux(
    args: list[str],
    check: bool = True,
    capture_output: bool = False,
    text: bool = True,
    timeout: float = TMUX_COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    cmd = ["tmux", *args]
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=text, timeout=timeout)


def tmux_with_retry(
    args: list[str],
    *,
    label: str,
    check: bool = True,
    retries: int = TMUX_COMMAND_RETRIES,
    timeout: float = TMUX_COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    last_error: subprocess.CalledProcessError | subprocess.TimeoutExpired | None = None
    for attempt in range(1, retries + 1):
        try:
            return tmux(
                args,
                check=check,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            if attempt >= retries:
                break
            print(
                f"tmux_retry: {label} attempt={attempt}/{retries} failed: {exc!s}",
                file=sys.stderr,
            )
            time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)

    if isinstance(last_error, subprocess.TimeoutExpired):
        raise AgentAdminWindowError(
            f"{label} failed after {retries} attempt(s): timeout after "
            f"{TMUX_COMMAND_TIMEOUT_SECONDS:.1f}s each, args={args}"
        ) from last_error
    if isinstance(last_error, subprocess.CalledProcessError):
        detail = str(last_error.stderr or last_error.stdout or "").strip()
        raise AgentAdminWindowError(
            f"{label} failed after {retries} attempt(s), exit={last_error.returncode}, "
            f"detail={detail}, args={args}"
        ) from last_error
    raise AgentAdminWindowError(f"{label} failed after {retries} attempt(s): args={args}")


def tmux_has_session(session: str) -> bool:
    try:
        result = tmux_with_retry(
            ["has-session", "-t", session],
            label=f"tmux_has_session({session})",
            check=False,
            retries=1,
        )
        return result.returncode == 0
    except AgentAdminWindowError:
        return False


def tmux_window_panes(window_target: str) -> list[dict[str, int | str]]:
    proc = tmux_with_retry(
        [
            "list-panes",
            "-t",
            window_target,
            "-F",
            "#{pane_id}\t#{pane_width}\t#{pane_height}\t#{pane_left}\t#{pane_top}",
        ],
        label=f"tmux_window_panes({window_target})",
        check=True,
    )
    panes: list[dict[str, int | str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        pane_id, width, height, left, top = parts
        panes.append(
            {
                "pane_id": pane_id,
                "width": int(width),
                "height": int(height),
                "left": int(left),
                "top": int(top),
            }
        )
    return panes


def monitor_attach_command(session: str) -> str:
    quoted = shlex.quote(session)
    return f"exec env -u TMUX tmux attach -t {quoted} || exec $SHELL -l"


def build_attach_command(
    *,
    session: str,
    workspace: str,
    fallback_to_shell: bool = True,
) -> str:
    """
    Compose a deterministic shell command for attaching into an existing tmux session.

    The command is intentionally strict:
    - run in target workspace
    - unset TMUX to avoid nested-session corruption
    - fail hard to shell fallback if attach fails (iterm-only policy)
    """
    attach_target = shlex.quote(session)
    workspace_dir = shlex.quote(workspace)
    fallback = " || exec $SHELL -l" if fallback_to_shell else ""
    return f"cd {workspace_dir} && exec env -u TMUX tmux attach -t {attach_target}{fallback}"


def _iterm_script_command(command: str, *, context: str) -> str:
    cleaned = command.strip()
    if not cleaned:
        raise AgentAdminWindowError(f"empty iterm command for {context}")
    return applescript_quote(cleaned)


def shell_attach_command(session: Any) -> str:
    return build_attach_command(session=session.session, workspace=session.workspace)


def project_monitor_shell_command(project: Any) -> str:
    # Use env -u TMUX to avoid nested-tmux interference.
    return build_attach_command(session=project.monitor_session, workspace=project.repo_root)


def _monitor_layout_target_sessions(project: Any, sessions: dict[str, Any]) -> list[Any]:
    target_ids = project.monitor_engineers[: max(1, project.monitor_max_panes)]
    resolved: list[Any] = []
    missing: list[str] = []
    for engineer_id in target_ids:
        session = sessions.get(engineer_id)
        if session is None or not tmux_has_session(session.session):
            missing.append(engineer_id)
            continue
        resolved.append(session)
    if not resolved:
        raise AgentAdminWindowError(
            f"{project.name} monitor layout has no running sessions. missing={missing}"
        )
    if missing:
        print(
            f"agent_admin_window: monitor layout skipped missing sessions for {project.name}: {', '.join(missing)}",
            file=sys.stderr,
        )
    return resolved


def build_monitor_layout(project: Any, sessions: dict[str, Any]) -> None:
    monitor = project.monitor_session
    if tmux_has_session(monitor):
        print(
            f"agent_admin_window: rebuilding monitor session '{monitor}' for {project.name}: killing existing session",
            file=sys.stderr,
        )
        tmux_with_retry(
            ["kill-session", "-t", monitor],
            label=f"kill existing monitor session {monitor}",
            check=False,
            retries=TMUX_COMMAND_RETRIES,
        )

    repo_root = project.repo_root
    visible_engineer_sessions = _monitor_layout_target_sessions(project, sessions)
    if not visible_engineer_sessions:
        raise AgentAdminWindowError(f"{project.name} has no monitor engineers configured")

    visible_engineer_ids = [session.engineer_id for session in visible_engineer_sessions]
    try:
        tmux_with_retry(
            ["new-session", "-d", "-x", "240", "-y", "80", "-s", monitor, "-c", repo_root],
            label=f"new monitor session {monitor}",
        )

        first_target = f"{monitor}:0.0"
        first_engineer = visible_engineer_sessions[0]
        tmux_with_retry(
            [
                "send-keys",
                "-t",
                first_target,
                monitor_attach_command(first_engineer.session),
                "C-m",
            ],
            label=f"seed first monitor pane attach {first_engineer.engineer_id}",
        )

        if len(visible_engineer_sessions) >= 2:
            second = visible_engineer_sessions[1]
            tmux_with_retry(
                [
                    "split-window",
                    "-h",
                    "-t",
                    first_target,
                    "-c",
                    repo_root,
                    monitor_attach_command(second.session),
                ],
                label=f"split pane for second monitor seat {second.engineer_id}",
            )

        panes = tmux_window_panes(f"{monitor}:0")
        if len(visible_engineer_sessions) >= 3 and panes:
            leftmost = min(panes, key=lambda item: (int(item["left"]), int(item["top"])))
            leftmost_id = str(leftmost["pane_id"])
            third = visible_engineer_sessions[2]
            tmux_with_retry(
                [
                    "split-window",
                    "-v",
                    "-t",
                    leftmost_id,
                    "-c",
                    repo_root,
                    monitor_attach_command(third.session),
                ],
                label=f"split pane for third monitor seat {third.engineer_id}",
            )

        panes = tmux_window_panes(f"{monitor}:0")
        if len(visible_engineer_sessions) >= 4 and panes:
            rightmost = max(panes, key=lambda item: (int(item["left"]), -int(item["top"])))
            rightmost_id = str(rightmost["pane_id"])
            fourth = visible_engineer_sessions[3]
            tmux_with_retry(
                [
                    "split-window",
                    "-v",
                    "-t",
                    rightmost_id,
                    "-c",
                    repo_root,
                    monitor_attach_command(fourth.session),
                ],
                label=f"split pane for fourth monitor seat {fourth.engineer_id}",
            )

        layout = "tiled"
        if project.window_mode == "tabs-1up":
            layout = "even-vertical"
        if len(visible_engineer_sessions) == 4:
            layout = "tiled"
        tmux_with_retry(
            ["select-layout", "-t", f"{monitor}:0", layout],
            label=f"set monitor layout {monitor}",
            check=False,
        )
    except AgentAdminWindowError as exc:
        # Roll back partial layout to avoid half-open tmux sessions.
        if tmux_has_session(monitor):
            tmux_with_retry(
                ["kill-session", "-t", monitor],
                label=f"rollback monitor session {monitor}",
                check=False,
                retries=TMUX_COMMAND_RETRIES,
            )
        raise AgentAdminWindowError(
            f"{project.name} monitor layout failed for session '{monitor}' (engineers={visible_engineer_ids}): {exc}"
        ) from exc


def osascript(script: str) -> None:
    result = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            ["osascript", "-e", script],
            output=result.stdout,
            stderr=result.stderr,
        )


def _sanitize_applescript_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def run_iterm_script(script_factory: Any) -> None:
    # iTerm-first hard-stop policy: do not downgrade to non-iTerm terminal tooling.
    # If this fails, caller should surface the error and ask operator for remediation.
    attempts = 0
    last_error: subprocess.CalledProcessError | None = None
    for app_name in ITERM_SCRIPT_APPS:
        for attempt in range(1, ITERM_SCRIPT_RETRIES + 1):
            attempts += 1
            try:
                osascript(script_factory(app_name))
                return
            except subprocess.CalledProcessError as exc:
                last_error = exc
                if attempt >= ITERM_SCRIPT_RETRIES:
                    break
                print(
                    f"iterm_script_retry: app={app_name} attempt={attempt}/{ITERM_SCRIPT_RETRIES} rc={exc.returncode}",
                    file=sys.stderr,
                )
                time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)
        if last_error is not None and last_error.returncode != 0:
            last_code = getattr(last_error, "returncode", "n/a")
            last_detail = ""
            if getattr(last_error, "stderr", None):
                last_detail = (getattr(last_error, "stderr") or "").strip()
            if not last_detail and getattr(last_error, "output", None):
                last_detail = (getattr(last_error, "output") or "").strip()
            print(
                f"iterm_script_failed_once: app={app_name} total_attempts={attempts} last_rc={last_code} "
                f"detail={last_detail}",
                file=sys.stderr,
            )
    if last_error is not None:
        raise AgentAdminWindowError(
            f"AppleScript failed after retries; apps={', '.join(ITERM_SCRIPT_APPS)} "
            f"last_rc={getattr(last_error, 'returncode', 'n/a')}"
        ) from last_error


def applescript_quote(value: str) -> str:
    return _sanitize_applescript_text(value)


def iterm_run_command(command: str, title: str | None = None) -> None:
    # Ensure command content is deterministic before writing into AppleScript text.
    escaped_command = _iterm_script_command(command, context="iterm_run_command")
    title_lines = ""
    if title:
        escaped_title = applescript_quote(title)
        title_lines = f'\n      set name to "{escaped_title}"'

    def build_script(app_name: str) -> str:
        return textwrap.dedent(
            f'''
            tell application "{app_name}"
              activate
              create window with default profile
              tell current session of current window
                {title_lines.strip()}
                write text "{escaped_command}"
              end tell
            end tell
            '''
            ).strip()

    run_iterm_script(build_script)


def open_monitor_window(project: Any, sessions: dict[str, Any], engineers: dict[str, Any]) -> None:
    if project.window_mode == "tabs-1up":
        open_project_tabs_window(project, sessions, engineers)
        return
    iterm_run_command(project_monitor_shell_command(project))


def open_project_tabs_window(project: Any, sessions: dict[str, Any], engineers: dict[str, Any]) -> None:
    visible_engineer_ids = project.monitor_engineers or project.engineers
    if not visible_engineer_ids:
        raise AgentAdminWindowError(f"{project.name} has no monitor engineers configured")

    resolved_sessions: list[Any] = []
    for engineer_id in visible_engineer_ids:
        session = sessions.get(engineer_id)
        if session is None:
            continue
        if tmux_has_session(session.session):
            resolved_sessions.append(session)

    if not resolved_sessions:
        raise AgentAdminWindowError(
            f"{project.name} has no running engineer sessions to open. "
            "Start the needed seats first, then reopen the project window."
        )

    def build_script(app_name: str) -> str:
        # Note: we intentionally do NOT close existing project tabs before
        # creating the new window. Closing tabs kills their shell process,
        # which detaches running agent sessions (including the caller if it
        # runs open-monitor from inside one of those tabs). Old windows are
        # left for the user to close manually or are replaced naturally when
        # the tmux session reattaches in the new tab.
        lines = [
            f'tell application "{app_name}"',
            "  activate",
            "  set projectWindow to (create window with default profile)",
        ]

        for tab_index, session in enumerate(resolved_sessions):
            if tab_index > 0:
                lines.append("  tell projectWindow")
                lines.append("    create tab with default profile")
                lines.append("  end tell")
            command = _iterm_script_command(shell_attach_command(session), context=f"monitor tab {session.engineer_id}")
            engineer = engineers.get(session.engineer_id)
            title = applescript_quote(f"{project.name}:{engineer.display_name if engineer else session.engineer_id}")
            lines.append("  tell current session of current window")
            lines.append(f'    set name to "{title}"')
            lines.append(f'    write text "{command}"')
            lines.append("  end tell")

        lines.append("end tell")
        return "\n".join(lines)

    run_iterm_script(build_script)


def open_dashboard_window(projects: list[Any]) -> None:
    if not projects:
        raise AgentAdminWindowError("No projects configured")

    def build_script(app_name: str) -> str:
        lines = [
            f'tell application "{app_name}"',
            "  activate",
            "  set dashboardWindow to (create window with default profile)",
        ]

        for tab_index, project in enumerate(projects):
            if tab_index > 0:
                lines.append("  tell dashboardWindow")
                lines.append("    create tab with default profile")
                lines.append("  end tell")
            command = _iterm_script_command(
                project_monitor_shell_command(project),
                context="open_dashboard_window",
            )
            lines.append("  tell current session of current window")
            lines.append(f'    write text "{command}"')
            lines.append("  end tell")

        lines.append("end tell")
        return "\n".join(lines)

    run_iterm_script(build_script)


def open_engineer_window(session: Any, engineer: Any | None) -> None:
    iterm_run_command(shell_attach_command(session), title=display_name_for(engineer, session.engineer_id))


def display_name_for(engineer: Any | None, fallback: str) -> str:
    if engineer and getattr(engineer, "display_name", ""):
        return engineer.display_name
    return fallback
