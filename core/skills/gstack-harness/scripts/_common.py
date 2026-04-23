#!/usr/bin/env python3
"""
_common.py — harness shared module (re-export hub).

Functions are organized into focused submodules:
  _utils.py            — file I/O, subprocess, TOML quoting, path constants
  _feishu.py           — Feishu/Lark messaging, delegation reports
  _task_io.py          — task dispatch/completion file operations
  _heartbeat_helpers.py — heartbeat contract verification

This file re-exports everything for backward compatibility with existing
`from _common import X` statements. New code should import from the
specific submodule when possible.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# ── Re-exports from submodules (backward compat) ─────────────────────

from _utils import (  # noqa: F401 — re-export
    AGENT_HOME,
    AGENTS_ROOT,
    CONSUMED_RE,
    OPENCLAW_AGENTS_ROOT,
    OPENCLAW_CONFIG_PATH,
    OPENCLAW_FEISHU_SEND_SH,
    OPENCLAW_HOME,
    PLACEHOLDER_RE,
    REPO_ROOT,
    SCRIPTS_ROOT,
    TASK_ROW_RE,
    ensure_dir,
    ensure_parent,
    executable_command,
    load_json,
    load_toml,
    q,
    q_array,
    read_text,
    require_success,
    run_command,
    run_command_with_env,
    sanitize_name,
    summarize_status_lines,
    utc_now_iso,
    write_json,
    write_text,
)

from _feishu import (  # noqa: F401 — re-export
    DELEGATION_REPORT_HEADER,
    VALID_DELEGATION_DECISION_HINTS,
    VALID_DELEGATION_LANES,
    VALID_DELEGATION_NEXT_ACTIONS,
    VALID_DELEGATION_REPORT_STATUSES,
    VALID_DELEGATION_USER_GATES,
    _classify_send_failure,
    _is_sandbox_home,
    _lark_cli_env,
    _lark_cli_real_home,
    _real_user_home,
    _resolve_effective_home,
    broadcast_feishu_group_message,
    build_delegation_report_text,
    check_feishu_auth,
    collect_feishu_group_ids_from_config,
    collect_feishu_group_ids_from_sessions,
    collect_feishu_group_keys,
    FeishuGroupResolutionError,
    legacy_feishu_group_broadcast_enabled,
    resolve_feishu_group_strict,
    resolve_primary_feishu_group_id,
    sanitize_report_value,
    send_feishu_user_message,
    stable_dispatch_nonce,
)

from _task_io import (  # noqa: F401 — re-export
    append_consumed_ack,
    append_status_note,
    append_task_to_queue,
    build_completion_message,
    build_notify_message,
    build_notify_payload,
    complete_task_in_queue,
    extract_canonical_verdict,
    extract_prefixed_value,
    file_declares_task,
    find_consumed_ack,
    handoff_assigned,
    upsert_tasks_row,
    write_delivery,
    write_todo,
)

from _heartbeat_helpers import (  # noqa: F401 — re-export
    heartbeat_manifest_fingerprint,
    heartbeat_receipt_is_verified,
    heartbeat_state,
)


# ── HarnessProfile dataclass + profile loading ───────────────────────


@dataclass
class ObservabilityConfig:
    announce_planner_events: bool = False


@dataclass
class HarnessProfile:
    # Canonical project/runtime contract used by the legacy harness path.
    profile_path: Path
    profile_name: str
    template_name: str
    project_name: str
    repo_root: Path
    tasks_root: Path
    project_doc: Path
    tasks_doc: Path
    status_doc: Path
    send_script: Path
    status_script: Path
    patrol_script: Path
    agent_admin: Path
    workspace_root: Path
    handoff_dir: Path
    # Legacy frontstage transport shims. Layered v2 profiles move these
    # semantics to PROJECT_BINDING + machine/tenant config; keep them here
    # only because the legacy harness scripts still need to route koder/openclaw.
    heartbeat_owner: str
    heartbeat_transport: str
    active_loop_owner: str
    default_notify_target: str
    heartbeat_receipt: Path
    seats: list[str]
    heartbeat_seats: list[str]
    seat_roles: dict[str, str]
    seat_overrides: dict[str, dict[str, str]]
    # Legacy/local-override compatibility fields. These are not canonical v2
    # profile schema fields; they survive here so pre-v2 harness/runtime files
    # can still describe which seats were materialized into tmux.
    dynamic_roster_enabled: bool = False
    runtime_seats: list[str] | None = None
    session_root: Path = Path()
    materialized_seats: list[str] | None = None
    bootstrap_seats: list[str] | None = None
    default_start_seats: list[str] | None = None
    compat_legacy_seats: bool = False
    legacy_seats: list[str] | None = None
    legacy_seat_roles: dict[str, str] | None = None
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    def todo_path(self, seat: str) -> Path:
        return self.tasks_root / seat / "TODO.md"

    def delivery_path(self, seat: str) -> Path:
        return self.tasks_root / seat / "DELIVERY.md"

    def handoff_path(self, task_id: str, source: str, target: str) -> Path:
        safe_task = sanitize_name(task_id)
        safe_source = sanitize_name(source)
        safe_target = sanitize_name(target)
        return self.handoff_dir / f"{safe_task}__{safe_source}__{safe_target}.json"

    def workspace_for(self, seat: str) -> Path:
        return self.workspace_root / seat

    def heartbeat_receipt_for(self, seat: str) -> Path:
        return self.workspace_for(seat) / "HEARTBEAT_RECEIPT.toml"

    def declared_project_seats(self) -> list[str]:
        return list(self.seats)

    def tmux_runtime_seats(self) -> list[str]:
        if self.runtime_seats is not None:
            return list(self.runtime_seats)
        if self.materialized_seats is not None:
            return list(self.materialized_seats)
        return self.declared_project_seats()

    def compat_materialized_seats(self) -> list[str]:
        return list(self.materialized_seats or self.seats)

    def frontstage_target_seat(self) -> str:
        return str(self.heartbeat_owner).strip()

    def frontstage_transport_kind(self) -> str:
        return str(self.heartbeat_transport).strip().lower() or "tmux"

    def declared_runtime_seats(self) -> list[str]:
        return self.tmux_runtime_seats()

    def seat_runs_in_tmux(self, seat: str) -> bool:
        if seat == self.frontstage_target_seat() and self.frontstage_transport_kind() == "openclaw":
            return False
        return seat in set(self.tmux_runtime_seats())

    def heartbeat_runs_in_openclaw(self) -> bool:
        return self.frontstage_transport_kind() == "openclaw"


# Pane-text patterns that tell us a TUI is waiting on human interaction
# (OAuth login, workspace trust, bypass warning, approval gate).
# Name kept for backward compat with agent_admin_heartbeat.py — these cover
# claude / codex / gemini.
#
# Marker strings are verified against real CLI output. Sources of truth:
#   - claude-code 2.1.112  (inspected package bundle + live runs)
#   - codex-cli   0.121.0  (inspected bundle + live first-run in isolated HOME)
#   - gemini-cli  0.38.1   (inspected bundle + live first-run in isolated HOME)
# If you upgrade a CLI, re-verify every line below and update tests/
# test_onboarding_markers.py accordingly. Do NOT add markers based on docs
# alone — only strings you can observe in a captured pane.
CLAUDE_ONBOARDING_MARKERS: list[tuple[str, str]] = [
    # ── Claude Code ────────────────────────────────────────────────
    ("Browser didn't open? Use the url below to sign in", "claude_oauth_login"),
    ("Paste code here if prompted >", "claude_oauth_code"),
    ("Login successful. Press Enter to continue", "claude_oauth_continue"),
    ("Accessing workspace:", "claude_workspace_trust"),
    ("Quick safety check:", "claude_workspace_trust"),
    ("WARNING: Claude Code running in Bypass Permissions mode", "claude_bypass_permissions"),
    ("OAuth error:", "claude_oauth_error"),
    # ── Codex (OpenAI) CLI ────────────────────────────────────────
    # First-run auth menu, ChatGPT OAuth (device-code), API key entry, and
    # the directory-trust + approval-gate prompts.
    ("Sign in with ChatGPT", "codex_oauth_login"),
    ("Provide your own API key", "codex_api_login"),
    ("Finish signing in via your browser", "codex_oauth_login"),
    ("If the link doesn't open automatically", "codex_oauth_login"),
    ("Enter this one-time code", "codex_oauth_code"),
    ("Do you trust the contents of this directory?", "codex_workspace_trust"),
    ("Approval requested:", "codex_approval_prompt"),
    ("Approval needed in", "codex_approval_prompt"),
    # ── Gemini CLI ────────────────────────────────────────────────
    # First-run auth menu, Google OAuth wait, and the folder-trust prompt.
    # The Google account picker is a browser step — there is no TUI marker
    # for it, so we do not try to detect it.
    ("Sign in with Google", "gemini_oauth_menu"),
    ("Waiting for authentication", "gemini_oauth_login"),
    ("Do you trust the files in this folder?", "gemini_workspace_trust"),
]


# ── Profile loading ──────────────────────────────────────────────────

def expand_profile_value(value: str) -> Path:
    """Expand {PLACEHOLDER} and ~ in a profile TOML value.

    Sandbox-safe: `~` is resolved against the operator's real HOME via
    core/lib/real_home.real_user_home(), not os.path.expanduser() which
    walks `$HOME` (the seat / ancestor sandbox HOME). Without this,
    profile values like `workspace_root = "~/.agents/workspaces/install"`
    resolve to `<sandbox>/.agents/workspaces/install` and bootstrap's
    _sync_workspaces_host_to_sandbox reports `host_workspace_not_found`.
    """
    defaults = {
        "CLAWSEAT_ROOT": str(REPO_ROOT),
        "AGENTS_ROOT": str(AGENTS_ROOT),
    }

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return os.environ.get(key, defaults.get(key, match.group(0)))

    expanded = PLACEHOLDER_RE.sub(replace, value)
    if expanded.startswith("~/") or expanded == "~":
        # Manual ~ substitution anchored on the operator's real HOME.
        # `_real_user_home` was re-exported from _feishu.py earlier in this
        # module; using it keeps every profile-loaded path sandbox-safe.
        expanded = str(_real_user_home()) + expanded[1:]
    # Path.expanduser() still runs to catch any ~user/ forms not handled above.
    return Path(expanded).expanduser()


def normalize_role(role: str) -> str:
    if role in {"planner", "planner-dispatcher"}:
        return "planner"
    if role in {"memory", "memory-oracle"}:
        return "memory"
    return role or "specialist"


def role_sort_key(seat: str, role: str, *, heartbeat_owner: str = "") -> tuple[int, str]:
    normalized = normalize_role(role)
    priority = {
        "frontstage-supervisor": 0,
        "planner": 1,
        "builder": 2,
        "reviewer": 3,
        "qa": 4,
        "designer": 5,
        "specialist": 50,
    }
    if (heartbeat_owner and seat == heartbeat_owner) or normalized == "frontstage-supervisor":
        return (0, seat)
    return (priority.get(normalized, 50), seat)


def _unique_seats(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        seat = str(value).strip()
        if not seat or seat in seen:
            continue
        seen.add(seat)
        ordered.append(seat)
    return ordered


def discovered_session_data(session_root: Path, project_name: str) -> dict[str, dict[str, Any]]:
    project_root = session_root / project_name
    if not project_root.exists():
        return {}
    discovered: dict[str, dict[str, Any]] = {}
    for session_path in sorted(project_root.glob("*/session.toml")):
        session = load_toml(session_path) or {}
        seat = str(session.get("engineer_id", session_path.parent.name)).strip() or session_path.parent.name
        discovered[seat] = session
    return discovered


def infer_role_from_seat_id(seat: str, fallback: str = "", *, heartbeat_owner: str = "") -> str:
    if fallback:
        return fallback
    if heartbeat_owner and seat == heartbeat_owner:
        return "frontstage-supervisor"
    if seat == "planner":
        return "planner"
    if re.match(r"^[a-z0-9-]+-\d+$", seat):
        return seat.rsplit("-", 1)[0]
    return "specialist"


def resolve_dynamic_seats(
    *,
    heartbeat_owner: str,
    declared_seats: list[str],
    compat_materialized_seats: list[str],
    compat_legacy_seats: bool,
    legacy_seats: list[str],
    discovered_sessions: dict[str, dict[str, Any]],
    seat_roles: dict[str, str],
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    groups = [
        [heartbeat_owner],
        declared_seats,
        compat_materialized_seats,
        legacy_seats if compat_legacy_seats else [],
        sorted(
            discovered_sessions.keys(),
            key=lambda seat: role_sort_key(
                seat,
                seat_roles.get(seat, ""),
                heartbeat_owner=heartbeat_owner,
            ),
        ),
    ]
    for group in groups:
        for seat in group:
            if not seat or seat in seen:
                continue
            seen.add(seat)
            ordered.append(seat)
    return ordered


def load_profile(path: str | Path) -> HarnessProfile:
    try:
        import tomllib as _tomllib
    except ModuleNotFoundError:
        import tomli as _tomllib  # type: ignore

    profile_path = Path(path).expanduser().resolve()
    data = _tomllib.loads(profile_path.read_text(encoding="utf-8"))
    dynamic = data.get("dynamic_roster", {})
    if not isinstance(dynamic, dict):
        dynamic = {}
    dynamic_enabled = bool(dynamic.get("enabled", False))
    session_root = expand_profile_value(str(dynamic.get("session_root", AGENTS_ROOT / "sessions")))
    # Legacy harness loader: keep reading the old frontstage/runtime transport
    # hints here because local override TOMLs and pre-v2 profiles still carry
    # them. Layered v2 profiles intentionally removed these keys from the
    # canonical schema.
    compat_frontstage_owner = str(data.get("heartbeat_owner", "koder"))
    compat_frontstage_transport = (
        str(data.get("heartbeat_transport", "tmux")).strip().lower() or "tmux"
    )
    if compat_frontstage_transport not in {"tmux", "openclaw"}:
        raise ValueError(
            f"invalid heartbeat_transport {compat_frontstage_transport!r} in {profile_path}; "
            "expected 'tmux' or 'openclaw'"
        )
    legacy_seat_roles = {
        str(key): str(value)
        for key, value in data.get("legacy_seat_roles", {}).items()
    }
    legacy_seats = [str(item) for item in data.get("legacy_seats", list(legacy_seat_roles.keys()))]
    declared_seats = [str(item) for item in data.get("seats", [])]
    compat_materialized_seats = [
        str(item)
        for item in dynamic.get("materialized_seats", declared_seats)
    ]
    compat_bootstrap_seats = [
        str(item)
        for item in dynamic.get("bootstrap_seats", [compat_frontstage_owner])
    ]
    compat_default_start_seats = [
        str(item)
        for item in dynamic.get(
            "default_start_seats",
            compat_bootstrap_seats or compat_materialized_seats,
        )
    ]
    compat_runtime_seats_raw = dynamic.get("runtime_seats")
    if compat_runtime_seats_raw is None:
        compat_runtime_seats = list(compat_materialized_seats or declared_seats)
        if compat_frontstage_transport == "openclaw":
            compat_runtime_seats = [
                seat for seat in compat_runtime_seats if seat != compat_frontstage_owner
            ]
    else:
        compat_runtime_seats = [str(item) for item in compat_runtime_seats_raw]
    compat_legacy_seats = bool(dynamic.get("compat_legacy_seats", False))
    discovered = discovered_session_data(session_root, str(data["project_name"])) if dynamic_enabled else {}
    seat_roles = {str(k): str(v) for k, v in data.get("seat_roles", {}).items()}
    seat_roles.update(legacy_seat_roles)
    for seat, session in discovered.items():
        role = str(session.get("role", "")).strip()
        seat_roles[seat] = infer_role_from_seat_id(
            seat,
            fallback=role or seat_roles.get(seat, ""),
            heartbeat_owner=compat_frontstage_owner,
        )
    seats = (
        resolve_dynamic_seats(
            heartbeat_owner=compat_frontstage_owner,
            declared_seats=declared_seats,
            compat_materialized_seats=compat_materialized_seats,
            compat_legacy_seats=compat_legacy_seats,
            legacy_seats=legacy_seats,
            discovered_sessions=discovered,
            seat_roles=seat_roles,
        )
        if dynamic_enabled
        else [str(item) for item in data.get("seats", [])]
    )
    compat_runtime_seats = _unique_seats(compat_runtime_seats)
    return HarnessProfile(
        profile_path=profile_path,
        profile_name=str(data["profile_name"]),
        template_name=str(data["template_name"]),
        project_name=str(data["project_name"]),
        repo_root=expand_profile_value(str(data["repo_root"])),
        tasks_root=expand_profile_value(str(data["tasks_root"])),
        project_doc=expand_profile_value(str(data["project_doc"])),
        tasks_doc=expand_profile_value(str(data["tasks_doc"])),
        status_doc=expand_profile_value(str(data["status_doc"])),
        send_script=expand_profile_value(str(data["send_script"])),
        # v0.4 migration stripped these fields (see schema §7). Provide
        # sane defaults so v2 profiles load cleanly:
        #   active_loop_owner → "planner" (the only active seat in v0.4)
        #   default_notify_target → "planner"
        #   status_script / patrol_script / heartbeat_receipt → empty
        status_script=expand_profile_value(str(data.get("status_script", ""))),
        patrol_script=expand_profile_value(str(data.get("patrol_script", ""))),
        agent_admin=expand_profile_value(str(data["agent_admin"])),
        workspace_root=expand_profile_value(str(data["workspace_root"])),
        handoff_dir=expand_profile_value(str(data["handoff_dir"])),
        heartbeat_owner=compat_frontstage_owner,
        heartbeat_transport=compat_frontstage_transport,
        active_loop_owner=str(data.get("active_loop_owner", "planner")),
        default_notify_target=str(data.get("default_notify_target", "planner")),
        heartbeat_receipt=expand_profile_value(str(data.get("heartbeat_receipt", ""))),
        seats=seats,
        runtime_seats=compat_runtime_seats,
        heartbeat_seats=[str(item) for item in data.get("heartbeat_seats", [])],
        seat_roles=seat_roles,
        seat_overrides={
            str(seat_id): {str(k): str(v) for k, v in values.items()}
            for seat_id, values in data.get("seat_overrides", {}).items()
        },
        dynamic_roster_enabled=dynamic_enabled,
        session_root=session_root,
        materialized_seats=compat_materialized_seats,
        bootstrap_seats=compat_bootstrap_seats,
        default_start_seats=compat_default_start_seats,
        compat_legacy_seats=compat_legacy_seats,
        legacy_seats=legacy_seats,
        legacy_seat_roles=legacy_seat_roles,
        observability=ObservabilityConfig(
            announce_planner_events=bool(
                data.get("observability", {}).get("announce_planner_events", False)
            )
        ),
    )


# ── Session / tmux helpers ───────────────────────────────────────────

def notify(profile: HarnessProfile, target_seat: str, message: str) -> subprocess.CompletedProcess[str]:
    session_name = resolve_session_name(profile, target_seat)
    # C6: always thread --project so multi-project installs don't let
    # send-and-verify.sh fall through to agentctl's unscoped session-name
    # lookup (which would pick any project with a matching seat id and
    # silently deliver to the wrong tmux window).
    return run_command_with_env(
        [str(profile.send_script), "--project", profile.project_name, session_name, message],
        cwd=profile.repo_root,
        env={"HOME": str(AGENT_HOME)},
    )


def resolve_session_name(profile: HarnessProfile, seat: str) -> str:
    session_toml = AGENTS_ROOT / "sessions" / profile.project_name / seat / "session.toml"
    session_data = load_toml(session_toml)
    if session_data:
        session_name = str(session_data.get("session", "")).strip()
        if session_name:
            return session_name
    return seat


def session_path_for(profile: HarnessProfile, seat: str) -> Path:
    agents_root = profile.workspace_root.parent.parent
    return agents_root / "sessions" / profile.project_name / seat / "session.toml"


def session_name_for(profile: HarnessProfile, seat: str) -> str | None:
    session_path = session_path_for(profile, seat)
    session_data = load_toml(session_path)
    if not session_data:
        return None
    session_name = str(session_data.get("session", "")).strip()
    return session_name or None


def capture_session_pane(profile: HarnessProfile, seat: str, *, lines: int = 160) -> str:
    session_name = session_name_for(profile, seat)
    if not session_name:
        return ""
    result = run_command(
        ["tmux", "capture-pane", "-t", session_name, "-p"],
        cwd=profile.repo_root,
    )
    if result.returncode != 0:
        return ""
    pane_text = result.stdout
    if not pane_text:
        return ""
    return "\n".join(pane_text.splitlines()[-lines:])


def detect_claude_onboarding_step(pane_text: str) -> str | None:
    for marker, step in CLAUDE_ONBOARDING_MARKERS:
        if marker in pane_text:
            return step
    return None


# ── Seat/runtime helpers ─────────────────────────────────────────────

def tracked_runtime_seats(profile: HarnessProfile) -> list[str]:
    return list(profile.tmux_runtime_seats())


def heartbeat_manifest_path(profile: HarnessProfile, seat: str) -> Path:
    return profile.workspace_for(seat) / "HEARTBEAT_MANIFEST.toml"


def heartbeat_md_path(profile: HarnessProfile, seat: str) -> Path:
    return profile.workspace_for(seat) / "HEARTBEAT.md"


def is_managed_runtime_path(profile: HarnessProfile, path: Path) -> bool:
    try:
        path.resolve().relative_to(profile.tasks_root.resolve())
        return True
    except ValueError:
        return False


def make_local_override(profile: HarnessProfile, *, project_name: str, repo_root: Path) -> Path:
    seat_order = list(profile.compat_materialized_seats())
    tmux_runtime_seats = list(profile.tmux_runtime_seats())
    lines = [
        "version = 1",
        "",
        f'project_name = "{project_name}"',
        f'repo_root = "{repo_root}"',
        "# Local override / legacy harness compatibility fields.",
        "# Layered v2 profiles do not store these keys directly.",
        f"seat_order = {json.dumps(seat_order)}",
        f"materialized_seats = {json.dumps(seat_order)}",
        f"runtime_seats = {json.dumps(tmux_runtime_seats)}",
        f"bootstrap_seats = {json.dumps(list(profile.bootstrap_seats or []))}",
        f"default_start_seats = {json.dumps(list(profile.default_start_seats or []))}",
        f'heartbeat_transport = "{profile.frontstage_transport_kind()}"',
    ]
    for seat_id, override in profile.seat_overrides.items():
        if not override:
            continue
        lines.extend(["", "[[overrides]]", f'id = "{seat_id}"'])
        for key, value in override.items():
            lines.append(f'{key} = "{value}"')
    payload = "\n".join(lines) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=f"{sanitize_name(project_name)}-", suffix=".toml")
    tmp_path = Path(tmp)
    os.close(fd)
    write_text(tmp_path, payload)
    return tmp_path


# ── Rendering ────────────────────────────────────────────────────────

def render_project_doc(profile: HarnessProfile) -> str:
    role_lines = []
    for seat in profile.seats:
        role = profile.seat_roles.get(seat, "specialist")
        role_lines.append(f"- `{seat}` = `{role}`")
    chain_owner = profile.active_loop_owner if profile.active_loop_owner in profile.seats else "planner"
    return (
        f"# {profile.project_name} Harness Project\n\n"
        "This project is managed by `gstack-harness`.\n\n"
        "## Seats\n\n"
        + "\n".join(role_lines)
        + "\n\n## Chain\n\n"
        + (
            f"`user -> {profile.heartbeat_owner} -> {chain_owner} -> specialist -> "
            f"{chain_owner} -> ... -> {profile.heartbeat_owner} -> user`\n"
            if chain_owner != profile.heartbeat_owner
            else f"`user -> {profile.heartbeat_owner} -> specialist -> {profile.heartbeat_owner} -> user`\n"
        )
    )


def render_tasks_doc() -> str:
    return "# Tasks\n\n| ID | Title | Owner | Status | Notes |\n|----|-------|-------|--------|-------|\n"


def render_status_doc() -> str:
    return "# Status\n"


def render_idle_todo(profile: HarnessProfile, seat: str) -> str:
    role = profile.seat_roles.get(seat, "specialist")
    if seat == profile.heartbeat_owner:
        reply_to = profile.default_notify_target
        title = "等待项目启动与群联调"
        objective = (
            f"{seat} template已初始化。若当前项目走 OpenClaw/Feishu 链路，且 planner 已经启动，"
            "请主动要求用户让 main agent 拉群并回报 group ID。无需 open_id。"
            "main 在群里保持 requireMention=true；项目面向前台的 koder 账号在该群里默认设为 requireMention=false，"
            "只有显式部署的系统 seat（如 warden）才需要额外放开。"
            "拿到 group ID 后，先确认该群绑定当前项目、已有项目还是新项目，再委派 planner 做飞书联调测试，"
            "提示用户\u201c收到测试消息即可回复希望完成什么任务\u201d，并并行拉起 reviewer 进入审查待命。"
        )
    elif seat == profile.active_loop_owner or role in {"planner", "planner-dispatcher"}:
        reply_to = profile.heartbeat_owner
        title = "等待 frontstage intake / 初始化广播"
        objective = (
            f"{seat} template已初始化。当前没有已派发任务。若你刚完成 planner 初始化，"
            "请尽快把 ready 状态回给 koder/frontstage，方便其完成项目绑定与 Feishu 群联调；"
            "若 frontstage 提供了 group ID 和项目绑定，请先完成群联调测试并向用户发送首条测试消息，提示其收到后直接回复希望完成什么任务；"
            "若当前链路是测试、验证、smoke 或回归重任务，请同步拉起 qa-1 作为验证席位；"
            "否则先阅读 WORKSPACE_CONTRACT.toml 与 workspace guide，等待新的 dispatch。"
        )
    else:
        reply_to = profile.active_loop_owner
        title = "等待任务派发"
        objective = (
            f"{seat} template已初始化。当前没有已派发任务，先阅读 WORKSPACE_CONTRACT.toml 与 workspace guide，随后等待新的 dispatch。"
        )
    return (
        "task_id: null\n"
        f"project: {profile.project_name}\n"
        f"owner: {seat}\n"
        "status: pending\n"
        f"title: {title}\n\n"
        f"# Objective\n\n{objective}\n\n"
        "# Dispatch\n\n"
        "source: null\n"
        f"reply_to: {reply_to}\n"
    )


def render_status_wrapper(profile: HarnessProfile) -> str:
    seats = " ".join(tracked_runtime_seats(profile))
    return (
        "#!/bin/bash\n"
        "set -euo pipefail\n\n"
        f"export TASKS_ROOT={profile.tasks_root}\n"
        f"export PATROL_DIR={profile.tasks_root / 'patrol'}\n"
        f"export DEFAULT_SESSIONS=\"{seats}\"\n\n"
        f"export AGENT_PROJECT=\"{profile.project_name}\"\n\n"
        f'exec {SCRIPTS_ROOT / "check-engineer-status.sh"} "$@"\n'
    )


def render_patrol_wrapper(profile: HarnessProfile) -> str:
    return (
        "#!/bin/bash\n"
        "set -euo pipefail\n\n"
        f'exec python3 {REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts" / "patrol_supervisor.py"} --profile {profile.profile_path} "$@"\n'
    )


def render_heartbeat_md(profile: HarnessProfile, seat: str) -> str:
    role = profile.seat_roles.get(seat, "frontstage-supervisor")
    patrol_entry = profile.patrol_script
    status_entry = profile.status_script
    return (
        f"# {seat} heartbeat\n\n"
        f"Runtime seat id: `{seat}`\n"
        f"Canonical role: `{role}`\n\n"
        "Provisioning assets:\n\n"
        "- `HEARTBEAT_MANIFEST.toml` is the desired heartbeat contract.\n"
        "- `HEARTBEAT_RECEIPT.toml` is the framework-owned verified install receipt.\n\n"
        "When a scheduled heartbeat poll arrives:\n\n"
        "1. Stay in lightweight patrol mode; do not enter plan mode for a routine heartbeat run.\n"
        "2. Do not reload broad project strategy docs unless the classifier or patrol script returns an ambiguous contradiction that cannot be resolved from the scripted facts.\n"
        f"3. Run `{status_entry}` as the first-pass classifier.\n"
        f"4. Run `{patrol_entry}` to decide whether `{profile.active_loop_owner}` needs a reminder.\n"
        "5. If there is no meaningful state change, reply exactly `HEARTBEAT_OK`.\n"
        "6. If patrol shows a real delivery-not-consumed or stalled-seat condition, use the frontstage unblock authority to clear the procedural wait and remind the active loop owner if needed.\n"
        f"7. Only if the scripts fail or disagree, read the smallest necessary docs (`{profile.tasks_doc}` / `{profile.status_doc}` first) and return a short blocker summary instead of loading the full frontstage context.\n\n"
        "Reliable handoff model:\n\n"
        "- `assigned` = target `TODO.md` exists\n"
        "- `notified` = `send-and-verify.sh` returned success\n"
        "- `consumed` = target seat durable ACK exists in `TODO.md`\n"
        "- only `assigned + notified + consumed` counts as a healthy handoff\n\n"
        "Review verdict routing matrix:\n\n"
        f"- `APPROVED` / `APPROVED_WITH_NITS` -> `{profile.heartbeat_owner}`\n"
        "- `CHANGES_REQUESTED` -> builder seat (from profile `seat_roles`, or `active_loop_owner`)\n"
        f"- `BLOCKED` / `DECISION_NEEDED` -> `{profile.heartbeat_owner}`\n"
        f"- Reviewer seat delivers verdicts; `{profile.active_loop_owner}` chooses the next hop\n\n"
        "Guardrails:\n\n"
        f"- `{profile.active_loop_owner}` remains the active loop owner and decision owner.\n"
        f"- `{profile.heartbeat_owner}` owns confirmations, approvals, reminders, and other procedural unblock actions.\n"
        "- Do not write downstream specialist TODOs from a heartbeat run.\n"
        "- Keep heartbeat replies short and factual; avoid restating full project context on every poll.\n"
        "- If there is no real reminder to send, stay silent with `HEARTBEAT_OK`.\n"
    )


def render_heartbeat_manifest(profile: HarnessProfile, seat: str) -> str:
    commands = [
        str(profile.patrol_script),
        f"{profile.patrol_script} --send",
    ]
    workspace = profile.workspace_for(seat)
    receipt = profile.heartbeat_receipt_for(seat)
    lines = [
        "version = 1",
        f'seat_id = "{seat}"',
        f'project = "{profile.project_name}"',
        f'role = "{profile.seat_roles.get(seat, "frontstage-supervisor")}"',
        'kind = "heartbeat"',
        "enabled = true",
        "interval_minutes = 15",
        f'active_loop_owner = "{profile.active_loop_owner}"',
        'expected_idle_reply = "HEARTBEAT_OK"',
        f'workspace = "{workspace}"',
        f'repo_root = "{profile.repo_root}"',
        f'receipt_path = "{receipt}"',
        f'patrol_entrypoint = "{profile.status_script}"',
        f'supervisor_entrypoint = "{profile.patrol_script}"',
        f'send_script = "{profile.send_script}"',
        f'commands = {json.dumps(commands, ensure_ascii=False)}',
        "",
    ]
    return "\n".join(lines)


# ── Runtime materialization ──────────────────────────────────────────

def _patch_claude_settings_from_profile(profile: HarnessProfile, seats: list[str]) -> None:
    """Patch Claude settings with model, effortLevel, and hasCompletedOnboarding."""
    template_path = REPO_ROOT / "core" / "templates" / profile.template_name / "template.toml"
    if not template_path.exists():
        return
    template_data = load_toml(template_path)
    engineer_map: dict[str, dict] = {}
    for eng in template_data.get("engineers", []):
        engineer_map[str(eng.get("id", ""))] = eng

    sessions_root = Path(os.environ.get("SESSIONS_ROOT", str(AGENTS_ROOT / "sessions")))

    _admin_scripts = REPO_ROOT / "core" / "scripts"
    _provider_configs: dict = {}
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location("agent_admin_config", _admin_scripts / "agent_admin_config.py")
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            import sys as _sys
            _sys.modules.setdefault("agent_admin_config", _mod)
            _spec.loader.exec_module(_mod)
            _provider_configs = getattr(_mod, "CLAUDE_API_PROVIDER_CONFIGS", {})
    except (ImportError, FileNotFoundError, OSError, AttributeError) as exc:
        # silent-ok: agent_admin_config is optional; fall back to empty provider list.
        import sys
        print(f"warn: agent_admin_config load failed: {exc}", file=sys.stderr)

    for seat in seats:
        spec = engineer_map.get(seat, {})
        model = str(spec.get("model", "")).strip()
        effort = str(spec.get("effort", "")).strip()
        auth_mode = str(spec.get("auth_mode", "")).strip()
        provider = str(spec.get("provider", "")).strip()
        session_path = sessions_root / profile.project_name / seat / "session.toml"
        runtime_dir = None
        if session_path.exists():
            session_data = load_toml(session_path)
            auth_mode = str(session_data.get("auth_mode", auth_mode)).strip()
            provider = str(session_data.get("provider", provider)).strip()
            runtime_dir = str(session_data.get("runtime_dir", "")).strip()
            tool = str(session_data.get("tool", "")).strip()
            if tool and tool != "claude":
                continue

        settings_path = profile.workspace_for(seat) / ".claude" / "settings.local.json"
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                settings = {}
            changed = False
            if model and settings.get("model") != model:
                settings["model"] = model
                changed = True
            if auth_mode == "api" and not settings.get("hasCompletedOnboarding"):
                settings["hasCompletedOnboarding"] = True
                changed = True
            if changed:
                write_text(settings_path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")

        if runtime_dir:
            runtime_settings_path = Path(runtime_dir) / "home" / ".claude" / "settings.json"
            ensure_parent(runtime_settings_path)
            try:
                rt_settings = json.loads(runtime_settings_path.read_text(encoding="utf-8")) if runtime_settings_path.exists() else {}
            except (json.JSONDecodeError, OSError):
                rt_settings = {}
            rt_changed = False
            if model and rt_settings.get("model") != model:
                rt_settings["model"] = model
                rt_changed = True
            if effort and rt_settings.get("effortLevel") != effort:
                rt_settings["effortLevel"] = effort
                rt_changed = True
            if "skipDangerousModePermissionPrompt" not in rt_settings:
                rt_settings["skipDangerousModePermissionPrompt"] = True
                rt_changed = True
            prov_config = _provider_configs.get(provider, {})
            extra_env = prov_config.get("extra_env")
            if extra_env:
                env_block = rt_settings.get("env", {})
                if not isinstance(env_block, dict):
                    env_block = {}
                for env_key, env_val in extra_env.items():
                    if env_block.get(env_key) != env_val:
                        env_block[env_key] = env_val
                        rt_changed = True
                if env_block:
                    rt_settings["env"] = env_block
            if rt_changed:
                write_text(runtime_settings_path, json.dumps(rt_settings, indent=2, ensure_ascii=False) + "\n")


def materialize_profile_runtime(profile: HarnessProfile) -> None:
    ensure_dir(profile.tasks_root)
    ensure_dir(profile.handoff_dir)
    all_seats: list[str] = []
    for seat in [*profile.compat_materialized_seats(), *profile.declared_project_seats()]:
        if seat and seat not in all_seats:
            all_seats.append(seat)
    for seat in all_seats:
        ensure_dir(profile.tasks_root / seat)
        todo_path = profile.todo_path(seat)
        if not todo_path.exists():
            write_text(todo_path, render_idle_todo(profile, seat))
    if not profile.project_doc.exists():
        write_text(profile.project_doc, render_project_doc(profile))
    if not profile.tasks_doc.exists():
        write_text(profile.tasks_doc, render_tasks_doc())
    if not profile.status_doc.exists():
        write_text(profile.status_doc, render_status_doc())
    if is_managed_runtime_path(profile, profile.status_script):
        write_text(profile.status_script, render_status_wrapper(profile))
        profile.status_script.chmod(0o755)
    if is_managed_runtime_path(profile, profile.patrol_script):
        write_text(profile.patrol_script, render_patrol_wrapper(profile))
        profile.patrol_script.chmod(0o755)
    _patch_claude_settings_from_profile(profile, all_seats)
    for seat in profile.heartbeat_seats:
        # Skip heartbeat manifest/md for seats that don't run in tmux — the
        # generated docs describe a tmux-only patrol transport (status_script,
        # patrol_script, send_script) that cannot reach an openclaw frontstage.
        if not profile.seat_runs_in_tmux(seat):
            continue
        ensure_dir(profile.workspace_for(seat))
        write_text(heartbeat_md_path(profile, seat), render_heartbeat_md(profile, seat))
        write_text(heartbeat_manifest_path(profile, seat), render_heartbeat_manifest(profile, seat))


# ── Secret seeding ───────────────────────────────────────────────────

GLOBAL_ENV_PATH = AGENTS_ROOT / ".env.global"

GLOBAL_SECRET_MAP: dict[tuple[str, str], dict[str, str]] = {
    ("claude", "minimax"): {
        "ANTHROPIC_AUTH_TOKEN": "MINIMAX_API_KEY",
        "ANTHROPIC_BASE_URL": "MINIMAX_BASE_URL",
    },
    ("claude", "xcode-best"): {
        "ANTHROPIC_API_KEY": "XCODE_BEST_API_KEY",
        "ANTHROPIC_BASE_URL": "XCODE_BEST_CLAUDE_BASE_URL",
    },
    ("codex", "xcode-best"): {
        "OPENAI_API_KEY": "XCODE_BEST_API_KEY",
    },
}


def _load_global_env() -> dict[str, str]:
    if not GLOBAL_ENV_PATH.exists():
        return {}
    result: dict[str, str] = {}
    for line in GLOBAL_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def seed_empty_secret_from_peer(profile: HarnessProfile, seat: str) -> Path | None:
    agents_root = profile.workspace_root.parent.parent
    session_path = agents_root / "sessions" / profile.project_name / seat / "session.toml"
    if not session_path.exists():
        return None
    session_data = load_toml(session_path)
    secret_file_raw = str(session_data.get("secret_file", "")).strip()
    if not secret_file_raw:
        return None
    secret_file = Path(secret_file_raw).expanduser()
    ensure_parent(secret_file)
    if secret_file.exists() and secret_file.stat().st_size > 0:
        return None
    provider_dir = secret_file.parent
    if provider_dir.exists():
        for peer in sorted(provider_dir.glob("*.env")):
            if peer == secret_file or peer.stat().st_size == 0:
                continue
            # Validate peer secret has at least one KEY=VALUE line with non-empty value
            peer_content = peer.read_text(encoding="utf-8").strip()
            has_valid_key = False
            for line in peer_content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    _k, _, _v = line.partition("=")
                    if _k.strip() and _v.strip().strip('"').strip("'"):
                        has_valid_key = True
                        break
            if not has_valid_key:
                print(f"secret_seed_skipped: {peer} has no valid KEY=VALUE entries", file=__import__('sys').stderr)
                continue
            shutil.copy2(peer, secret_file)
            secret_file.chmod(0o600)
            return peer
    tool = str(session_data.get("tool", "")).strip()
    provider = str(session_data.get("provider", "")).strip()
    mapping = GLOBAL_SECRET_MAP.get((tool, provider))
    if mapping:
        global_env = _load_global_env()
        lines = []
        for seat_var, global_var in mapping.items():
            value = global_env.get(global_var, "")
            if value:
                lines.append(f'{seat_var}="{value}"')
        if lines:
            ensure_parent(secret_file)
            write_text(secret_file, "\n".join(lines) + "\n")
            secret_file.chmod(0o600)
            return GLOBAL_ENV_PATH
    return None


# NOTE: OAuth auth is the user's job, done interactively in the TUI pane.
# ClawSeat's only job is to spin up tmux + CLI + iTerm tab; credentials
# live in whatever CODEX_HOME / HOME / XDG dirs the CLI manages itself.
# We intentionally DO NOT seed or copy oauth tokens across identities.


# ── Memory-seat target guard (T9) ─────────────────────────────────────
#
# Memory is a synchronous oracle, not a task worker. It runs a `/clear`
# Stop hook so every turn starts with no LLM context; its knowledge
# lives on disk under ~/.agents/memory/*.json and is re-read on demand.
#
# Dispatching a task (TODO.md + tmux notify) or sending a free-form
# notification to memory therefore fails silently: by the time the
# notify text lands in the tmux pane, memory has already /clear'd and
# cannot see the TODO queue. Callers must instead use the read-only
# query_memory.py tool, which writes a prompt file the UserPromptSubmit
# hook can inject a fresh context for.
#
# This guard lives in _common.py so both dispatch_task.py and
# notify_seat.py pick it up from the same import surface they already
# use. See core/skills/clawseat-install/references/memory-query-protocol.md
# for the full seat→memory contract.

MEMORY_SEAT_NAME = "memory"

MEMORY_QUERY_POINTER = (
    "To interact with memory, use the read-only query tool:\n"
    "  python3 $CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py \\\n"
    "    --ask \"<question>\" --profile <profile>\n"
    "\n"
    "Or for a direct key / file lookup:\n"
    "  python3 $CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py \\\n"
    "    --key <dot.path>\n"
    "  python3 $CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py \\\n"
    "    --file <file-stem> --section <section>\n"
    "\n"
    "See core/skills/clawseat-install/references/memory-query-protocol.md"
)


def assert_target_not_memory(target: str, caller_tool: str) -> None:
    """Exit 2 if ``target`` is the memory seat.

    Both dispatch_task.py and notify_seat.py call this after argparse,
    before writing any TODO / receipt / tmux notification. The exit code
    mirrors argparse's own exit code for bad invocations so scripted
    callers can treat "bad target" and "bad flag" uniformly.

    T22 (folded into T19 PR-2 for merge convenience):
    notify_seat.py is allowed to target memory because T7 memory-query-protocol
    Missing-Key Escalation requires it — memory needs to receive notification
    when a key it asked for is missing. dispatch_task.py + dynamic variants
    remain blocked because memory doesn't read TODO.md entries.
    """
    import sys as _sys

    if target == MEMORY_SEAT_NAME and caller_tool != "notify_seat.py":
        print(
            f"error: {caller_tool} does not support --target memory.\n"
            "       Memory is a synchronous oracle; dispatching writes TODO\n"
            "       entries the target cannot read because its context is\n"
            "       cleared between turns (/clear Stop hook).\n"
            "\n"
            f"{MEMORY_QUERY_POINTER}",
            file=_sys.stderr,
        )
        raise SystemExit(2)


def add_notify_args(parser: "argparse.ArgumentParser") -> None:
    """Add --notify / --no-notify / --skip-notify (deprecated) to *parser*.

    C15: notify is default-ON. --no-notify opts out. --skip-notify is the
    legacy alias kept for backwards compatibility (logs a deprecation warning).
    Call this helper from both static and dynamic dispatch/handoff scripts so
    the semantics stay in sync via BASE_COMMON re-export.
    """
    import argparse as _argparse  # noqa: F401 — only needed for the type hint above
    notify_group = parser.add_mutually_exclusive_group()
    notify_group.add_argument(
        "--notify", action="store_true", default=None,
        help="Send tmux notify to target after dispatch/completion (default).",
    )
    notify_group.add_argument(
        "--no-notify", action="store_true",
        help="Suppress tmux notify. Target must discover the task by reading its queue/DELIVERY.md.",
    )
    # Legacy alias — accepted but logs deprecation warning to stderr.
    parser.add_argument(
        "--skip-notify", action="store_true",
        help="[deprecated] Use --no-notify. Kept for backwards compatibility.",
    )


def resolve_notify(args: "argparse.Namespace") -> bool:
    """Resolve the effective notify flag from parsed args.

    Returns True (notify) by default; False when --no-notify or --skip-notify given.
    Prints a deprecation warning to stderr when --skip-notify is used.
    """
    import sys as _sys
    do_notify = True
    if getattr(args, "no_notify", False) or getattr(args, "skip_notify", False):
        do_notify = False
    if getattr(args, "skip_notify", False):
        print("warn: --skip-notify is deprecated; use --no-notify", file=_sys.stderr)
    return do_notify


# ── C16: token-usage watermark helpers ──────────────────────────────────────

_TOKEN_MAX_MODELS: dict[str, int] = {
    "opus-4-7": 200_000,
    "claude-opus-4-7": 200_000,
    "sonnet-4-6": 200_000,
    "claude-sonnet-4-6": 200_000,
    "haiku-4-5": 200_000,
    "claude-haiku-4-5": 200_000,
    # Opus 1M variant
    "claude-opus-4-7-1m": 1_000_000,
}
_TOKEN_MAX_DEFAULT = 200_000
_BYTES_PER_TOKEN = 8  # safe upper bound: 1 token ≈ 4 bytes prose + JSON overhead


def _infer_max_tokens(model: str) -> int:
    """Hardcoded context-window size per model. ~30% error bar heuristic."""
    m = model.lower().strip()
    # Generic 1M detection (check before exact-key loop so "1m" in model name wins)
    if "1m" in m and "opus" in m:
        return 1_000_000
    # Longest key first to ensure more-specific variants win
    for key, tokens in sorted(_TOKEN_MAX_MODELS.items(), key=lambda kv: -len(kv[0])):
        if key in m:
            return tokens
    return _TOKEN_MAX_DEFAULT


def _find_session_jsonls(runtime_dir: str | None, workspace: "Path") -> list["Path"]:
    """Locate session.jsonl files for the seat's active CC session.

    Searches (in order):
    1. runtime_dir/home/.claude/projects/-*/*.jsonl
    2. workspace/.claude/projects/-*/*.jsonl
    """
    candidates: list[Path] = []
    for base in [
        Path(runtime_dir) / "home" / ".claude" / "projects" if runtime_dir else None,
        workspace / ".claude" / "projects",
    ]:
        if base is None or not base.exists():
            continue
        candidates.extend(base.glob("-*/*.jsonl"))
    return candidates


def _compute_pct_from_jsonl(jsonl_path: "Path", model: str = "") -> tuple[float, str]:
    """Compute token usage pct from a session.jsonl file size.

    Heuristic: 1 token ≈ 8 bytes. ~30% error bar.
    Intended to catch egregious cases (75%+), not pixel-accurate.
    """
    size_bytes = jsonl_path.stat().st_size
    max_tokens = _infer_max_tokens(model)
    approx_tokens = size_bytes / _BYTES_PER_TOKEN
    pct = min(1.0, approx_tokens / max_tokens)
    return pct, "session_jsonl_size"


def measure_token_usage_pct(
    profile: "HarnessProfile",
    seat: str,
    *,
    _session_jsonl_override: "Path | None" = None,
    _model_override: str = "",
) -> tuple[float | None, str]:
    """Best-effort token usage for a seat's active CC session.

    Sources tried in order:
    1. CC_CONTEXT_USAGE_PCT env var (future CC feature)
    2. session.jsonl size / (max_tokens * _BYTES_PER_TOKEN)
    3. Fallback: (None, 'unknown')

    Heuristic: 1 token ≈ 8 bytes (JSON overhead makes this a safe upper bound).
    ~30% error bar — intended for egregious cases, not pixel-accurate accounting.

    Args:
        _session_jsonl_override: For testing only — skip path discovery, use this file.
        _model_override: For testing only — override model for max_token inference.
    """
    import os as _os

    # Source 1: env var (forward-compat: CC may expose this natively one day)
    env_pct = _os.environ.get("CC_CONTEXT_USAGE_PCT", "").strip()
    if env_pct:
        try:
            return (min(1.0, max(0.0, float(env_pct))), "cc_env")
        except ValueError:  # silent-ok: malformed env var → fall through to next source
            pass

    # Source 2: session.jsonl size
    try:
        if _session_jsonl_override is not None:
            jsonl = _session_jsonl_override
            model = _model_override
        else:
            # Locate runtime_dir via session.toml
            agents_root = Path(_os.environ.get("AGENTS_ROOT", str(_real_user_home() / ".agents")))
            sessions_root = agents_root / "sessions"
            session_toml_path = sessions_root / profile.project_name / seat / "session.toml"
            runtime_dir = None
            model = _model_override
            if session_toml_path.exists():
                session_data = load_toml(session_toml_path)
                if session_data:
                    runtime_dir = str(session_data.get("runtime_dir", "")).strip() or None
                    if not model:
                        model = str(session_data.get("model", "")).strip()

            workspace = profile.workspace_for(seat)
            candidates = _find_session_jsonls(runtime_dir, workspace)
            if not candidates:
                return (None, "unknown")
            # Use the largest file (most active session)
            jsonl = max(candidates, key=lambda p: p.stat().st_size)

        pct, source = _compute_pct_from_jsonl(jsonl, model)
        return (pct, source)
    except Exception:
        return (None, "unknown")


def write_gstack_heartbeat_receipt(
    profile: "HarnessProfile",
    seat: str,
    *,
    status: str = "verified",
    install_fingerprint: str = "",
    manifest_fingerprint: str = "",
    verification_method: str = "gstack-harness",
    evidence: str = "",
    verified_at: str | None = None,
    _session_jsonl_override: "Path | None" = None,
    _model_override: str = "",
) -> None:
    """Write HEARTBEAT_RECEIPT.toml v2 for *seat* with token-usage measurement.

    Measurement failure never blocks the write — receipt is written with
    token_usage_source='unknown' and token_usage_pct absent when None.
    """
    try:
        pct, source = measure_token_usage_pct(
            profile, seat,
            _session_jsonl_override=_session_jsonl_override,
            _model_override=_model_override,
        )
    except Exception:
        pct, source = None, "unknown"
    now = utc_now_iso()
    receipt_path = profile.heartbeat_receipt_for(seat)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "version = 2",
        f'seat_id = "{seat}"',
        f'project = "{profile.project_name}"',
        f'status = "{status}"',
        f'verified_at = "{verified_at or now}"',
    ]
    if install_fingerprint:
        lines.append(f'install_fingerprint = "{install_fingerprint}"')
    if manifest_fingerprint:
        lines.append(f'manifest_fingerprint = "{manifest_fingerprint}"')
    if verification_method:
        lines.append(f'verification_method = "{verification_method}"')
    if evidence:
        lines.append(f'evidence = "{evidence}"')
    # Token fields — pct absent when unknown (readers default to None = no alert)
    if pct is not None:
        lines.append(f"token_usage_pct = {pct:.6f}")
    lines.append(f'token_usage_source = "{source}"')
    lines.append(f'token_usage_measured_at = "{now}"')
    lines.append("")
    receipt_path.write_text("\n".join(lines), encoding="utf-8")
