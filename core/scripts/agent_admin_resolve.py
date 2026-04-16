from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ResolveHooks:
    error_cls: type[Exception]
    default_tool_args: dict[str, list[str]]
    codex_api_provider_configs: dict[str, dict[str, Any]]
    common_env: Callable[[], dict[str, str]]
    ensure_dir: Callable[[Path], None]
    parse_env_file: Callable[[Path], dict[str, str]]
    write_codex_api_config: Callable[[Any, Path, Path, dict[str, dict[str, Any]], Any], None]
    write_text: Callable[[Path, str, int | None], None]
    load_project: Callable[[str], Any]
    load_projects: Callable[[], dict[str, Any]]
    load_engineers: Callable[[], dict[str, Any]]
    load_sessions: Callable[[], dict[tuple[str, str], Any]]
    get_current_project_name: Callable[[dict[str, Any] | None], str | None]
    display_name_for: Callable[[Any | None, str], str]


class ResolveHandlers:
    def __init__(self, hooks: ResolveHooks) -> None:
        self.hooks = hooks

    def build_runtime(self, session: Any) -> tuple[str, dict[str, str]]:
        runtime_dir = Path(session.runtime_dir)
        tool = session.tool
        mode = session.auth_mode
        binary = session.bin_path
        env = self.hooks.common_env()
        shared_agent_home = Path(os.environ.get("AGENT_HOME", str(Path.home()))).expanduser()

        home = runtime_dir / "home"
        xdg_config = runtime_dir / "xdg" / "config"
        xdg_data = runtime_dir / "xdg" / "data"
        xdg_cache = runtime_dir / "xdg" / "cache"
        xdg_state = runtime_dir / "xdg" / "state"
        for path in (home, xdg_config, xdg_data, xdg_cache, xdg_state):
            self.hooks.ensure_dir(path)
        env.update(
            {
                "AGENT_HOME": str(shared_agent_home),
                "AGENTS_ROOT": str(shared_agent_home / ".agents"),
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg_config),
                "XDG_DATA_HOME": str(xdg_data),
                "XDG_CACHE_HOME": str(xdg_cache),
                "XDG_STATE_HOME": str(xdg_state),
            }
        )

        codex_home = None
        if tool == "codex":
            codex_home = runtime_dir / "codex"
            self.hooks.ensure_dir(codex_home)
            self.hooks.ensure_dir(codex_home / "tmp")
            env["CODEX_HOME"] = str(codex_home)

        if mode == "api":
            if not session.secret_file:
                session_path = (
                    self.hooks.sessions_root
                    / session.project
                    / session.engineer_id
                    / "session.toml"
                )
                raise self.hooks.error_cls(
                    f"{session.engineer_id} is missing 'secret_file' in session.toml "
                    f"(auth_mode=api requires it). "
                    f"Edit {session_path} and add:\n"
                    f"  secret_file = \"/path/to/{session.engineer_id}.env\"\n"
                    f"Or run: agent-admin session switch-harness "
                    f"--engineer {session.engineer_id} "
                    f"--project {session.project} "
                    f"--tool {session.tool} --mode api --provider {session.provider}"
                )
            secret_env = self.hooks.parse_env_file(Path(session.secret_file))
            env.update(secret_env)
            if tool == "codex":
                api_key = secret_env.get("OPENAI_API_KEY", "")
                if not api_key:
                    raise self.hooks.error_cls(
                        f"{session.engineer_id} is missing OPENAI_API_KEY in {session.secret_file}"
                    )
                auth_path = codex_home / "auth.json"
                auth_path.write_text(json.dumps({"OPENAI_API_KEY": api_key}, ensure_ascii=True))
                auth_path.chmod(0o600)
                self.hooks.write_codex_api_config(
                    session,
                    codex_home,
                    Path(self.hooks.load_project(session.project).repo_root),
                    self.hooks.codex_api_provider_configs,
                    self.hooks.write_text,
                )
                env.pop("OPENAI_API_KEY", None)

        return binary, env

    def default_launch_args(self, session: Any) -> list[str]:
        return list(self.hooks.default_tool_args.get(session.tool, []))

    def resolve_engineer(self, name: str, engineers: dict[str, Any] | None = None) -> Any:
        engineer_map = engineers or self.hooks.load_engineers()
        if name in engineer_map:
            return engineer_map[name]
        for engineer in engineer_map.values():
            if name in engineer.aliases:
                return engineer
        raise self.hooks.error_cls(f"Unknown engineer: {name}")

    def resolve_engineer_session(
        self,
        engineer_name: str,
        project_name: str | None = None,
        sessions: dict[tuple[str, str], Any] | None = None,
        engineers: dict[str, Any] | None = None,
    ) -> Any:
        engineer = self.resolve_engineer(engineer_name, engineers)
        session_map = sessions or self.hooks.load_sessions()
        if project_name:
            key = (project_name, engineer.engineer_id)
            if key in session_map:
                return session_map[key]
            raise self.hooks.error_cls(f"{engineer.engineer_id} has no session in project {project_name}")

        current_project = self.hooks.get_current_project_name(self.hooks.load_projects())
        if current_project and (current_project, engineer.engineer_id) in session_map:
            return session_map[(current_project, engineer.engineer_id)]

        matches = [session for session in session_map.values() if session.engineer_id == engineer.engineer_id]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise self.hooks.error_cls(f"{engineer.engineer_id} has no session")
        raise self.hooks.error_cls(f"{engineer.engineer_id} exists in multiple projects; specify --project")

    def resolve_session(
        self,
        name: str,
        project_name: str | None = None,
        *,
        prefer_current_project: bool = True,
    ) -> str:
        engineers = self.hooks.load_engineers()
        sessions = self.hooks.load_sessions()
        engineer_error: Exception | None = None
        try:
            if project_name:
                session = self.resolve_engineer_session(
                    name,
                    project_name=project_name,
                    sessions=sessions,
                    engineers=engineers,
                )
            elif prefer_current_project:
                session = self.resolve_engineer_session(name, sessions=sessions, engineers=engineers)
            else:
                engineer = self.resolve_engineer(name, engineers)
                matches = [session for session in sessions.values() if session.engineer_id == engineer.engineer_id]
                if len(matches) == 1:
                    session = matches[0]
                elif not matches:
                    raise self.hooks.error_cls(f"{engineer.engineer_id} has no session")
                else:
                    raise self.hooks.error_cls(
                        f"{engineer.engineer_id} exists in multiple projects; specify --project"
                    )
            return session.session
        except self.hooks.error_cls as exc:
            engineer_error = exc
        for session in sessions.values():
            if name == session.session or name in session.legacy_sessions:
                return session.session
        projects = self.hooks.load_projects()
        if name in projects:
            return projects[name].monitor_session
        for project in projects.values():
            if name == project.monitor_session:
                return project.monitor_session
        if engineer_error is not None:
            raise engineer_error
        raise self.hooks.error_cls(f"Unknown session or engineer: {name}")

    def display_label(self, engineer: Any | None, fallback: str) -> str:
        display_name = self.hooks.display_name_for(engineer, fallback)
        if display_name == fallback:
            return fallback
        return f"{display_name} ({fallback})"
