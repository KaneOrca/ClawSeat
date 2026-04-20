from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ParserHooks:
    migrate_legacy: Callable[[Any], int]
    cmd_list_projects: Callable[[Any], int]
    cmd_list_engineers: Callable[[Any], int]
    cmd_list_identities: Callable[[Any], int]
    cmd_show_project: Callable[[Any], int]
    cmd_show_engineer: Callable[[Any], int]
    cmd_show: Callable[[Any], int]
    cmd_resolve: Callable[[Any], int]
    cmd_show_identity: Callable[[Any], int]
    cmd_run_engineer: Callable[[Any], int]
    cmd_start: Callable[[Any], int]
    cmd_start_identity: Callable[[Any], int]
    cmd_session_name: Callable[[Any], int]
    cmd_project_open: Callable[[Any], int]
    cmd_project_current: Callable[[Any], int]
    cmd_project_use: Callable[[Any], int]
    cmd_project_create: Callable[[Any], int]
    cmd_project_bootstrap: Callable[[Any], int]
    cmd_project_delete: Callable[[Any], int]
    cmd_project_layout_set: Callable[[Any], int]
    cmd_session_start_engineer: Callable[[Any], int]
    cmd_session_provision_heartbeat: Callable[[Any], int]
    cmd_session_stop_engineer: Callable[[Any], int]
    cmd_session_start_project: Callable[[Any], int]
    cmd_session_status: Callable[[Any], int]
    cmd_session_effective_launch: Callable[[Any], int]
    cmd_session_switch_harness: Callable[[Any], int]
    cmd_session_switch_auth: Callable[[Any], int]
    cmd_window_open_monitor: Callable[[Any], int]
    cmd_window_open_dashboard: Callable[[Any], int]
    cmd_window_open_engineer: Callable[[Any], int]
    cmd_window_config_monitor: Callable[[Any], int]
    cmd_engineer_create: Callable[[Any], int]
    cmd_engineer_delete: Callable[[Any], int]
    cmd_engineer_rename: Callable[[Any], int]
    cmd_engineer_rebind: Callable[[Any], int]
    cmd_engineer_secret_set: Callable[[Any], int]
    cmd_tui: Callable[[Any], int]


def build_parser(hooks: ParserHooks) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-admin")
    sub = parser.add_subparsers(dest="command", required=True)

    migrate = sub.add_parser("migrate-legacy")
    migrate.add_argument("--force", action="store_true")
    migrate.set_defaults(func=hooks.migrate_legacy)

    list_projects = sub.add_parser("list-projects")
    list_projects.set_defaults(func=hooks.cmd_list_projects)

    list_engineers = sub.add_parser("list-engineers")
    list_engineers.set_defaults(func=hooks.cmd_list_engineers)

    list_identities = sub.add_parser("list-identities")
    list_identities.set_defaults(func=hooks.cmd_list_identities)

    show_project = sub.add_parser("show-project")
    show_project.add_argument("project")
    show_project.set_defaults(func=hooks.cmd_show_project)

    show_engineer = sub.add_parser("show-engineer")
    show_engineer.add_argument("engineer")
    show_engineer.add_argument("--project")
    show_engineer.set_defaults(func=hooks.cmd_show_engineer)

    show = sub.add_parser("show")
    show.add_argument("engineer")
    show.add_argument("--project")
    show.set_defaults(func=hooks.cmd_show)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("engineer")
    resolve.add_argument("tool", choices=["codex", "claude", "gemini"])
    resolve.add_argument("--project")
    resolve.set_defaults(func=hooks.cmd_resolve)

    show_identity = sub.add_parser("show-identity")
    show_identity.add_argument("identity")
    show_identity.set_defaults(func=hooks.cmd_show_identity)

    run_engineer = sub.add_parser("run-engineer")
    run_engineer.add_argument("engineer")
    run_engineer.add_argument("--project")
    run_engineer.add_argument("cmd", nargs="*")
    run_engineer.set_defaults(func=hooks.cmd_run_engineer)

    start = sub.add_parser("start")
    start.add_argument("engineer")
    start.add_argument("tool", choices=["codex", "claude", "gemini"])
    start.add_argument("--project")
    start.add_argument("cmd", nargs="*")
    start.set_defaults(func=hooks.cmd_start)

    start_identity = sub.add_parser("start-identity")
    start_identity.add_argument("identity")
    start_identity.add_argument("cmd", nargs=argparse.REMAINDER)
    start_identity.set_defaults(func=hooks.cmd_start_identity)

    session_name = sub.add_parser("session-name")
    session_name.add_argument("target")
    session_name.add_argument("--project")
    session_name.set_defaults(func=hooks.cmd_session_name)

    project_open = sub.add_parser("project-open")
    project_open.add_argument("project")
    project_open.set_defaults(func=hooks.cmd_project_open)

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)

    project_list_nested = project_sub.add_parser("list")
    project_list_nested.set_defaults(func=hooks.cmd_list_projects)

    project_current_nested = project_sub.add_parser("current")
    project_current_nested.set_defaults(func=hooks.cmd_project_current)

    project_use_nested = project_sub.add_parser("use")
    project_use_nested.add_argument("project")
    project_use_nested.set_defaults(func=hooks.cmd_project_use)

    project_show_nested = project_sub.add_parser("show")
    project_show_nested.add_argument("project", nargs="?")
    project_show_nested.set_defaults(func=hooks.cmd_show_project)

    project_open_nested = project_sub.add_parser("open")
    project_open_nested.add_argument("project")
    project_open_nested.set_defaults(func=hooks.cmd_project_open)

    project_create_nested = project_sub.add_parser("create")
    project_create_nested.add_argument("project")
    project_create_nested.add_argument("repo_root")
    project_create_nested.add_argument("--window-mode", choices=["tabs-1up", "tabs-2up"], default="tabs-1up")
    project_create_nested.add_argument("--open-detail-windows", action="store_true")
    project_create_nested.set_defaults(func=hooks.cmd_project_create)

    project_bootstrap_nested = project_sub.add_parser("bootstrap")
    project_bootstrap_nested.add_argument("--template", required=True)
    project_bootstrap_nested.add_argument(
        "--local",
        required=True,
        help="Path to a local TOML override file containing project_name/repo_root overrides",
    )
    project_bootstrap_nested.add_argument("--start", action="store_true")
    project_bootstrap_nested.set_defaults(func=hooks.cmd_project_bootstrap)

    project_delete_nested = project_sub.add_parser("delete")
    project_delete_nested.add_argument("project")
    project_delete_nested.set_defaults(func=hooks.cmd_project_delete)

    project_layout_nested = project_sub.add_parser("layout")
    project_layout_nested.add_argument("project", nargs="?")
    project_layout_nested.add_argument("--window-mode", choices=["tabs-1up", "tabs-2up", "project-monitor"])
    project_layout_nested.add_argument("--monitor-max-panes", type=int)
    project_layout_nested.add_argument("--monitor-engineers")
    project_layout_nested.add_argument("--open-detail-windows", choices=["true", "false"])
    project_layout_nested.set_defaults(func=hooks.cmd_project_layout_set)

    session = sub.add_parser("session")
    session_sub = session.add_subparsers(dest="session_command", required=True)

    session_start_eng = session_sub.add_parser("start-engineer")
    session_start_eng.add_argument("engineer")
    session_start_eng.add_argument("--project")
    session_start_eng.add_argument("--reset", action="store_true")
    session_start_eng.set_defaults(func=hooks.cmd_session_start_engineer)

    session_provision_heartbeat = session_sub.add_parser("provision-heartbeat")
    session_provision_heartbeat.add_argument("engineer")
    session_provision_heartbeat.add_argument("--project")
    session_provision_heartbeat.add_argument("--force", action="store_true")
    session_provision_heartbeat.add_argument("--dry-run", action="store_true")
    session_provision_heartbeat.set_defaults(func=hooks.cmd_session_provision_heartbeat)

    session_stop_eng = session_sub.add_parser("stop-engineer")
    session_stop_eng.add_argument("engineer")
    session_stop_eng.add_argument("--project")
    session_stop_eng.set_defaults(func=hooks.cmd_session_stop_engineer)

    session_start_project = session_sub.add_parser("start-project")
    session_start_project.add_argument("project", nargs="?")
    session_start_project.add_argument("--reset", action="store_true")
    session_start_project.add_argument("--no-monitor", action="store_true")
    session_start_project.set_defaults(func=hooks.cmd_session_start_project)

    session_status_parser = session_sub.add_parser("status")
    session_status_parser.add_argument("engineer", nargs="?")
    session_status_parser.add_argument("--project")
    session_status_parser.set_defaults(func=hooks.cmd_session_status)

    session_effective_launch = session_sub.add_parser("effective-launch")
    session_effective_launch.add_argument("engineer")
    session_effective_launch.add_argument("--project")
    session_effective_launch.add_argument("cmd", nargs="*")
    session_effective_launch.set_defaults(func=hooks.cmd_session_effective_launch)

    switch_harness = session_sub.add_parser("switch-harness")
    switch_harness.add_argument("--project", required=True)
    switch_harness.add_argument("--engineer", required=True)
    switch_harness.add_argument("--tool", required=True, choices=["codex", "claude", "gemini"])
    switch_harness.add_argument("--mode", required=True, choices=["oauth", "api"])
    switch_harness.add_argument("--provider", required=True)
    switch_harness.set_defaults(func=hooks.cmd_session_switch_harness)

    switch_auth = session_sub.add_parser("switch-auth")
    switch_auth.add_argument("--project", required=True)
    switch_auth.add_argument("--engineer", required=True)
    switch_auth.add_argument("--mode", required=True, choices=["oauth", "api"])
    switch_auth.add_argument("--provider", required=True)
    switch_auth.set_defaults(func=hooks.cmd_session_switch_auth)

    window = sub.add_parser("window")
    window_sub = window.add_subparsers(dest="window_command", required=True)

    open_monitor = window_sub.add_parser("open-monitor")
    open_monitor.add_argument("project", nargs="?")
    open_monitor.set_defaults(func=hooks.cmd_window_open_monitor)

    open_dashboard = window_sub.add_parser("open-dashboard")
    open_dashboard.set_defaults(func=hooks.cmd_window_open_dashboard)

    open_engineer = window_sub.add_parser("open-engineer")
    open_engineer.add_argument("engineer")
    open_engineer.add_argument("--project")
    open_engineer.set_defaults(func=hooks.cmd_window_open_engineer)

    config_monitor = window_sub.add_parser("config-monitor")
    config_monitor.add_argument("project", nargs="?")
    config_monitor.add_argument("engineers")
    config_monitor.set_defaults(func=hooks.cmd_window_config_monitor)

    engineer = sub.add_parser("engineer")
    engineer_sub = engineer.add_subparsers(dest="engineer_command", required=True)

    engineer_list_nested = engineer_sub.add_parser("list")
    engineer_list_nested.set_defaults(func=hooks.cmd_list_engineers)

    engineer_show_nested = engineer_sub.add_parser("show")
    engineer_show_nested.add_argument("engineer")
    engineer_show_nested.add_argument("--project")
    engineer_show_nested.set_defaults(func=hooks.cmd_show_engineer)

    create = engineer_sub.add_parser("create")
    create.add_argument("engineer")
    create.add_argument("project")
    create.add_argument("tool", choices=["codex", "claude", "gemini"])
    create.add_argument("mode", choices=["oauth", "api"])
    create.add_argument("provider")
    create.add_argument("--no-monitor", action="store_true")
    create.set_defaults(func=hooks.cmd_engineer_create)

    delete = engineer_sub.add_parser("delete")
    delete.add_argument("engineer")
    delete.add_argument("--project")
    delete.set_defaults(func=hooks.cmd_engineer_delete)

    rename = engineer_sub.add_parser("rename")
    rename.add_argument("old")
    rename.add_argument("new")
    rename.set_defaults(func=hooks.cmd_engineer_rename)

    rebind = engineer_sub.add_parser("rebind")
    rebind.add_argument("engineer")
    rebind.add_argument("--project")
    rebind.add_argument("mode", choices=["oauth", "api"])
    rebind.add_argument("provider")
    rebind.set_defaults(func=hooks.cmd_engineer_rebind)

    secret = engineer_sub.add_parser("secret-set")
    secret.add_argument("engineer")
    secret.add_argument("--project")
    secret.add_argument("key")
    secret.add_argument("value")
    secret.set_defaults(func=hooks.cmd_engineer_secret_set)

    identity = sub.add_parser("identity")
    identity_sub = identity.add_subparsers(dest="identity_command", required=True)

    identity_list_nested = identity_sub.add_parser("list")
    identity_list_nested.set_defaults(func=hooks.cmd_list_identities)

    identity_show_nested = identity_sub.add_parser("show")
    identity_show_nested.add_argument("identity")
    identity_show_nested.set_defaults(func=hooks.cmd_show_identity)

    tui = sub.add_parser("tui")
    tui.set_defaults(func=hooks.cmd_tui)

    return parser
