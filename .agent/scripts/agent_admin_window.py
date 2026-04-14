from __future__ import annotations

import shlex
import subprocess
import textwrap
from typing import Any


class AgentAdminWindowError(Exception):
    pass


def tmux(args: list[str], check: bool = True, capture_output: bool = False, text: bool = True) -> subprocess.CompletedProcess:
    cmd = ["tmux", *args]
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=text)


def tmux_has_session(session: str) -> bool:
    return subprocess.run(["tmux", "has-session", "-t", session], capture_output=True).returncode == 0


def tmux_window_panes(window_target: str) -> list[dict[str, int | str]]:
    proc = tmux(
        [
            "list-panes",
            "-t",
            window_target,
            "-F",
            "#{pane_id}\t#{pane_width}\t#{pane_height}\t#{pane_left}\t#{pane_top}",
        ],
        capture_output=True,
    )
    panes: list[dict[str, int | str]] = []
    for line in proc.stdout.splitlines():
        pane_id, width, height, left, top = line.split("\t", 4)
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


def shell_attach_command(session: Any) -> str:
    session_name = shlex.quote(session.session)
    cwd = shlex.quote(session.workspace)
    return f"cd {cwd} && exec env -u TMUX tmux attach -t {session_name} || exec $SHELL -l"


def project_monitor_shell_command(project: Any) -> str:
    session = shlex.quote(project.monitor_session)
    cwd = shlex.quote(project.repo_root)
    return f"cd {cwd} && exec tmux attach -t {session} || exec $SHELL -l"


def build_monitor_layout(project: Any, sessions: dict[str, Any]) -> None:
    monitor = project.monitor_session
    if tmux_has_session(monitor):
        subprocess.run(["tmux", "kill-session", "-t", monitor], check=False)
    repo_root = project.repo_root
    visible_engineer_ids = project.monitor_engineers[: max(1, project.monitor_max_panes)]
    if not visible_engineer_ids:
        raise AgentAdminWindowError(f"{project.name} has no monitor engineers configured")
    subprocess.run(
        ["tmux", "new-session", "-d", "-x", "240", "-y", "80", "-s", monitor, "-c", repo_root],
        check=True,
    )
    first_target = f"{monitor}:0.0"
    first_engineer = sessions[visible_engineer_ids[0]]
    subprocess.run(
        ["tmux", "send-keys", "-t", first_target, monitor_attach_command(first_engineer.session), "C-m"],
        check=True,
    )

    if len(visible_engineer_ids) >= 2:
        second = sessions[visible_engineer_ids[1]]
        subprocess.run(
            [
                "tmux",
                "split-window",
                "-h",
                "-t",
                first_target,
                "-c",
                repo_root,
                monitor_attach_command(second.session),
            ],
            check=True,
        )

    panes = tmux_window_panes(f"{monitor}:0")
    if len(visible_engineer_ids) >= 3 and panes:
        leftmost = min(panes, key=lambda item: (int(item["left"]), int(item["top"])))
        leftmost_id = str(leftmost["pane_id"])
        third = sessions[visible_engineer_ids[2]]
        subprocess.run(
            [
                "tmux",
                "split-window",
                "-v",
                "-t",
                leftmost_id,
                "-c",
                repo_root,
                monitor_attach_command(third.session),
            ],
            check=True,
        )

    panes = tmux_window_panes(f"{monitor}:0")
    if len(visible_engineer_ids) >= 4 and panes:
        rightmost = max(panes, key=lambda item: (int(item["left"]), -int(item["top"])))
        rightmost_id = str(rightmost["pane_id"])
        fourth = sessions[visible_engineer_ids[3]]
        subprocess.run(
            [
                "tmux",
                "split-window",
                "-v",
                "-t",
                rightmost_id,
                "-c",
                repo_root,
                monitor_attach_command(fourth.session),
            ],
            check=True,
        )

    layout = "tiled"
    if project.window_mode == "tabs-1up":
        layout = "even-vertical"
    if len(visible_engineer_ids) == 4:
        layout = "tiled"
    subprocess.run(["tmux", "select-layout", "-t", f"{monitor}:0", layout], check=False)


def osascript(script: str) -> None:
    subprocess.run(["osascript", "-e", script], check=True)


def escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def display_name_for(engineer: Any | None, fallback: str) -> str:
    if engineer and getattr(engineer, "display_name", ""):
        return engineer.display_name
    return fallback


def iterm_run_command(command: str, title: str | None = None) -> None:
    escaped = escape_applescript(command)
    title_lines = ""
    if title:
        escaped_title = escape_applescript(title)
        title_lines = f'\n      set name to "{escaped_title}"'
    script = textwrap.dedent(
        f'''
        tell application "iTerm2"
          activate
          create window with default profile
          tell current session of current window
            {title_lines.strip()}
            write text "{escaped}"
          end tell
        end tell
        '''
    ).strip()
    try:
        osascript(script)
    except subprocess.CalledProcessError:
        fallback = textwrap.dedent(
            f'''
            tell application "iTerm"
              activate
              create window with default profile
              tell current session of current window
                {title_lines.strip()}
                write text "{escaped}"
              end tell
            end tell
            '''
        ).strip()
        osascript(fallback)


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

    def applescript_quote(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    lines = [
        'tell application "iTerm2"',
        "  activate",
        "  set existingWindow to missing value",
        "  repeat with w in windows",
        "    repeat with t in tabs of w",
        "      try",
        "        set tabName to name of current session of t",
        f'        if tabName starts with "{applescript_quote(project.name)}:" then',
        "          set existingWindow to w",
        "          exit repeat",
        "        end if",
        "      end try",
        "    end repeat",
        "    if existingWindow is not missing value then exit repeat",
        "  end repeat",
        "  if existingWindow is not missing value then close existingWindow",
        "  set projectWindow to (create window with default profile)",
    ]

    for tab_index, session in enumerate(resolved_sessions):
        if tab_index > 0:
            lines.append("  tell projectWindow")
            lines.append("    create tab with default profile")
            lines.append("  end tell")
        command = applescript_quote(shell_attach_command(session))
        engineer = engineers.get(session.engineer_id)
        title = applescript_quote(f"{project.name}:{display_name_for(engineer, session.engineer_id)}")
        lines.append("  tell current session of current tab of projectWindow")
        lines.append(f'    set name to "{title}"')
        lines.append(f'    write text "{command}"')
        lines.append("  end tell")

    lines.append("end tell")
    osascript("\n".join(lines))


def open_dashboard_window(projects: list[Any]) -> None:
    if not projects:
        raise AgentAdminWindowError("No projects configured")

    def applescript_quote(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    lines = [
        'tell application "iTerm2"',
        "  activate",
        "  set dashboardWindow to (create window with default profile)",
    ]

    for tab_index, project in enumerate(projects):
        if tab_index > 0:
            lines.append("  tell dashboardWindow")
            lines.append("    create tab with default profile")
            lines.append("  end tell")
        command = applescript_quote(project_monitor_shell_command(project))
        lines.append("  tell current session of current tab of dashboardWindow")
        lines.append(f'    write text "{command}"')
        lines.append("  end tell")

    lines.append("end tell")
    osascript("\n".join(lines))


def open_engineer_window(session: Any, engineer: Any | None) -> None:
    iterm_run_command(shell_attach_command(session), title=display_name_for(engineer, session.engineer_id))
