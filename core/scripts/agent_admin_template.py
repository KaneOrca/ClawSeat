from __future__ import annotations

import os
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


# Ensure `core/` is importable so bare `from resolve import ...` resolves
# regardless of how this module is invoked (direct script vs import).
_REPO_ROOT = Path(
    os.environ.get("CLAWSEAT_ROOT", str(Path(__file__).resolve().parents[2]))
)
_CORE_PATH = str(_REPO_ROOT / "core")
if _CORE_PATH not in sys.path:
    sys.path.insert(0, _CORE_PATH)
_CORE_SCRIPTS_PATH = str(_REPO_ROOT / "core" / "scripts")
if _CORE_SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, _CORE_SCRIPTS_PATH)


def _load_role_skill_content(
    repo_root: Path,
    seat_id: str,
    role_hint: str | None = None,
) -> tuple[str, str] | None:
    """Locate and read `core/skills/<role>/SKILL.md` for a seat.

    Returns (role_name, body_without_frontmatter) or None when no role
    mapping exists or the SKILL.md file is missing. Resolution order:
      1. role_hint (e.g. "creative-builder") when the seat's template role
         differs from its generic seat-id (e.g. "builder").  If the hint's
         SKILL.md exists it takes precedence so creative/engineering template
         seats load the right contract.
      2. seat_skill_mapping.role_skill_for_seat(seat_id) — handles suffixed
         ids like `builder-1 -> builder` and `memory -> memory-oracle`.
    YAML frontmatter (leading `---` block) is stripped so the embedded
    content slots cleanly under a `## Role SKILL (canonical)` header.
    """
    def _read_skill(role_name: str) -> tuple[str, str] | None:
        skill_file = Path(repo_root) / "core" / "skills" / role_name / "SKILL.md"
        if not skill_file.is_file():
            return None
        try:
            text = skill_file.read_text(encoding="utf-8")
        except OSError:
            return None
        # Strip YAML frontmatter of the form:
        #   ---\n<fields>\n---\n<body>
        if text.startswith("---\n") or text.startswith("---\r\n"):
            newline_marker = "\n---\n"
            end = text.find(newline_marker, 4)
            if end >= 0:
                text = text[end + len(newline_marker):]
        return role_name, text.lstrip("\n")

    if role_hint:
        result = _read_skill(role_hint)
        if result is not None:
            return result

    try:
        from seat_skill_mapping import role_skill_for_seat
    except ModuleNotFoundError:
        return None
    role_name = role_skill_for_seat(seat_id)
    if not role_name:
        return None
    return _read_skill(role_name)


def _role_skill_section_lines(
    repo_root: Path,
    seat_id: str,
    role_hint: str | None = None,
) -> list[str]:
    """Render the `## Role SKILL (canonical)` block, or [] when no skill."""
    info = _load_role_skill_content(repo_root, seat_id, role_hint)
    if not info:
        return []
    role_name, body = info
    return [
        "",
        "---",
        "",
        "## Role SKILL (canonical)",
        "",
        (
            f"Loaded from `core/skills/{role_name}/SKILL.md` — this is the "
            "authoritative role contract for this seat. Treat any conflict "
            "with the stub above as the SKILL winning; stub metadata exists "
            "only to anchor the workspace to the rendered engineer profile."
        ),
        "",
        body.rstrip(),
    ]


@dataclass
class TemplateHooks:
    ensure_dir: Callable[[Path], None]
    write_text: Callable[[Path, str], None]
    load_engineer: Callable[[str], Any]
    project_template_context: Callable[[Any], tuple[dict[str, Any], list[str], list[dict[str, object]]] | None]
    q: Callable[[str], str]
    render_authority_lines: Callable[[Any], list[str]]
    render_read_first_lines: Callable[[Any, Any, Any], list[str]]
    render_harness_runtime_lines: Callable[[Any], list[str]]
    render_project_seat_map_lines: Callable[..., list[str]]
    render_seat_boundary_lines: Callable[[Any, Any], list[str]]
    render_communication_protocol_lines: Callable[[Any, str], list[str]]
    render_dispatch_playbook_lines: Callable[[Any, Any, Any], list[str]]
    render_loaded_skills_lines: Callable[[Any, str], list[str]]
    render_optional_skills_catalog: Callable[[list[dict[str, object]]], str]
    workspace_contract_payload: Callable[..., dict[str, object]]
    workspace_contract_fingerprint: Callable[[dict[str, object]], str]
    render_workspace_contract_text: Callable[..., str]
    render_role_line: Callable[[Any, bool], str]
    render_role_details_lines: Callable[[Any], list[str]]
    render_aliases_lines: Callable[[Any], list[str]]
    render_heartbeat_text: Callable[[Any, Any, Any], str | None]
    render_heartbeat_manifest_text: Callable[..., str | None]


class TemplateHandlers:
    def __init__(self, hooks: TemplateHooks) -> None:
        self.hooks = hooks

    def _render_workspace_memory_template(
        self,
        variant: str,
        *,
        session: Any,
        project: Any,
        profile_display: str,
    ) -> str:
        template_path = _REPO_ROOT / "core" / "templates" / f"workspace-memory.template.md.{variant}"
        text = template_path.read_text(encoding="utf-8")
        agents_home = str(Path(session.workspace).expanduser().parents[2])
        replacements = {
            "{{project}}": str(project.name),
            "{{profile}}": profile_display,
            "{{repo_root}}": str(project.repo_root),
            "{{workspace}}": str(session.workspace),
            "{{agents_home}}": agents_home,
        }
        for needle, value in replacements.items():
            text = text.replace(needle, value)
        return text

    def _render_claude_settings(self, session: Any, engineer: Any = None) -> str:
        import json
        try:
            import tomllib as _tomllib
        except ModuleNotFoundError:
            import tomli as _tomllib
        from agent_admin_config import CLAUDE_API_PROVIDER_CONFIGS

        settings: dict[str, object] = {"workspace_label": session.engineer_id}

        # Model/effort resolution chain:
        # 1. _template_model/_template_effort (set by project_bootstrap on session)
        # 2. template.toml engineer spec — only attempted when session.project_record.template_name is set
        # 3. CLAUDE_API_PROVIDER_CONFIGS — only for auth_mode=api with a known provider
        model = getattr(session, "_template_model", "") or ""
        effort = getattr(session, "_template_effort", "") or ""

        if not model or not effort:
            template_name = getattr(getattr(session, "project_record", None), "template_name", "") or ""
            if template_name:
                from pathlib import Path
                from agent_admin_config import REPO_ROOT
                tpl_path = REPO_ROOT / "core" / "templates" / template_name / "template.toml"
                if tpl_path.exists():
                    with open(tpl_path, "rb") as f:
                        tpl = _tomllib.load(f)
                    for eng in tpl.get("engineers", []):
                        if eng.get("id") == session.engineer_id:
                            if not model:
                                model = str(eng.get("model", "")).strip()
                            if not effort:
                                effort = str(eng.get("effort", "")).strip()
                            break

        if not model and session.auth_mode == "api":
            provider_config = CLAUDE_API_PROVIDER_CONFIGS.get(session.provider, {})
            model = provider_config.get("model", "")

        if model:
            settings["model"] = model
        if effort:
            settings["effortLevel"] = effort

        # API mode seats skip onboarding — auth is via API key, not OAuth
        if session.auth_mode == "api":
            settings["hasCompletedOnboarding"] = True

        return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"

    def render_template_text(
        self,
        tool: str,
        session: Any,
        project: Any,
        engineer_override: Any | None = None,
        project_engineers: dict[str, Any] | None = None,
        engineer_order: list[str] | None = None,
    ) -> dict[str, str]:
        repo_root = project.repo_root
        engineer = engineer_override or self.hooks.load_engineer(session.engineer_id)
        session.project_record = project
        session.project_engineers = project_engineers or {}
        session.engineer_order = engineer_order or []
        engineer._project_record = project
        engineer._project_engineers = project_engineers or {}
        engineer._engineer_order = engineer_order or []
        authority_lines = self.hooks.render_authority_lines(engineer)
        read_first_lines = self.hooks.render_read_first_lines(session, project, engineer)
        harness_runtime_lines = self.hooks.render_harness_runtime_lines(engineer)
        project_seat_map_lines = self.hooks.render_project_seat_map_lines(
            session,
            project,
            engineer,
            project_engineers=project_engineers,
            engineer_order=engineer_order,
        )
        seat_boundary_lines = self.hooks.render_seat_boundary_lines(session, engineer)
        communication_protocol_lines = self.hooks.render_communication_protocol_lines(engineer, project.name)
        dispatch_playbook_lines = self.hooks.render_dispatch_playbook_lines(session, project, engineer)
        contract_payload = self.hooks.workspace_contract_payload(
            session,
            project,
            engineer,
            project_engineers=project_engineers,
            engineer_order=engineer_order,
        )
        contract_fingerprint = self.hooks.workspace_contract_fingerprint(contract_payload)

        codex_lines = [
            f"# {session.engineer_id}",
            "",
            f"- Tool: `{session.tool}`",
            f"- Project: `{project.name}`",
            f"- Repo root: `{repo_root}`",
            f"- Workspace: `{session.workspace}`",
            f"- Contract fingerprint: `{contract_fingerprint}`",
        ]
        role_line = self.hooks.render_role_line(engineer, True)
        if role_line:
            codex_lines.append(role_line)
        if engineer.role_details:
            codex_lines.extend(["", *self.hooks.render_role_details_lines(engineer)])
        if engineer.aliases:
            codex_lines.extend(["", *self.hooks.render_aliases_lines(engineer)])
        if authority_lines:
            codex_lines.extend(["", *authority_lines])
        codex_lines.extend(["", *read_first_lines])
        if harness_runtime_lines:
            codex_lines.extend(["", *harness_runtime_lines])
        if project_seat_map_lines:
            codex_lines.extend(["", *project_seat_map_lines])
        codex_lines.extend(["", *seat_boundary_lines, "", *communication_protocol_lines])
        if dispatch_playbook_lines:
            codex_lines.extend(["", *dispatch_playbook_lines])
        codex_lines.extend(
            [
                "",
                f"Use this workspace as the control room. The actual codebase remains at `{repo_root}`.",
            ]
        )
        if engineer.skills:
            codex_lines.extend(["", *self.hooks.render_loaded_skills_lines(engineer, session.engineer_id)])
        codex_lines.extend(_role_skill_section_lines(repo_root, session.engineer_id, role_hint=engineer.role or None))

        tasks_root = getattr(project, "tasks_root", f"{repo_root}/.tasks")
        profile_display = getattr(project, "profile_path", "")
        from resolve import dynamic_profile_path as _dpp
        if not profile_display:
            profile_display = str(_dpp(project.name))

        claude_lines = [
            f"# {session.engineer_id}",
            "",
            f"Managed Claude workspace for project `{project.name}`.",
            "",
            f"Primary repo root: `{repo_root}`",
            f"Task inbox: `{tasks_root}/{session.engineer_id}`",
            f"Profile: `{profile_display}`",
            f"Contract fingerprint: `{contract_fingerprint}`",
        ]
        role_text_line = self.hooks.render_role_line(engineer, False)
        if role_text_line:
            claude_lines.append(role_text_line)
        if engineer.role_details:
            claude_lines.extend(["", *self.hooks.render_role_details_lines(engineer)])
        if engineer.aliases:
            claude_lines.extend(["", *self.hooks.render_aliases_lines(engineer)])
        if authority_lines:
            claude_lines.extend(["", *authority_lines])
        claude_lines.extend(["", *read_first_lines])
        if engineer.skills:
            claude_lines.extend(["", *self.hooks.render_loaded_skills_lines(engineer, session.engineer_id)])
        if harness_runtime_lines:
            claude_lines.extend(["", *harness_runtime_lines])
        if project_seat_map_lines:
            claude_lines.extend(["", *project_seat_map_lines])
        claude_lines.extend(["", *seat_boundary_lines, "", *communication_protocol_lines])
        if dispatch_playbook_lines:
            claude_lines.extend(["", *dispatch_playbook_lines])
        claude_lines.extend(_role_skill_section_lines(repo_root, session.engineer_id, role_hint=engineer.role or None))

        gemini_lines = [
            f"# {session.engineer_id}",
            "",
            f"Managed Gemini workspace for project `{project.name}`.",
            "",
            f"Primary repo root: `{repo_root}`",
            f"Task inbox: `{tasks_root}/{session.engineer_id}`",
            f"Profile: `{profile_display}`",
            f"Contract fingerprint: `{contract_fingerprint}`",
        ]
        if role_text_line:
            gemini_lines.append(role_text_line)
        if engineer.role_details:
            gemini_lines.extend(["", *self.hooks.render_role_details_lines(engineer)])
        if engineer.aliases:
            gemini_lines.extend(["", *self.hooks.render_aliases_lines(engineer)])
        if authority_lines:
            gemini_lines.extend(["", *authority_lines])
        gemini_lines.extend(["", *read_first_lines])
        if engineer.skills:
            gemini_lines.extend(["", *self.hooks.render_loaded_skills_lines(engineer, session.engineer_id)])
        if harness_runtime_lines:
            gemini_lines.extend(["", *harness_runtime_lines])
        if project_seat_map_lines:
            gemini_lines.extend(["", *project_seat_map_lines])
        gemini_lines.extend(["", *seat_boundary_lines, "", *communication_protocol_lines])
        if dispatch_playbook_lines:
            gemini_lines.extend(["", *dispatch_playbook_lines])
        gemini_lines.extend(_role_skill_section_lines(repo_root, session.engineer_id, role_hint=engineer.role or None))

        workspace_notes_lines = [
            "# Workspace Notes",
            "",
            f"This is the managed workspace for `{session.engineer_id}`.",
            "",
            "Useful paths:",
            f"- repo: `{repo_root}`",
        ]
        for label in ("openclaw",):
            candidate = Path(repo_root) / label
            if candidate.exists():
                workspace_notes_lines.append(f"- {label}: `{candidate}`")
        workspace_notes_lines.append(f"- tasks: `{repo_root}/.tasks/{session.engineer_id}`")

        template_map = {
            "codex": {
                "AGENTS.md": "\n".join(codex_lines) + "\n",
                "WORKSPACE_CONTRACT.toml": self.hooks.render_workspace_contract_text(
                    session,
                    project,
                    engineer,
                    project_engineers=project_engineers,
                    engineer_order=engineer_order,
                ),
                "WORKSPACE.md": "\n".join(workspace_notes_lines) + "\n",
            },
            "claude": {
                "AGENTS.md": "\n".join(claude_lines) + "\n",
                # Claude Code reads CLAUDE.md in the project root as the
                # primary system-prompt file; AGENTS.md is only a fallback
                # (and version-dependent). Emitting both means the seat
                # sees its role contract regardless of which one Claude
                # Code picks up on this version.
                "CLAUDE.md": "\n".join(claude_lines) + "\n",
                "WORKSPACE_CONTRACT.toml": self.hooks.render_workspace_contract_text(
                    session,
                    project,
                    engineer,
                    project_engineers=project_engineers,
                    engineer_order=engineer_order,
                ),
                ".claude/settings.local.json": self._render_claude_settings(session, engineer),
            },
            "gemini": {
                "AGENTS.md": "\n".join(gemini_lines) + "\n",
                # Gemini CLI similarly prefers GEMINI.md; write both so
                # the role SKILL is picked up regardless of the CLI
                # version's auto-discovery rules.
                "GEMINI.md": "\n".join(gemini_lines) + "\n",
                "WORKSPACE_CONTRACT.toml": self.hooks.render_workspace_contract_text(
                    session,
                    project,
                    engineer,
                    project_engineers=project_engineers,
                    engineer_order=engineer_order,
                ),
                "WORKSPACE.md": textwrap.dedent(
                    """\
                    # Workspace Notes

                    Use the symlinks in `repos/` to access the live project.
                    """
                ),
            },
        }
        heartbeat_text = self.hooks.render_heartbeat_text(session, project, engineer)
        if heartbeat_text:
            template_map.setdefault(tool, {})["HEARTBEAT.md"] = heartbeat_text
        heartbeat_manifest_text = self.hooks.render_heartbeat_manifest_text(
            session,
            project,
            engineer,
            project_engineers=project_engineers,
            engineer_order=engineer_order,
        )
        if heartbeat_manifest_text:
            template_map.setdefault(tool, {})["HEARTBEAT_MANIFEST.toml"] = heartbeat_manifest_text
        rendered = template_map.get(tool, {})
        if session.engineer_id == "memory":
            claude_memory = self._render_workspace_memory_template(
                "claude",
                session=session,
                project=project,
                profile_display=profile_display,
            )
            gemini_memory = self._render_workspace_memory_template(
                "gemini",
                session=session,
                project=project,
                profile_display=profile_display,
            )
            rendered["AGENTS.md"] = gemini_memory if tool == "gemini" else claude_memory
            rendered["CLAUDE.md"] = claude_memory
            rendered["GEMINI.md"] = gemini_memory
        return rendered

    def apply_template(
        self,
        session: Any,
        project: Any,
        engineer_override: Any | None = None,
        optional_skills: list[dict[str, object]] | None = None,
        project_engineers: dict[str, Any] | None = None,
        engineer_order: list[str] | None = None,
    ) -> None:
        derived_context = None
        if (
            engineer_override is None
            or optional_skills is None
            or project_engineers is None
            or engineer_order is None
        ):
            derived_context = self.hooks.project_template_context(project)
        if engineer_override is None and derived_context:
            engineer_override = derived_context[0].get(session.engineer_id)
        if optional_skills is None and derived_context:
            optional_skills = derived_context[2]
        if project_engineers is None and derived_context:
            project_engineers = derived_context[0]
        if engineer_order is None and derived_context:
            engineer_order = derived_context[1]
        workspace = Path(session.workspace)
        self.hooks.ensure_dir(workspace)
        rendered = self.render_template_text(
            session.tool,
            session,
            project,
            engineer_override=engineer_override,
            project_engineers=project_engineers,
            engineer_order=engineer_order,
        )
        for stale_name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            if stale_name not in rendered:
                stale_path = workspace / stale_name
                if stale_path.exists():
                    stale_path.unlink()
        for relpath, content in rendered.items():
            self.hooks.write_text(workspace / relpath, content)
        matching_optional_skills = [
            skill
            for skill in (optional_skills or [])
            if session.engineer_id in {str(seat).strip() for seat in skill.get("seat_affinity", [])}
        ]
        if matching_optional_skills:
            self.hooks.write_text(
                workspace / "SKILLS_CATALOG.md",
                self.hooks.render_optional_skills_catalog(matching_optional_skills),
            )
        repos_dir = workspace / "repos"
        self.hooks.ensure_dir(repos_dir)
        repo_root = Path(project.repo_root)
        links = {
            "repo": repo_root,
            project.name: repo_root,
        }
        if (repo_root / "openclaw").exists():
            links["openclaw"] = repo_root / "openclaw"
        for name, target in links.items():
            link = repos_dir / name
            if not target.exists():
                continue
            if link.is_symlink():
                existing = link.resolve(strict=False)
                if existing == target:
                    continue
                link.unlink()
            elif link.exists():
                continue
            try:
                link.symlink_to(target)
            except FileExistsError:
                pass
