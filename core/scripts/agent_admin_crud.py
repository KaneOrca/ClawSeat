from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent_admin_config import HOME, REPO_ROOT, SEND_AND_VERIFY_SH, validate_runtime_combo


# ── Profile TOML helpers (text-based, preserves comments and order) ────────────


def _toml_inline_list_add(text: str, key: str, value: str, *, section: str | None = None) -> str:
    """Add *value* to an inline TOML list; no-op if already present or key not found."""
    if section is not None:
        sec_m = re.search(rf'^\[{re.escape(section)}\]', text, re.MULTILINE)
        if not sec_m:
            return text
        after_sec = text[sec_m.end():]
        nxt = re.search(r'^\[', after_sec, re.MULTILINE)
        search_text = after_sec[: nxt.start()] if nxt else after_sec
        base_offset = sec_m.end()
    else:
        search_text = text
        base_offset = 0

    pat = re.compile(rf'^{re.escape(key)}\s*=\s*\[([^\]]*)\]', re.MULTILINE)
    km = pat.search(search_text)
    if not km:
        return text

    inner = km.group(1)
    existing = [v.strip().strip("\"'") for v in inner.split(",") if v.strip().strip("\"'")]
    if value in existing:
        return text

    new_inner = (inner + f', "{value}"') if inner.strip() else f'"{value}"'
    new_entry = f"{key} = [{new_inner}]"
    abs_start = base_offset + km.start()
    abs_end = base_offset + km.end()
    return text[:abs_start] + new_entry + text[abs_end:]


def _toml_seat_role_set(text: str, seat_id: str, role: str) -> str:
    """Set seat_roles.<seat_id> = role in the [seat_roles] section."""
    sec_m = re.search(r'^\[seat_roles\]', text, re.MULTILINE)
    if not sec_m:
        return text.rstrip("\n") + f'\n\n[seat_roles]\n{seat_id} = "{role}"\n'

    after = text[sec_m.end():]
    nxt = re.search(r'^\[', after, re.MULTILINE)
    sec_len = nxt.start() if nxt else len(after)
    sec_content = after[:sec_len]

    km = re.search(rf'^{re.escape(seat_id)}\s*=.*$', sec_content, re.MULTILINE)
    if km:
        new_sec = sec_content[: km.start()] + f'{seat_id} = "{role}"' + sec_content[km.end():]
    else:
        new_sec = sec_content.rstrip("\n") + f'\n{seat_id} = "{role}"\n'

    return text[: sec_m.end()] + new_sec + text[sec_m.end() + sec_len:]


def _toml_seat_overrides_set(
    text: str,
    seat_id: str,
    tool: str,
    auth_mode: str,
    provider: str,
    model: str | None,
    *,
    update: bool = False,
) -> str:
    """Add (or update when update=True) a [seat_overrides.<seat_id>] block."""
    block_key = f"seat_overrides.{seat_id}"
    block_m = re.search(rf'^\[{re.escape(block_key)}\]', text, re.MULTILINE)

    lines = [f"[{block_key}]", f'tool = "{tool}"', f'auth_mode = "{auth_mode}"', f'provider = "{provider}"']
    if model:
        lines.append(f'model = "{model}"')
    new_block = "\n".join(lines) + "\n"

    if block_m:
        if not update:
            return text  # already exists — idempotent skip for create
        after = text[block_m.end():]
        nxt = re.search(r'^\[', after, re.MULTILINE)
        block_end = block_m.end() + (nxt.start() if nxt else len(after))
        before = text[: block_m.start()].rstrip("\n") + "\n\n"
        rest = text[block_end:].lstrip("\n")
        return before + new_block + ("\n" + rest if rest else "")

    return text.rstrip("\n") + "\n\n" + new_block


def _update_profile_seat(
    profile_path: Path,
    seat_id: str,
    role: str,
    tool: str,
    auth_mode: str,
    provider: str,
    model: str | None = None,
    *,
    rebind: bool = False,
) -> None:
    """Update a harness profile TOML with seat metadata.

    For create (rebind=False): idempotently appends seat to seats,
    materialized_seats, runtime_seats, seat_roles, and seat_overrides.
    For rebind (rebind=True): only updates seat_overrides (always overwrites).
    """
    if not re.match(r'^[a-zA-Z0-9_-]+$', seat_id):
        raise ValueError(f"Invalid seat_id {seat_id!r}: must match [a-zA-Z0-9_-]+")

    text = profile_path.read_text(encoding="utf-8")

    if not rebind:
        text = _toml_inline_list_add(text, "seats", seat_id)
        text = _toml_inline_list_add(text, "materialized_seats", seat_id, section="dynamic_roster")
        text = _toml_inline_list_add(text, "runtime_seats", seat_id, section="dynamic_roster")
        text = _toml_seat_role_set(text, seat_id, role)
        text = _toml_seat_overrides_set(text, seat_id, tool, auth_mode, provider, model)
    else:
        text = _toml_seat_overrides_set(text, seat_id, tool, auth_mode, provider, model, update=True)

    profile_path.write_text(text, encoding="utf-8")


_PROJECT_TOOL_SEED_MAP: dict[str, tuple[tuple[str, bool], ...]] = {
    "lark-cli": ((".lark-cli", True),),
    "gemini": (
        (".config/gemini", True),
        (".gemini", True),
    ),
    "codex": (
        (".config/codex", True),
        (".codex", True),
    ),
    "iterm2": (
        ("Library/Application Support/iTerm2", True),
        ("Library/Preferences/com.googlecode.iterm2.plist", False),
    ),
}

_PROJECT_TOOL_SEED_ALIASES = {
    "lark": "lark-cli",
    "lark-cli": "lark-cli",
    "lark_cli": "lark-cli",
    "gemini": "gemini",
    "codex": "codex",
    "iterm": "iterm2",
    "iterm2": "iterm2",
}

_DEFAULT_PROJECT_TOOL_SEEDS = ("lark-cli", "gemini", "codex", "iterm2")


def _normalize_project_tool_seed_names(raw: str | None) -> list[str]:
    if raw is None:
        return list(_DEFAULT_PROJECT_TOOL_SEEDS)
    tokens = [item.strip().lower() for item in re.split(r"[,\s]+", raw) if item.strip()]
    if not tokens:
        return list(_DEFAULT_PROJECT_TOOL_SEEDS)
    result: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        canonical = _PROJECT_TOOL_SEED_ALIASES.get(token)
        if not canonical:
            raise ValueError(
                f"unknown tool {token!r}; expected lark-cli, gemini, codex, or iterm2"
            )
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def _project_tool_seed_entries(tool: str) -> tuple[tuple[str, bool], ...]:
    try:
        return _PROJECT_TOOL_SEED_MAP[tool]
    except KeyError as exc:
        raise ValueError(f"unknown project tool seed {tool!r}") from exc


def _remove_existing_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_project_tool_seed(source: Path, target: Path) -> None:
    if source.is_dir():
        if target.exists() and not target.is_dir():
            _remove_existing_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=True)
        return
    if target.exists():
        _remove_existing_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _project_tool_root_path(project: str) -> Path:
    from project_tool_root import project_tool_root

    return project_tool_root(project)


def _q(value: str) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def _q_array(values: list[str]) -> str:
    return "[" + ", ".join(_q(value) for value in values) + "]"


def _render_dynamic_profile(
    template_text: str,
    *,
    project: str,
    repo_root: str,
    profile_path: Path,
    seats: list[str],
    seat_roles: dict[str, str],
) -> str:
    tasks_root = HOME / ".agents" / "tasks" / project
    workspace_root = HOME / ".agents" / "workspaces" / project
    handoff_dir = tasks_root / "patrol" / "handoffs"
    default_target = "planner" if "planner" in seats else (seats[0] if seats else "")
    seat_roles_block = "\n".join(f"{seat} = {_q(seat_roles.get(seat, seat))}" for seat in seats)
    seat_overrides_block = "\n\n".join(f"[seat_overrides.{seat}]" for seat in seats)
    replacements = {
        "{{project}}": project,
        "{{profile_path}}": str(profile_path),
        "{{repo_root}}": repo_root,
        "{{tasks_root}}": str(tasks_root),
        "{{project_doc}}": str(tasks_root / "PROJECT.md"),
        "{{tasks_doc}}": str(tasks_root / "TASKS.md"),
        "{{status_doc}}": str(tasks_root / "STATUS.md"),
        "{{send_script}}": str(SEND_AND_VERIFY_SH),
        "{{agent_admin}}": str(REPO_ROOT / "core" / "scripts" / "agent_admin.py"),
        "{{workspace_root}}": str(workspace_root),
        "{{handoff_dir}}": str(handoff_dir),
        "{{heartbeat_receipt}}": str(HOME / ".openclaw" / "koder" / f"{project}-HEARTBEAT_RECEIPT.toml"),
        "{{session_root}}": str(HOME / ".agents" / "sessions"),
        "{{default_notify_target}}": default_target,
        "{{seats}}": _q_array(seats),
        "{{seat_roles_block}}": seat_roles_block,
        "{{seat_overrides_block}}": seat_overrides_block,
    }
    rendered = template_text
    for needle, value in replacements.items():
        rendered = rendered.replace(needle, value)
    return rendered.rstrip() + "\n"


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

    def _engineer_template_defaults(self, project: Any, engineer_id: str) -> dict[str, str]:
        template_names = [str(getattr(project, "template_name", "") or ""), "gstack-harness"]
        seen: set[str] = set()
        for template_name in template_names:
            if not template_name or template_name in seen:
                continue
            seen.add(template_name)
            try:
                template = self.hooks.load_template(template_name)
            except Exception:
                continue
            for spec in template.get("engineers", []):
                if self.hooks.normalize_name(str(spec.get("id", ""))) == engineer_id:
                    return {
                        "tool": str(spec.get("tool", "") or ""),
                        "mode": str(spec.get("auth_mode", "") or ""),
                        "provider": str(spec.get("provider", "") or ""),
                    }
        return {}

    def project_open(self, args: Any) -> int:
        return self.hooks.show_project(args)

    def project_create(self, args: Any) -> int:
        project_name = self.hooks.normalize_name(args.project)
        path = self.hooks.project_path(project_name)
        if path.exists():
            print(project_name)
            return 0
        repo_root_value = (args.repo_root or "").strip()
        repo_root = str(Path(repo_root_value or os.getcwd()).expanduser())
        template_name = str(getattr(args, "template", "") or "clawseat-minimal")
        template = self.hooks.load_template(template_name)
        merged = self.hooks.merge_template_local(
            template,
            {
                "project_name": project_name,
                "repo_root": repo_root,
            },
        )
        engineer_ids = [
            self.hooks.normalize_name(str(item.get("id", "")))
            for item in merged["engineers"]
            if str(item.get("id", "")).strip()
        ]
        seat_roles = {
            self.hooks.normalize_name(str(item.get("id", ""))): str(item.get("role", "") or item.get("id", ""))
            for item in merged["engineers"]
            if str(item.get("id", "")).strip()
        }
        project = self.hooks.project_cls(
            name=project_name,
            repo_root=merged["repo_root"],
            monitor_session=f"project-{project_name}-monitor",
            engineers=list(engineer_ids),
            monitor_engineers=list(engineer_ids),
            template_name=str(template.get("template_name", template_name)),
            seat_overrides={seat_id: {} for seat_id in engineer_ids},
            window_mode=getattr(args, "window_mode", None) or str(merged["window_mode"]),
            monitor_max_panes=len(engineer_ids) or int(merged["monitor_max_panes"]),
            open_detail_windows=bool(args.open_detail_windows) or bool(merged["open_detail_windows"]),
        )
        self.hooks.write_project(project)
        profile_path = HOME / ".agents" / "profiles" / f"{project_name}-profile-dynamic.toml"
        if not profile_path.exists():
            profile_template = (REPO_ROOT / "core" / "templates" / "profile-dynamic.template.toml").read_text(
                encoding="utf-8"
            )
            self.hooks.write_text(
                profile_path,
                _render_dynamic_profile(
                    profile_template,
                    project=project_name,
                    repo_root=project.repo_root,
                    profile_path=profile_path,
                    seats=engineer_ids,
                    seat_roles=seat_roles,
                ),
                None,
            )
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
                session_name=str(engineer_spec.get("session_name", "")).strip(),
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

    def project_init_tools(self, args: Any) -> int:
        from project_binding import load_binding, write_binding
        from real_home import real_user_home

        project = self.hooks.load_project_or_current(args.project)
        binding = load_binding(project.name)
        if binding is None:
            raise self.hooks.error_cls(
                f"project {project.name!r} has no PROJECT_BINDING.toml; bind it first before init-tools"
            )

        tools = _normalize_project_tool_seed_names(getattr(args, "tools", None))
        target_root = _project_tool_root_path(project.name)
        source_project = (getattr(args, "source_project", "") or "").strip()
        source_root = (
            _project_tool_root_path(source_project)
            if source_project
            else real_user_home()
        )
        from_mode = (getattr(args, "from_source", "real-home") or "real-home").strip()

        if binding.tools_isolation != "per-project":
            binding.tools_isolation = "per-project"

        if getattr(args, "dry_run", False):
            print(
                f"dry-run\tproject init-tools {project.name} -> {target_root}"
                f"\n  from\t{source_project or from_mode}"
                f"\n  tools\t{', '.join(tools)}"
            )
            return 0

        target_root.mkdir(parents=True, exist_ok=True)
        planned: list[str] = []
        for tool in tools:
            for rel_path, is_dir in _project_tool_seed_entries(tool):
                dst = target_root / rel_path
                if from_mode == "empty" and not source_project:
                    if is_dir:
                        dst.mkdir(parents=True, exist_ok=True)
                    else:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                    planned.append(rel_path)
                    continue
                src = source_root / rel_path
                if not src.exists():
                    continue
                _copy_project_tool_seed(src, dst)
                planned.append(rel_path)

        write_binding(binding)
        reseeded: list[str] = []
        for engineer_id in list(project.engineers):
            try:
                session = self.hooks.resolve_engineer_session(engineer_id, project_name=project.name)
                updated = self.hooks.session_service.reseed_sandbox_user_tool_dirs(session)
            except Exception as exc:  # noqa: BLE001 - surface clear operator error
                raise self.hooks.error_cls(
                    f"init-tools reseed failed for {engineer_id}: {exc}"
                ) from exc
            if updated:
                reseeded.append(f"{engineer_id}: {', '.join(updated)}")

        print(f"project init-tools updated: {project.name} [{target_root}]")
        if planned:
            print(f"seeded\t{', '.join(planned)}")
        if reseeded:
            print("\n".join(f"reseeded\t{item}" for item in reseeded))
        return 0

    def project_switch_identity(self, args: Any) -> int:
        """Record project-local identity metadata and reseed existing seats.

        Behavioral contract:
        - This command only updates PROJECT_BINDING.toml and reseeds seat sandboxes.
        - It does not call native login CLIs such as `lark-cli auth ...`.
        - It does not migrate credential payloads such as
          `.gemini/oauth_creds.json` or `.codex/auth.json`.
        - Operators must prepare the per-project tool root first
          (`project init-tools --from real-home|empty [--source-project ...]`)
          and place the desired credentials there before switching.
        """
        from project_binding import load_binding, write_binding

        project = self.hooks.load_project_or_current(args.project)
        binding = load_binding(project.name)
        if binding is None:
            raise self.hooks.error_cls(
                f"project {project.name!r} has no PROJECT_BINDING.toml; bind it first before switch-identity"
            )

        tool = str(getattr(args, "tool", "")).strip().lower()
        identity = str(getattr(args, "identity", "")).strip()
        if not identity:
            raise self.hooks.error_cls("switch-identity requires --identity")
        if tool not in {"feishu", "gemini", "codex"}:
            raise self.hooks.error_cls("switch-identity tool must be feishu, gemini, or codex")

        if tool == "feishu":
            binding.feishu_sender_app_id = identity
            binding.feishu_bot_account = identity
        elif tool == "gemini":
            binding.gemini_account_email = identity
        elif tool == "codex":
            binding.codex_account_email = identity
        binding.tools_isolation = "per-project"

        if getattr(args, "dry_run", False):
            print(
                f"dry-run\tproject switch-identity {project.name}"
                f"\n  tool\t{tool}"
                f"\n  identity\t{identity}"
                f"\n  binding\ttools_isolation=per-project"
            )
            return 0

        write_binding(binding)

        reseeded: list[str] = []
        for engineer_id in list(project.engineers):
            try:
                session = self.hooks.resolve_engineer_session(engineer_id, project_name=project.name)
                updated = self.hooks.session_service.reseed_sandbox_user_tool_dirs(session)
            except Exception as exc:  # noqa: BLE001 - surface clear operator error
                raise self.hooks.error_cls(
                    f"switch-identity reseed failed for {engineer_id}: {exc}"
                ) from exc
            if updated:
                reseeded.append(f"{engineer_id}: {', '.join(updated)}")

        print(
            f"project switch-identity updated: {project.name} tool={tool} identity={identity}"
        )
        if reseeded:
            print("\n".join(f"reseeded\t{item}" for item in reseeded))
        return 0

    def _archive_session_artifacts(self, session: Any) -> None:
        """Archive workspace/runtime/secret/session-dir and remove from project rosters."""
        self.hooks.archive_if_exists(Path(session.workspace), "workspaces")
        self.hooks.archive_if_exists(Path(session.runtime_dir), "runtimes")
        if session.secret_file:
            self.hooks.archive_if_exists(Path(session.secret_file), "secrets")
        self.hooks.archive_if_exists(
            self.hooks.session_path(session.project, session.engineer_id).parent, "sessions"
        )
        project = self.hooks.load_project(session.project)
        project.engineers = [item for item in project.engineers if item != session.engineer_id]
        project.monitor_engineers = [item for item in project.monitor_engineers if item != session.engineer_id]
        self.hooks.write_project(project)

    def project_delete(self, args: Any) -> int:
        project = self.hooks.load_project(args.project)
        for engineer_id in list(project.engineers):
            session = self.hooks.resolve_engineer_session(engineer_id, project_name=project.name)
            self.hooks.session_service.stop_engineer(session)
            self._archive_session_artifacts(session)
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
        projects = self.hooks.load_projects()
        project = projects[args.project]
        engineer_id = self.hooks.normalize_name(args.engineer)
        defaults = self._engineer_template_defaults(project, engineer_id)
        tool = getattr(args, "tool", None) or defaults.get("tool") or "claude"
        mode = getattr(args, "mode", None) or defaults.get("mode") or "oauth"
        provider = getattr(args, "provider", None) or defaults.get("provider") or "anthropic"
        # Validate the tool/auth_mode/provider triple BEFORE we touch any
        # filesystem state. Historically typos like `anthropix` (vs
        # `anthropic`) silently created engineer profiles + runtime sandbox
        # directories under the wrong identity path, then the seat would
        # start but never get its secret because the secret-file lookup
        # used the typoed provider. The operator's only symptom was a blank
        # pane. Catching this at the argparse boundary gives a clear error.
        validate_runtime_combo(
            tool,
            mode,
            provider,
            error_cls=self.hooks.error_cls,
            context=f"engineer create {args.engineer}",
        )
        if self.hooks.session_path(project.name, engineer_id).exists():
            raise self.hooks.error_cls(f"{engineer_id} already has a session in {project.name}")
        if self.hooks.engineer_path(engineer_id).exists():
            profile = self.hooks.load_engineer(engineer_id)
        else:
            profile = self.hooks.create_engineer_profile(
                engineer_id=engineer_id,
                tool=tool,
                auth_mode=mode,
                provider=provider,
            )
            self.hooks.write_engineer(profile)
        session = self.hooks.create_session_record(
            engineer_id=engineer_id,
            project=project,
            tool=tool,
            auth_mode=mode,
            provider=provider,
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

        profile_path = getattr(args, "profile", None)
        if profile_path:
            session_toml = self.hooks.session_path(project.name, engineer_id)
            if not session_toml.exists():
                print(
                    f"warn: session.toml not found at {session_toml}; skipping profile update",
                    file=sys.stderr,
                )
            else:
                try:
                    session_data = self.hooks.load_toml(session_toml)
                    role_val = (getattr(args, "role", None) or "").strip() or engineer_id.split("-")[0]
                    _update_profile_seat(
                        Path(profile_path),
                        engineer_id,
                        role_val,
                        session_data.get("tool", tool),
                        session_data.get("auth_mode", mode),
                        session_data.get("provider", provider),
                        session_data.get("model"),
                    )
                except Exception as exc:
                    print(f"warn: profile update failed: {exc}", file=sys.stderr)

        print(session.engineer_id)
        return 0

    def engineer_delete(self, args: Any) -> int:
        project_name = getattr(args, "project", None)
        if project_name:
            session = self.hooks.resolve_engineer_session(args.engineer, project_name=project_name)
            self.hooks.session_service.stop_engineer(session)
            self._archive_session_artifacts(session)
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
            self._archive_session_artifacts(session)
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
        requested_tool = getattr(args, "tool", None)
        if requested_tool is not None and requested_tool != session.tool:
            print(
                f"error: rebind cannot change tool (current={session.tool}, requested={requested_tool}). "
                f"Use 'engineer delete {args.engineer}' then 'engineer create' with the new tool.",
                file=sys.stderr,
            )
            return 2
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

        profile_path = getattr(args, "profile", None)
        if profile_path:
            session_toml = self.hooks.session_path(session.project, session.engineer_id)
            if not session_toml.exists():
                print(
                    f"warn: session.toml not found at {session_toml}; skipping profile update",
                    file=sys.stderr,
                )
            else:
                try:
                    session_data = self.hooks.load_toml(session_toml)
                    role_val = session.engineer_id.split("-")[0]
                    _update_profile_seat(
                        Path(profile_path),
                        session.engineer_id,
                        role_val,
                        session_data.get("tool", session.tool),
                        session_data.get("auth_mode", mode),
                        session_data.get("provider", provider),
                        session_data.get("model"),
                        rebind=True,
                    )
                except Exception as exc:
                    print(f"warn: profile update failed: {exc}", file=sys.stderr)

        return 0

    def engineer_refresh_workspace(self, args: Any) -> int:
        session = self.hooks.resolve_engineer_session(
            args.engineer,
            project_name=getattr(args, "project", None),
        )
        project = self.hooks.load_project(session.project)
        self.hooks.apply_template(session, project)
        print(f"refreshed\t{session.engineer_id}\t{session.session}\t{session.workspace}")
        return 0

    def engineer_secret_set(self, args: Any) -> int:
        session = self.hooks.resolve_engineer_session(args.engineer, project_name=getattr(args, "project", None))
        if session.auth_mode != "api" or not session.secret_file:
            raise self.hooks.error_cls(f"{session.engineer_id} does not use API secrets")
        values = self.hooks.parse_env_file(Path(session.secret_file))
        values[args.key] = args.value
        self.hooks.write_env_file(Path(session.secret_file), values, self.hooks.ensure_dir, self.hooks.write_text)
        return 0


if __name__ == "__main__":
    import argparse as _ap

    _p = _ap.ArgumentParser(description="Profile-only seat operations (no session bootstrap)")
    _p.add_argument("command", choices=["engineer_create", "engineer_rebind"])
    _p.add_argument("seat_id")
    _p.add_argument("--profile", required=True)
    _p.add_argument("--role")
    _p.add_argument("--tool", default="claude")
    _p.add_argument("--mode", default="oauth")
    _p.add_argument("--provider", default="anthropic")
    _p.add_argument("--model")
    _a = _p.parse_args()
    _profile_path = Path(_a.profile)
    _role = (_a.role or "").strip() or _a.seat_id.split("-")[0]
    _rebind = _a.command == "engineer_rebind"
    try:
        _update_profile_seat(
            _profile_path,
            _a.seat_id,
            _role,
            _a.tool,
            _a.mode,
            _a.provider,
            _a.model,
            rebind=_rebind,
        )
        print(f"updated profile {_profile_path}: {_a.seat_id} ({_a.command})")
    except Exception as _exc:
        print(f"error: {_exc}", file=sys.stderr)
        sys.exit(1)
