from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class StoreHooks:
    error_cls: type[Exception]
    project_cls: type
    engineer_cls: type
    session_record_cls: type
    projects_root: Path
    engineers_root: Path
    sessions_root: Path
    workspaces_root: Path
    current_project_path: Path
    templates_root: Path
    tool_binaries: dict[str, str]
    normalize_name: Callable[[str], str]
    ensure_dir: Callable[[Path], None]
    write_text: Callable[[Path, str, int | None], None]
    load_toml: Callable[[Path], dict]
    q: Callable[[str], str]
    q_array: Callable[[list[str]], str]
    identity_name: Callable[..., str]
    runtime_dir_for_identity: Callable[..., Path]
    secret_file_for: Callable[..., Path]
    session_name_for: Callable[..., str]


class StoreHandlers:
    def __init__(self, hooks: StoreHooks) -> None:
        self.hooks = hooks

    def project_path(self, project: str) -> Path:
        return self.hooks.projects_root / project / "project.toml"

    def engineer_path(self, engineer_id: str) -> Path:
        return self.hooks.engineers_root / engineer_id / "engineer.toml"

    def session_path(self, project: str, engineer_id: str) -> Path:
        return self.hooks.sessions_root / project / engineer_id / "session.toml"

    def load_project(self, name: str) -> Any:
        data = self.hooks.load_toml(self.project_path(name))
        return self.hooks.project_cls(
            name=data["name"],
            repo_root=data["repo_root"],
            monitor_session=data["monitor_session"],
            engineers=list(data.get("engineers", [])),
            monitor_engineers=list(data.get("monitor_engineers", [])),
            template_name=str(data.get("template_name", "")),
            seat_overrides={
                str(seat_id): dict(values)
                for seat_id, values in data.get("seat_overrides", {}).items()
            },
            window_mode=data.get("window_mode", "project-monitor"),
            monitor_max_panes=int(data.get("monitor_max_panes", 4)),
            open_detail_windows=bool(data.get("open_detail_windows", False)),
        )

    def load_projects(self) -> dict[str, Any]:
        projects: dict[str, Any] = {}
        if not self.hooks.projects_root.exists():
            return projects
        for path in sorted(self.hooks.projects_root.glob("*/project.toml")):
            project = self.load_project(path.parent.name)
            projects[project.name] = project
        return projects

    def get_current_project_name(self, projects: dict[str, Any] | None = None) -> str | None:
        project_map = projects or self.load_projects()
        if self.hooks.current_project_path.exists():
            value = self.hooks.current_project_path.read_text().strip()
            if value in project_map:
                return value
        if project_map:
            return sorted(project_map)[0]
        return None

    def set_current_project(self, name: str) -> None:
        self.hooks.ensure_dir(self.hooks.current_project_path.parent)
        self.hooks.write_text(self.hooks.current_project_path, f"{name}\n", None)

    def load_project_or_current(self, name: str | None) -> Any:
        projects = self.load_projects()
        project_name = name or self.get_current_project_name(projects)
        if not project_name:
            raise self.hooks.error_cls("No project configured")
        if project_name not in projects:
            raise self.hooks.error_cls(f"Unknown project: {project_name}")
        return projects[project_name]

    def load_engineer(self, engineer_id: str) -> Any:
        data = self.hooks.load_toml(self.engineer_path(engineer_id))
        return self.hooks.engineer_cls(
            engineer_id=data["id"],
            display_name=data.get("display_name", data["id"]),
            aliases=list(data.get("aliases", [])),
            role=data.get("role", ""),
            role_details=list(data.get("role_details", [])),
            skills=list(data.get("skills", [])),
            human_facing=bool(data.get("human_facing", False)),
            active_loop_owner=bool(data.get("active_loop_owner", False)),
            dispatch_authority=bool(data.get("dispatch_authority", False)),
            patrol_authority=bool(data.get("patrol_authority", False)),
            unblock_authority=bool(data.get("unblock_authority", False)),
            escalation_authority=bool(data.get("escalation_authority", False)),
            remind_active_loop_owner=bool(data.get("remind_active_loop_owner", False)),
            review_authority=bool(data.get("review_authority", False)),
            qa_authority=bool(data.get("qa_authority", False)),
            design_authority=bool(data.get("design_authority", False)),
            default_tool=data.get("default_tool", data.get("tool", "")),
            default_auth_mode=data.get("default_auth_mode", data.get("auth_mode", "")),
            default_provider=data.get("default_provider", data.get("provider", "")),
        )

    def load_engineers(self) -> dict[str, Any]:
        engineers: dict[str, Any] = {}
        if not self.hooks.engineers_root.exists():
            return engineers
        for path in sorted(self.hooks.engineers_root.glob("*/engineer.toml")):
            engineer = self.load_engineer(path.parent.name)
            engineers[engineer.engineer_id] = engineer
        return engineers

    def load_session(self, project: str, engineer_id: str) -> Any:
        data = self.hooks.load_toml(self.session_path(project, engineer_id))
        return self.hooks.session_record_cls(
            engineer_id=data["engineer_id"],
            project=data["project"],
            tool=data["tool"],
            auth_mode=data["auth_mode"],
            provider=data["provider"],
            identity=data["identity"],
            workspace=data["workspace"],
            runtime_dir=data["runtime_dir"],
            session=data["session"],
            bin_path=data.get("bin_path", self.hooks.tool_binaries[data["tool"]]),
            monitor=bool(data.get("monitor", True)),
            legacy_sessions=list(data.get("legacy_sessions", [])),
            launch_args=list(data.get("launch_args", [])),
            secret_file=data.get("secret_file", ""),
            wrapper=data.get("wrapper", ""),
        )

    def load_sessions(self) -> dict[tuple[str, str], Any]:
        sessions: dict[tuple[str, str], Any] = {}
        if not self.hooks.sessions_root.exists():
            return sessions
        for path in sorted(self.hooks.sessions_root.glob("*/*/session.toml")):
            session = self.load_session(path.parent.parent.name, path.parent.name)
            sessions[(session.project, session.engineer_id)] = session
        return sessions

    def load_project_sessions(self, project: str) -> dict[str, Any]:
        return {
            engineer_id: session
            for (project_name, engineer_id), session in self.load_sessions().items()
            if project_name == project
        }

    def load_template(self, name_or_path: str) -> dict:
        candidate = Path(name_or_path).expanduser()
        if candidate.exists():
            if candidate.is_dir():
                candidate = candidate / "template.toml"
        else:
            candidate = self.hooks.templates_root / name_or_path / "template.toml"
        if not candidate.exists():
            raise self.hooks.error_cls(f"Template not found: {name_or_path}")
        data = self.hooks.load_toml(candidate)
        if not isinstance(data.get("engineers"), list):
            raise self.hooks.error_cls(f"Template {candidate} is missing [[engineers]] entries")
        return data

    def merge_template_local(self, template: dict, local: dict) -> dict:
        project_name_raw = str(local.get("project_name", "")).strip()
        repo_root_raw = str(local.get("repo_root", "")).strip()
        if not project_name_raw:
            raise self.hooks.error_cls("local.toml is missing required field: project_name")
        if not repo_root_raw:
            raise self.hooks.error_cls("local.toml is missing required field: repo_root")

        project_name = self.hooks.normalize_name(project_name_raw)
        repo_root = str(Path(repo_root_raw).expanduser())
        defaults = dict(template.get("defaults", {}))

        template_engineers: list[dict] = []
        seen_ids: set[str] = set()
        for engineer in template.get("engineers", []):
            engineer_id = self.hooks.normalize_name(str(engineer.get("id", "")))
            if engineer_id in seen_ids:
                raise self.hooks.error_cls(f"Template declares duplicate engineer id: {engineer_id}")
            seen_ids.add(engineer_id)
            merged_engineer = dict(engineer)
            merged_engineer["id"] = engineer_id
            template_engineers.append(merged_engineer)

        override_map: dict[str, dict] = {}
        for override in local.get("overrides", []):
            engineer_id = self.hooks.normalize_name(str(override.get("id", "")))
            if engineer_id not in seen_ids:
                raise self.hooks.error_cls(f"Override references unknown engineer id: {engineer_id}")
            if engineer_id in override_map:
                raise self.hooks.error_cls(f"Duplicate override for engineer id: {engineer_id}")
            override_map[engineer_id] = dict(override)

        final_engineers: list[dict] = []
        for engineer in template_engineers:
            engineer_id = engineer["id"]
            merged_engineer = dict(engineer)
            override = override_map.get(engineer_id)
            if override:
                merged_engineer.update(override)
                merged_engineer["id"] = engineer_id
            if merged_engineer.get("active", True) is False:
                continue
            final_engineers.append(merged_engineer)

        seat_order_raw = [
            self.hooks.normalize_name(str(item))
            for item in local.get("seat_order", [])
            if str(item).strip()
        ]
        bootstrap_seats_raw = [
            self.hooks.normalize_name(str(item))
            for item in local.get("bootstrap_seats", [])
            if str(item).strip()
        ]
        if bootstrap_seats_raw:
            final_ids = {str(engineer["id"]) for engineer in final_engineers}
            unknown = [seat_id for seat_id in bootstrap_seats_raw if seat_id not in final_ids]
            if unknown:
                raise self.hooks.error_cls(
                    f"bootstrap_seats references unknown/disabled engineer ids: {', '.join(unknown)}"
                )
            bootstrap_set = set(bootstrap_seats_raw)
            final_engineers = [
                engineer
                for engineer in final_engineers
                if str(engineer["id"]) in bootstrap_set
            ]
        if seat_order_raw:
            final_ids = {str(engineer["id"]) for engineer in final_engineers}
            unknown = [seat_id for seat_id in seat_order_raw if seat_id not in final_ids]
            if unknown:
                raise self.hooks.error_cls(
                    f"seat_order references unknown/disabled engineer ids: {', '.join(unknown)}"
                )
            order_index = {seat_id: index for index, seat_id in enumerate(seat_order_raw)}
            final_engineers.sort(
                key=lambda engineer: (
                    order_index.get(str(engineer["id"]), len(order_index)),
                    str(engineer["id"]),
                )
            )

        return {
            "project_name": project_name,
            "repo_root": repo_root,
            "window_mode": defaults.get("window_mode", "tabs-1up"),
            "monitor_max_panes": int(defaults.get("monitor_max_panes", 4)),
            "open_detail_windows": bool(defaults.get("open_detail_windows", False)),
            "engineers": final_engineers,
            "optional_skills": list(template.get("optional_skills", [])),
        }

    def write_project(self, project: Any) -> None:
        path = self.project_path(project.name)
        self.hooks.ensure_dir(path.parent)
        lines = [
            "version = 1",
            f"name = {self.hooks.q(project.name)}",
            f"repo_root = {self.hooks.q(project.repo_root)}",
            f"monitor_session = {self.hooks.q(project.monitor_session)}",
        ]
        if project.template_name:
            lines.append(f"template_name = {self.hooks.q(project.template_name)}")
        lines.extend(
            [
                f"window_mode = {self.hooks.q(project.window_mode)}",
                f"monitor_max_panes = {project.monitor_max_panes}",
                f"open_detail_windows = {'true' if project.open_detail_windows else 'false'}",
                f"engineers = {self.hooks.q_array(project.engineers)}",
                f"monitor_engineers = {self.hooks.q_array(project.monitor_engineers)}",
            ]
        )
        for seat_id, override in sorted((project.seat_overrides or {}).items()):
            if not override:
                continue
            lines.extend(["", f"[seat_overrides.{seat_id}]"])
            for key, value in override.items():
                if isinstance(value, bool):
                    rendered = "true" if value else "false"
                elif isinstance(value, int):
                    rendered = str(value)
                elif isinstance(value, list):
                    rendered = self.hooks.q_array([str(item) for item in value])
                else:
                    rendered = self.hooks.q(str(value))
                lines.append(f"{key} = {rendered}")
        lines.append("")
        self.hooks.write_text(path, "\n".join(lines), None)

    def write_engineer(self, engineer: Any) -> None:
        path = self.engineer_path(engineer.engineer_id)
        self.hooks.ensure_dir(path.parent)
        lines = [
            "version = 1",
            f"id = {self.hooks.q(engineer.engineer_id)}",
            f"display_name = {self.hooks.q(engineer.display_name)}",
            f"aliases = {self.hooks.q_array(engineer.aliases)}",
            f"role = {self.hooks.q(engineer.role)}",
        ]
        if engineer.role_details:
            lines.append(f"role_details = {self.hooks.q_array(engineer.role_details)}")
        lines.extend(
            [
                f"skills = {self.hooks.q_array(engineer.skills)}",
                f"human_facing = {'true' if engineer.human_facing else 'false'}",
                f"active_loop_owner = {'true' if engineer.active_loop_owner else 'false'}",
                f"dispatch_authority = {'true' if engineer.dispatch_authority else 'false'}",
                f"patrol_authority = {'true' if engineer.patrol_authority else 'false'}",
                f"unblock_authority = {'true' if engineer.unblock_authority else 'false'}",
                f"escalation_authority = {'true' if engineer.escalation_authority else 'false'}",
                f"remind_active_loop_owner = {'true' if engineer.remind_active_loop_owner else 'false'}",
                f"review_authority = {'true' if engineer.review_authority else 'false'}",
                f"qa_authority = {'true' if engineer.qa_authority else 'false'}",
                f"design_authority = {'true' if engineer.design_authority else 'false'}",
                f"default_tool = {self.hooks.q(engineer.default_tool)}",
                f"default_auth_mode = {self.hooks.q(engineer.default_auth_mode)}",
                f"default_provider = {self.hooks.q(engineer.default_provider)}",
            ]
        )
        lines.append("")
        self.hooks.write_text(path, "\n".join(lines), None)

    def write_session(self, session: Any) -> None:
        path = self.session_path(session.project, session.engineer_id)
        self.hooks.ensure_dir(path.parent)
        lines = [
            "version = 1",
            f"project = {self.hooks.q(session.project)}",
            f"engineer_id = {self.hooks.q(session.engineer_id)}",
            f"tool = {self.hooks.q(session.tool)}",
            f"auth_mode = {self.hooks.q(session.auth_mode)}",
            f"provider = {self.hooks.q(session.provider)}",
            f"identity = {self.hooks.q(session.identity)}",
            f"workspace = {self.hooks.q(session.workspace)}",
            f"runtime_dir = {self.hooks.q(session.runtime_dir)}",
            f"session = {self.hooks.q(session.session)}",
            f"bin_path = {self.hooks.q(session.bin_path)}",
            f"monitor = {'true' if session.monitor else 'false'}",
            f"legacy_sessions = {self.hooks.q_array(session.legacy_sessions)}",
            f"launch_args = {self.hooks.q_array(session.launch_args)}",
        ]
        if session.secret_file:
            lines.append(f"secret_file = {self.hooks.q(session.secret_file)}")
        if session.wrapper:
            lines.append(f"wrapper = {self.hooks.q(session.wrapper)}")
        lines.append("")
        self.hooks.write_text(path, "\n".join(lines), None)

    def create_engineer_profile(
        self,
        engineer_id: str,
        tool: str,
        auth_mode: str,
        provider: str,
        role: str = "",
        display_name: str = "",
        role_details: list[str] | None = None,
        skills: list[str] | None = None,
        aliases: list[str] | None = None,
        human_facing: bool = False,
        active_loop_owner: bool = False,
        dispatch_authority: bool = False,
        patrol_authority: bool = False,
        unblock_authority: bool = False,
        escalation_authority: bool = False,
        remind_active_loop_owner: bool = False,
        review_authority: bool = False,
        qa_authority: bool = False,
        design_authority: bool = False,
    ) -> Any:
        engineer_id = self.hooks.normalize_name(engineer_id)
        return self.hooks.engineer_cls(
            engineer_id=engineer_id,
            display_name=display_name or engineer_id,
            aliases=list(aliases or []),
            role=role or engineer_id,
            role_details=list(role_details or []),
            skills=list(skills or []),
            human_facing=human_facing,
            active_loop_owner=active_loop_owner,
            dispatch_authority=dispatch_authority,
            patrol_authority=patrol_authority,
            unblock_authority=unblock_authority,
            escalation_authority=escalation_authority,
            remind_active_loop_owner=remind_active_loop_owner,
            review_authority=review_authority,
            qa_authority=qa_authority,
            design_authority=design_authority,
            default_tool=tool,
            default_auth_mode=auth_mode,
            default_provider=provider,
        )

    def merge_engineer_profile_with_template(self, profile: Any, engineer_spec: dict) -> Any:
        role = str(engineer_spec.get("role", profile.role)).strip()
        display_name = str(engineer_spec.get("display_name", profile.display_name)).strip() or profile.display_name
        aliases = list(engineer_spec.get("aliases", profile.aliases))
        role_details = list(engineer_spec.get("role_details", profile.role_details))
        skills = list(engineer_spec.get("skills", profile.skills))
        default_tool = str(engineer_spec.get("tool", profile.default_tool)).strip() or profile.default_tool
        default_auth_mode = (
            str(engineer_spec.get("auth_mode", profile.default_auth_mode)).strip()
            or profile.default_auth_mode
        )
        default_provider = (
            str(engineer_spec.get("provider", profile.default_provider)).strip()
            or profile.default_provider
        )
        return self.hooks.engineer_cls(
            engineer_id=profile.engineer_id,
            display_name=display_name,
            aliases=aliases,
            role=role,
            role_details=role_details,
            skills=skills,
            human_facing=bool(engineer_spec.get("human_facing", profile.human_facing)),
            active_loop_owner=bool(engineer_spec.get("active_loop_owner", profile.active_loop_owner)),
            dispatch_authority=bool(engineer_spec.get("dispatch_authority", profile.dispatch_authority)),
            patrol_authority=bool(engineer_spec.get("patrol_authority", profile.patrol_authority)),
            unblock_authority=bool(engineer_spec.get("unblock_authority", profile.unblock_authority)),
            escalation_authority=bool(engineer_spec.get("escalation_authority", profile.escalation_authority)),
            remind_active_loop_owner=bool(
                engineer_spec.get("remind_active_loop_owner", profile.remind_active_loop_owner)
            ),
            review_authority=bool(engineer_spec.get("review_authority", profile.review_authority)),
            qa_authority=bool(engineer_spec.get("qa_authority", profile.qa_authority)),
            design_authority=bool(engineer_spec.get("design_authority", profile.design_authority)),
            default_tool=default_tool,
            default_auth_mode=default_auth_mode,
            default_provider=default_provider,
        )

    def create_session_record(
        self,
        engineer_id: str,
        project: Any,
        tool: str,
        auth_mode: str,
        provider: str,
        monitor: bool = True,
        legacy_session: str = "",
        launch_args: list[str] | None = None,
        wrapper: str = "",
    ) -> Any:
        engineer_id = self.hooks.normalize_name(engineer_id)
        identity = self.hooks.identity_name(tool, auth_mode, provider, engineer_id, project.name)
        workspace = self.hooks.workspaces_root / project.name / engineer_id
        runtime_dir = self.hooks.runtime_dir_for_identity(tool, auth_mode, identity)
        secret_file = ""
        if auth_mode == "api":
            secret_file = str(self.hooks.secret_file_for(tool, provider, engineer_id))
        return self.hooks.session_record_cls(
            engineer_id=engineer_id,
            project=project.name,
            tool=tool,
            auth_mode=auth_mode,
            provider=provider,
            identity=identity,
            workspace=str(workspace),
            runtime_dir=str(runtime_dir),
            session=self.hooks.session_name_for(project.name, engineer_id, tool),
            bin_path=self.hooks.tool_binaries[tool],
            monitor=monitor,
            legacy_sessions=[legacy_session] if legacy_session else [],
            launch_args=list(launch_args or []),
            secret_file=secret_file,
            wrapper=wrapper,
        )

    def project_template_context(
        self,
        project: Any,
    ) -> tuple[dict[str, Any], list[str], list[dict[str, object]]] | None:
        if not project.template_name:
            return None
        try:
            template = self.load_template(project.template_name)
        except self.hooks.error_cls:
            return None
        merged = self.merge_template_local(
            template,
            {
                "project_name": project.name,
                "repo_root": project.repo_root,
                "overrides": [
                    {"id": seat_id, **dict(values)}
                    for seat_id, values in (project.seat_overrides or {}).items()
                ],
            },
        )
        template_profiles: dict[str, Any] = {}
        engineer_order: list[str] = []
        for engineer_spec in merged["engineers"]:
            engineer_id = self.hooks.normalize_name(str(engineer_spec["id"]))
            engineer_order.append(engineer_id)
            if self.engineer_path(engineer_id).exists():
                base_profile = self.load_engineer(engineer_id)
            else:
                role = str(engineer_spec.get("role", "")).strip()
                base_profile = self.create_engineer_profile(
                    engineer_id=engineer_id,
                    tool=str(engineer_spec["tool"]),
                    auth_mode=str(engineer_spec["auth_mode"]),
                    provider=str(engineer_spec["provider"]),
                    role=role,
                    display_name=str(engineer_spec.get("display_name", "")).strip() or role or engineer_id,
                    role_details=list(engineer_spec.get("role_details", [])),
                    skills=list(engineer_spec.get("skills", [])),
                    aliases=list(engineer_spec.get("aliases", [])),
                    human_facing=bool(engineer_spec.get("human_facing", False)),
                    active_loop_owner=bool(engineer_spec.get("active_loop_owner", False)),
                    dispatch_authority=bool(engineer_spec.get("dispatch_authority", False)),
                    patrol_authority=bool(engineer_spec.get("patrol_authority", False)),
                    unblock_authority=bool(engineer_spec.get("unblock_authority", False)),
                    escalation_authority=bool(engineer_spec.get("escalation_authority", False)),
                    remind_active_loop_owner=bool(engineer_spec.get("remind_active_loop_owner", False)),
                    review_authority=bool(engineer_spec.get("review_authority", False)),
                    qa_authority=bool(engineer_spec.get("qa_authority", False)),
                    design_authority=bool(engineer_spec.get("design_authority", False)),
                )
            template_profiles[engineer_id] = self.merge_engineer_profile_with_template(
                base_profile,
                engineer_spec,
            )
        return template_profiles, engineer_order, list(merged.get("optional_skills", []))
