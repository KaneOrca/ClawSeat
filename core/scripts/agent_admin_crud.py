from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent_admin_config import validate_runtime_combo


@dataclass
class CrudHooks:
    error_cls: type[Exception]
    project_cls: type
    engineer_cls: type
    session_record_cls: type
    sessions_root: Path
    workspaces_root: Path
    current_project_path: Path
    normalize_name: Callable[[str], str]
    project_path: Callable[[str], Path]
    engineer_path: Callable[[str], Path]
    session_path: Callable[[str, str], Path]
    load_project: Callable[[str], Any]
    load_projects: Callable[[], dict[str, Any]]
    load_project_or_current: Callable[[str | None], Any]
    load_engineer: Callable[[str], Any]
    load_sessions: Callable[[], dict[tuple[str, str], Any]]
    load_template: Callable[[str], dict]
    load_toml: Callable[[Path], dict]
    merge_template_local: Callable[[dict, dict], dict]
    write_project: Callable[[Any], None]
    write_engineer: Callable[[Any], None]
    write_session: Callable[[Any], None]
    set_current_project: Callable[[str], None]
    get_current_project_name: Callable[..., str | None]
    show_project: Callable[[Any], int]
    resolve_engineer: Callable[[str], Any]
    resolve_engineer_session: Callable[..., Any]
    create_engineer_profile: Callable[..., Any]
    merge_engineer_profile_with_template: Callable[[Any, dict], Any]
    create_session_record: Callable[..., Any]
    apply_template: Callable[[Any, Any], None]
    ensure_empty_env_file: Callable[..., None]
    ensure_dir: Callable[[Path], None]
    write_text: Callable[..., None]
    write_env_file: Callable[..., None]
    parse_env_file: Callable[[Path], dict[str, str]]
    archive_if_exists: Callable[[Path, str], None]
    identity_name: Callable[..., str]
    runtime_dir_for_identity: Callable[..., Path]
    secret_file_for: Callable[..., Path]
    session_name_for: Callable[..., str]
    ensure_secret_permissions: Callable[[Path], None]
    session_service: Any
    tmux_has_session: Callable[[str], bool]


class CrudHandlers:
    def __init__(self, hooks: CrudHooks) -> None:
        self.hooks = hooks

    def project_open(self, args: Any) -> int:
        return self.hooks.show_project(args)

    def project_create(self, args: Any) -> int:
        project_name = self.hooks.normalize_name(args.project)
        path = self.hooks.project_path(project_name)
        if path.exists():
            raise self.hooks.error_cls(f"{project_name} already exists")
        repo_root_value = (args.repo_root or "").strip()
        repo_root = str(Path(repo_root_value or os.getcwd()).expanduser())
        project = self.hooks.project_cls(
            name=project_name,
            repo_root=repo_root,
            monitor_session=f"project-{project_name}-monitor",
            engineers=[],
            monitor_engineers=[],
            template_name="",
            seat_overrides={},
            window_mode=args.window_mode,
            open_detail_windows=bool(args.open_detail_windows),
        )
        self.hooks.write_project(project)
        self.hooks.set_current_project(project.name)
        print(project.name)
        return 0

    def project_bootstrap(self, args: Any) -> int:
        template = self.hooks.load_template(args.template)
        local_path = Path(args.local).expanduser()
        if not local_path.exists():
            raise self.hooks.error_cls(f"Local config not found: {local_path}")
        if local_path.is_dir():
            raise self.hooks.error_cls(
                f"Local config must be a TOML file, not a directory: {local_path}"
            )
        local = self.hooks.load_toml(local_path)
        merged = self.hooks.merge_template_local(template, local)
        local_seat_overrides = {
            self.hooks.normalize_name(str(item.get("id", ""))): {
                str(key): value
                for key, value in dict(item).items()
                if key != "id"
            }
            for item in local.get("overrides", [])
            if str(item.get("id", "")).strip()
        }

        project_name = merged["project_name"]
        path = self.hooks.project_path(project_name)
        if path.exists():
            raise self.hooks.error_cls(f"{project_name} already exists")

        project = self.hooks.project_cls(
            name=project_name,
            repo_root=merged["repo_root"],
            monitor_session=f"project-{project_name}-monitor",
            engineers=[],
            monitor_engineers=[],
            template_name=str(template.get("template_name", args.template)),
            seat_overrides=local_seat_overrides,
            window_mode=merged["window_mode"],
            monitor_max_panes=merged["monitor_max_panes"],
            open_detail_windows=merged["open_detail_windows"],
        )
        self.hooks.write_project(project)

        template_profiles: dict[str, Any] = {}
        engineer_order: list[str] = []
        for engineer_spec in merged["engineers"]:
            engineer_id = self.hooks.normalize_name(str(engineer_spec["id"]))
            engineer_order.append(engineer_id)
            if self.hooks.engineer_path(engineer_id).exists():
                base_profile = self.hooks.load_engineer(engineer_id)
            else:
                role = str(engineer_spec.get("role", "")).strip()
                base_profile = self.hooks.create_engineer_profile(
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
            template_profiles[engineer_id] = self.hooks.merge_engineer_profile_with_template(base_profile, engineer_spec)

        created_sessions: list[Any] = []
        for engineer_spec in merged["engineers"]:
            engineer_id = self.hooks.normalize_name(str(engineer_spec["id"]))
            if self.hooks.session_path(project.name, engineer_id).exists():
                raise self.hooks.error_cls(f"{engineer_id} already has a session in {project.name}")
            if self.hooks.engineer_path(engineer_id).exists():
                profile = self.hooks.load_engineer(engineer_id)
            else:
                profile = template_profiles[engineer_id]
                self.hooks.write_engineer(profile)
            template_profile = template_profiles[engineer_id]

            session = self.hooks.create_session_record(
                engineer_id=engineer_id,
                project=project,
                tool=str(engineer_spec["tool"]),
                auth_mode=str(engineer_spec["auth_mode"]),
                provider=str(engineer_spec["provider"]),
                monitor=bool(engineer_spec.get("monitor", True)),
            )
            # Attach template-only fields (model, effort) for settings generation.
            # These are not part of SessionRecord but are consumed by _render_claude_settings.
            session._template_model = str(engineer_spec.get("model", "")).strip()
            session._template_effort = str(engineer_spec.get("effort", "")).strip()
            self.hooks.write_session(session)
            self.hooks.apply_template(
                session,
                project,
                engineer_override=template_profile,
                optional_skills=list(merged.get("optional_skills", [])),
                project_engineers=template_profiles,
                engineer_order=engineer_order,
            )
            self.hooks.ensure_dir(Path(session.runtime_dir))
            if session.secret_file:
                self.hooks.ensure_empty_env_file(Path(session.secret_file), self.hooks.ensure_dir, self.hooks.write_text)
            if session.engineer_id not in project.engineers:
                project.engineers.append(session.engineer_id)
            if session.monitor and session.engineer_id not in project.monitor_engineers:
                project.monitor_engineers.append(session.engineer_id)
            created_sessions.append(session)

        self.hooks.write_project(project)
        self.hooks.set_current_project(project.name)

        print(f"bootstrapped {project.name}")
        print(f"repo_root\t{project.repo_root}")
        for session in created_sessions:
            print(
                "\t".join(
                    [
                        session.engineer_id,
                        session.session,
                        session.tool,
                        session.auth_mode,
                        session.provider,
                    ]
                )
            )
        if any(session.auth_mode == "api" for session in created_sessions):
            print("warning\tapi secrets not provisioned — provision before starting sessions")
        if args.start:
            self.hooks.session_service.start_project(project)
            start_ids = self.hooks.session_service.project_autostart_engineer_ids(project)
            print(f"started\t{','.join(start_ids)}")
        return 0

    def project_use(self, args: Any) -> int:
        project = self.hooks.load_project(args.project)
        self.hooks.set_current_project(project.name)
        print(project.name)
        return 0

    def project_current(self, args: Any) -> int:
        project_name = self.hooks.get_current_project_name()
        if not project_name:
            raise self.hooks.error_cls("No current project configured")
        print(project_name)
        return 0

    def project_layout_set(self, args: Any) -> int:
        project = self.hooks.load_project_or_current(args.project)
        if args.window_mode:
            project.window_mode = args.window_mode
        if args.monitor_max_panes is not None:
            project.monitor_max_panes = max(1, int(args.monitor_max_panes))
        if args.open_detail_windows is not None:
            project.open_detail_windows = args.open_detail_windows == "true"
        if args.monitor_engineers is not None:
            monitor_engineers = [
                self.hooks.normalize_name(item)
                for item in args.monitor_engineers.split(",")
                if item.strip()
            ]
            project.monitor_engineers = monitor_engineers
        self.hooks.write_project(project)
        print(project.name)
        return 0

    def project_delete(self, args: Any) -> int:
        project = self.hooks.load_project(args.project)
        for engineer_id in list(project.engineers):
            session = self.hooks.resolve_engineer_session(engineer_id, project_name=project.name)
            self.hooks.session_service.stop_engineer(session)
            self.hooks.archive_if_exists(Path(session.workspace), "workspaces")
            self.hooks.archive_if_exists(Path(session.runtime_dir), "runtimes")
            if session.secret_file:
                self.hooks.archive_if_exists(Path(session.secret_file), "secrets")
            self.hooks.archive_if_exists(self.hooks.session_path(session.project, session.engineer_id).parent, "sessions")
            project = self.hooks.load_project(session.project)
            project.engineers = [item for item in project.engineers if item != session.engineer_id]
            project.monitor_engineers = [item for item in project.monitor_engineers if item != session.engineer_id]
            self.hooks.write_project(project)
            remaining_sessions = [
                item for item in self.hooks.load_sessions().values() if item.engineer_id == session.engineer_id
            ]
            if not remaining_sessions:
                self.hooks.archive_if_exists(self.hooks.engineer_path(session.engineer_id).parent, "engineers")
        sessions_dir = self.hooks.sessions_root / project.name
        if sessions_dir.exists():
            shutil.rmtree(sessions_dir)
        workspaces_dir = self.hooks.workspaces_root / project.name
        if workspaces_dir.exists():
            shutil.rmtree(workspaces_dir)
        project_dir = self.hooks.project_path(project.name).parent
        if project_dir.exists():
            shutil.rmtree(project_dir)
        current_project = self.hooks.get_current_project_name()
        if current_project == project.name:
            remaining = self.hooks.load_projects()
            next_project = sorted(remaining)[0] if remaining else None
            if next_project:
                self.hooks.set_current_project(next_project)
            elif self.hooks.current_project_path.exists():
                self.hooks.current_project_path.unlink()
        return 0

    def engineer_create(self, args: Any) -> int:
        # Validate the tool/auth_mode/provider triple BEFORE we touch any
        # filesystem state. Historically typos like `anthropix` (vs
        # `anthropic`) silently created engineer profiles + runtime sandbox
        # directories under the wrong identity path, then the seat would
        # start but never get its secret because the secret-file lookup
        # used the typoed provider. The operator's only symptom was a blank
        # pane. Catching this at the argparse boundary gives a clear error.
        validate_runtime_combo(
            args.tool,
            args.mode,
            args.provider,
            error_cls=self.hooks.error_cls,
            context=f"engineer create {args.engineer}",
        )
        projects = self.hooks.load_projects()
        project = projects[args.project]
        engineer_id = self.hooks.normalize_name(args.engineer)
        if self.hooks.session_path(project.name, engineer_id).exists():
            raise self.hooks.error_cls(f"{engineer_id} already has a session in {project.name}")
        if self.hooks.engineer_path(engineer_id).exists():
            profile = self.hooks.load_engineer(engineer_id)
        else:
            profile = self.hooks.create_engineer_profile(
                engineer_id=engineer_id,
                tool=args.tool,
                auth_mode=args.mode,
                provider=args.provider,
            )
            self.hooks.write_engineer(profile)
        session = self.hooks.create_session_record(
            engineer_id=engineer_id,
            project=project,
            tool=args.tool,
            auth_mode=args.mode,
            provider=args.provider,
            monitor=not args.no_monitor,
        )
        self.hooks.write_session(session)
        self.hooks.apply_template(session, project)
        self.hooks.ensure_dir(Path(session.runtime_dir))
        if session.secret_file:
            self.hooks.write_env_file(Path(session.secret_file), {}, self.hooks.ensure_dir, self.hooks.write_text)
        if session.engineer_id not in project.engineers:
            project.engineers.append(session.engineer_id)
        if session.monitor and session.engineer_id not in project.monitor_engineers:
            project.monitor_engineers.append(session.engineer_id)
        self.hooks.write_project(project)
        print(session.engineer_id)
        return 0

    def engineer_delete(self, args: Any) -> int:
        project_name = getattr(args, "project", None)
        if project_name:
            session = self.hooks.resolve_engineer_session(args.engineer, project_name=project_name)
            self.hooks.session_service.stop_engineer(session)
            self.hooks.archive_if_exists(Path(session.workspace), "workspaces")
            self.hooks.archive_if_exists(Path(session.runtime_dir), "runtimes")
            if session.secret_file:
                self.hooks.archive_if_exists(Path(session.secret_file), "secrets")
            self.hooks.archive_if_exists(self.hooks.session_path(session.project, session.engineer_id).parent, "sessions")
            project = self.hooks.load_project(session.project)
            project.engineers = [item for item in project.engineers if item != session.engineer_id]
            project.monitor_engineers = [item for item in project.monitor_engineers if item != session.engineer_id]
            self.hooks.write_project(project)
            remaining_sessions = [
                item for item in self.hooks.load_sessions().values() if item.engineer_id == session.engineer_id
            ]
            if not remaining_sessions:
                self.hooks.archive_if_exists(self.hooks.engineer_path(session.engineer_id).parent, "engineers")
            return 0

        engineer = self.hooks.resolve_engineer(args.engineer)
        all_sessions = [
            item for item in self.hooks.load_sessions().values() if item.engineer_id == engineer.engineer_id
        ]
        for session in all_sessions:
            self.hooks.session_service.stop_engineer(session)
            self.hooks.archive_if_exists(Path(session.workspace), "workspaces")
            self.hooks.archive_if_exists(Path(session.runtime_dir), "runtimes")
            if session.secret_file:
                self.hooks.archive_if_exists(Path(session.secret_file), "secrets")
            self.hooks.archive_if_exists(self.hooks.session_path(session.project, session.engineer_id).parent, "sessions")
            project = self.hooks.load_project(session.project)
            project.engineers = [item for item in project.engineers if item != session.engineer_id]
            project.monitor_engineers = [item for item in project.monitor_engineers if item != session.engineer_id]
            self.hooks.write_project(project)
        self.hooks.archive_if_exists(self.hooks.engineer_path(engineer.engineer_id).parent, "engineers")
        return 0

    def engineer_rename(self, args: Any) -> int:
        old = self.hooks.resolve_engineer(args.old)
        new_id = self.hooks.normalize_name(args.new)
        if self.hooks.engineer_path(new_id).exists():
            raise self.hooks.error_cls(f"{new_id} already exists")

        new_engineer = self.hooks.engineer_cls(
            engineer_id=new_id,
            display_name=new_id,
            aliases=[*old.aliases, old.engineer_id],
            role=old.role,
            role_details=list(old.role_details),
            skills=list(old.skills),
            human_facing=old.human_facing,
            active_loop_owner=old.active_loop_owner,
            dispatch_authority=old.dispatch_authority,
            patrol_authority=old.patrol_authority,
            unblock_authority=old.unblock_authority,
            escalation_authority=old.escalation_authority,
            remind_active_loop_owner=old.remind_active_loop_owner,
            review_authority=old.review_authority,
            qa_authority=old.qa_authority,
            design_authority=old.design_authority,
            default_tool=old.default_tool,
            default_auth_mode=old.default_auth_mode,
            default_provider=old.default_provider,
        )
        self.hooks.write_engineer(new_engineer)

        all_sessions = [
            item for item in self.hooks.load_sessions().values() if item.engineer_id == old.engineer_id
        ]
        for old_session in all_sessions:
            new_identity = self.hooks.identity_name(
                old_session.tool,
                old_session.auth_mode,
                old_session.provider,
                new_id,
                old_session.project,
            )
            new_session = self.hooks.session_record_cls(
                engineer_id=new_id,
                project=old_session.project,
                tool=old_session.tool,
                auth_mode=old_session.auth_mode,
                provider=old_session.provider,
                identity=new_identity,
                workspace=str(self.hooks.workspaces_root / old_session.project / new_id),
                runtime_dir=str(
                    self.hooks.runtime_dir_for_identity(
                        old_session.tool,
                        old_session.auth_mode,
                        new_identity,
                    )
                ),
                session=self.hooks.session_name_for(old_session.project, new_id, old_session.tool),
                bin_path=old_session.bin_path,
                monitor=old_session.monitor,
                legacy_sessions=list(old_session.legacy_sessions),
                launch_args=list(old_session.launch_args),
                secret_file="",
                wrapper=old_session.wrapper,
            )
            if old_session.secret_file:
                new_session.secret_file = str(
                    self.hooks.secret_file_for(old_session.tool, old_session.provider, new_id)
                )

            if self.hooks.tmux_has_session(old_session.session):
                subprocess.run(["tmux", "rename-session", "-t", old_session.session, new_session.session], check=True)

            if Path(old_session.workspace).exists():
                self.hooks.ensure_dir(Path(new_session.workspace).parent)
                shutil.move(old_session.workspace, new_session.workspace)
            if Path(old_session.runtime_dir).exists():
                self.hooks.ensure_dir(Path(new_session.runtime_dir).parent)
                shutil.move(old_session.runtime_dir, new_session.runtime_dir)
            if old_session.secret_file and Path(old_session.secret_file).exists():
                self.hooks.ensure_dir(Path(new_session.secret_file).parent)
                shutil.move(old_session.secret_file, new_session.secret_file)
                self.hooks.ensure_secret_permissions(Path(new_session.secret_file))

            self.hooks.write_session(new_session)
            self.hooks.archive_if_exists(self.hooks.session_path(old_session.project, old.engineer_id).parent, "sessions")
            project = self.hooks.load_project(old_session.project)
            project.engineers = [new_id if item == old.engineer_id else item for item in project.engineers]
            project.monitor_engineers = [
                new_id if item == old.engineer_id else item for item in project.monitor_engineers
            ]
            self.hooks.write_project(project)

        shutil.rmtree(self.hooks.engineer_path(old.engineer_id).parent)
        return 0

    def engineer_rebind(self, args: Any) -> int:
        session = self.hooks.resolve_engineer_session(args.engineer, project_name=getattr(args, "project", None))
        project = self.hooks.load_project(session.project)
        provider = args.provider
        mode = args.mode
        new_identity = self.hooks.identity_name(
            session.tool,
            mode,
            provider,
            session.engineer_id,
            session.project,
        )
        new_runtime = self.hooks.runtime_dir_for_identity(session.tool, mode, new_identity)
        if session.auth_mode == mode and session.provider == provider:
            return 0

        old_runtime = Path(session.runtime_dir)
        if old_runtime.exists():
            self.hooks.archive_if_exists(old_runtime, "runtimes")
        new_secret_file = ""
        if mode == "api":
            new_secret_file = str(self.hooks.secret_file_for(session.tool, provider, session.engineer_id))
            if not Path(new_secret_file).exists():
                self.hooks.write_env_file(Path(new_secret_file), {}, self.hooks.ensure_dir, self.hooks.write_text)
        session.auth_mode = mode
        session.provider = provider
        session.identity = new_identity
        session.runtime_dir = str(new_runtime)
        session.secret_file = new_secret_file
        self.hooks.write_session(session)
        self.hooks.apply_template(session, project)
        return 0

    def engineer_secret_set(self, args: Any) -> int:
        session = self.hooks.resolve_engineer_session(args.engineer, project_name=getattr(args, "project", None))
        if session.auth_mode != "api" or not session.secret_file:
            raise self.hooks.error_cls(f"{session.engineer_id} does not use API secrets")
        values = self.hooks.parse_env_file(Path(session.secret_file))
        values[args.key] = args.value
        self.hooks.write_env_file(Path(session.secret_file), values, self.hooks.ensure_dir, self.hooks.write_text)
        return 0
