#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


REPO_ROOT = Path(
    os.environ.get("CLAWSEAT_ROOT", str(Path(__file__).resolve().parents[4]))
)
AGENT_HOME = Path(os.environ.get("AGENT_HOME", str(Path.home()))).expanduser()
AGENTS_ROOT = AGENT_HOME / ".agents"
SCRIPTS_ROOT = REPO_ROOT / "core" / "shell-scripts"
OPENCLAW_HOME = Path(
    os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw"))
).expanduser()
OPENCLAW_CONFIG_PATH = Path(
    os.environ.get("OPENCLAW_CONFIG_PATH", str(OPENCLAW_HOME / "openclaw.json"))
).expanduser()
OPENCLAW_AGENTS_ROOT = OPENCLAW_HOME / "agents"
OPENCLAW_FEISHU_SEND_SH = Path(
    os.environ.get(
        "CLAWSEAT_FEISHU_SEND_SH",
        os.environ.get(
            "OPENCLAW_FEISHU_SEND_SH",
            str(OPENCLAW_HOME / "skills" / "claude-desktop" / "script" / "feishu-send.sh"),
        ),
    )
).expanduser()


TASK_ROW_RE = re.compile(r"^\|\s*([A-Za-z0-9_-]+)\s*\|")
CONSUMED_RE = re.compile(
    r"^Consumed:\s*(?P<task_id>\S+)\s+from\s+(?P<source>\S+)\s+at\s+(?P<ts>.+)$"
)
PLACEHOLDER_RE = re.compile(r"\{([A-Z0-9_]+)\}")

DELEGATION_REPORT_HEADER = "OC_DELEGATION_REPORT_V1"
VALID_DELEGATION_LANES = {
    "planning",
    "builder",
    "reviewer",
    "qa",
    "designer",
    "frontstage",
}
VALID_DELEGATION_REPORT_STATUSES = {
    "in_progress",
    "done",
    "needs_decision",
    "blocked",
}
VALID_DELEGATION_DECISION_HINTS = {
    "hold",
    "proceed",
    "ask_user",
    "retry",
    "escalate",
    "close",
}
VALID_DELEGATION_USER_GATES = {
    "none",
    "optional",
    "required",
}
VALID_DELEGATION_NEXT_ACTIONS = {
    "wait",
    "consume_closeout",
    "ask_user",
    "retry_current_lane",
    "surface_blocker",
    "finalize_chain",
}


@dataclass
class HarnessProfile:
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
    heartbeat_owner: str
    active_loop_owner: str
    default_notify_target: str
    heartbeat_receipt: Path
    seats: list[str]
    heartbeat_seats: list[str]
    seat_roles: dict[str, str]
    seat_overrides: dict[str, dict[str, str]]
    dynamic_roster_enabled: bool = False
    session_root: Path = Path()
    bootstrap_seats: list[str] | None = None
    default_start_seats: list[str] | None = None
    compat_legacy_seats: bool = False
    legacy_seats: list[str] | None = None
    legacy_seat_roles: dict[str, str] | None = None

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


CLAUDE_ONBOARDING_MARKERS: list[tuple[str, str]] = [
    ("Browser didn't open? Use the url below to sign in", "oauth_login"),
    ("Paste code here if prompted >", "oauth_code"),
    ("Login successful. Press Enter to continue", "oauth_continue"),
    ("Accessing workspace:", "workspace_trust"),
    ("Quick safety check:", "workspace_trust"),
    ("WARNING: Claude Code running in Bypass Permissions mode", "bypass_permissions"),
    ("OAuth error:", "oauth_error"),
]


def sanitize_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())


def expand_profile_value(value: str) -> Path:
    defaults = {
        "CLAWSEAT_ROOT": str(REPO_ROOT),
        "AGENTS_ROOT": str(AGENTS_ROOT),
    }

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return os.environ.get(key, defaults.get(key, match.group(0)))

    return Path(PLACEHOLDER_RE.sub(replace, value)).expanduser()


def normalize_role(role: str) -> str:
    if role in {"planner", "planner-dispatcher"}:
        return "planner"
    return role or "specialist"


def role_sort_key(seat: str, role: str) -> tuple[int, str]:
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
    if seat == "koder":
        return (0, seat)
    return (priority.get(normalized, 50), seat)


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


def infer_role_from_seat_id(seat: str, fallback: str = "") -> str:
    if fallback:
        return fallback
    if seat == "koder":
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
    bootstrap_seats: list[str],
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
        bootstrap_seats,
        legacy_seats if compat_legacy_seats else [],
        sorted(
            discovered_sessions.keys(),
            key=lambda seat: role_sort_key(seat, seat_roles.get(seat, "")),
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
    profile_path = Path(path).expanduser().resolve()
    data = tomllib.loads(profile_path.read_text(encoding="utf-8"))
    dynamic = data.get("dynamic_roster", {})
    if not isinstance(dynamic, dict):
        dynamic = {}
    dynamic_enabled = bool(dynamic.get("enabled", False))
    session_root = expand_profile_value(str(dynamic.get("session_root", AGENTS_ROOT / "sessions")))
    heartbeat_owner = str(data["heartbeat_owner"])
    legacy_seat_roles = {
        str(key): str(value)
        for key, value in data.get("legacy_seat_roles", {}).items()
    }
    legacy_seats = [str(item) for item in data.get("legacy_seats", list(legacy_seat_roles.keys()))]
    bootstrap_seats = [str(item) for item in dynamic.get("bootstrap_seats", data.get("seats", []))]
    declared_seats = [str(item) for item in data.get("seats", [])]
    default_start_seats = [
        str(item) for item in dynamic.get("default_start_seats", bootstrap_seats)
    ]
    compat_legacy_seats = bool(dynamic.get("compat_legacy_seats", False))
    discovered = discovered_session_data(session_root, str(data["project_name"])) if dynamic_enabled else {}
    seat_roles = {str(k): str(v) for k, v in data.get("seat_roles", {}).items()}
    seat_roles.update(legacy_seat_roles)
    for seat, session in discovered.items():
        role = str(session.get("role", "")).strip()
        seat_roles[seat] = infer_role_from_seat_id(seat, fallback=role or seat_roles.get(seat, ""))
    seats = (
        resolve_dynamic_seats(
            heartbeat_owner=heartbeat_owner,
            declared_seats=declared_seats,
            bootstrap_seats=bootstrap_seats,
            compat_legacy_seats=compat_legacy_seats,
            legacy_seats=legacy_seats,
            discovered_sessions=discovered,
            seat_roles=seat_roles,
        )
        if dynamic_enabled
        else [str(item) for item in data.get("seats", [])]
    )
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
        status_script=expand_profile_value(str(data["status_script"])),
        patrol_script=expand_profile_value(str(data["patrol_script"])),
        agent_admin=expand_profile_value(str(data["agent_admin"])),
        workspace_root=expand_profile_value(str(data["workspace_root"])),
        handoff_dir=expand_profile_value(str(data["handoff_dir"])),
        heartbeat_owner=heartbeat_owner,
        active_loop_owner=str(data["active_loop_owner"]),
        default_notify_target=str(data["default_notify_target"]),
        heartbeat_receipt=expand_profile_value(str(data["heartbeat_receipt"])),
        seats=seats,
        heartbeat_seats=[str(item) for item in data.get("heartbeat_seats", [])],
        seat_roles=seat_roles,
        seat_overrides={
            str(seat_id): {str(k): str(v) for k, v in values.items()}
            for seat_id, values in data.get("seat_overrides", {}).items()
        },
        dynamic_roster_enabled=dynamic_enabled,
        session_root=session_root,
        bootstrap_seats=bootstrap_seats,
        default_start_seats=default_start_seats,
        compat_legacy_seats=compat_legacy_seats,
        legacy_seats=legacy_seats,
        legacy_seat_roles=legacy_seat_roles,
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_toml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return tomllib.loads(path.read_text(encoding="utf-8"))


def collect_feishu_group_keys(payload: Any, *, found: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(key, str) and key.startswith("group:"):
                group_id = key.split("group:", 1)[1].strip()
                if group_id and group_id not in found:
                    found.append(group_id)
            collect_feishu_group_keys(value, found=found)
    elif isinstance(payload, list):
        for item in payload:
            collect_feishu_group_keys(item, found=found)


def collect_feishu_group_ids_from_config(config: dict[str, Any]) -> list[str]:
    found: list[str] = []

    def add_group_id(value: Any) -> None:
        group_id = str(value).strip()
        if group_id and group_id != "*" and group_id not in found:
            found.append(group_id)

    channels = config.get("channels")
    if isinstance(channels, dict):
        feishu = channels.get("feishu")
        if isinstance(feishu, dict):
            groups = feishu.get("groups")
            if isinstance(groups, dict):
                for group_id in groups.keys():
                    add_group_id(group_id)
            accounts = feishu.get("accounts")
            if isinstance(accounts, dict):
                default_account = feishu.get("defaultAccount")
                if isinstance(default_account, str):
                    default_account_payload = accounts.get(default_account)
                    if isinstance(default_account_payload, dict):
                        default_groups = default_account_payload.get("groups")
                        if isinstance(default_groups, dict):
                            for group_id in default_groups.keys():
                                add_group_id(group_id)
                for account_payload in accounts.values():
                    if not isinstance(account_payload, dict):
                        continue
                    account_groups = account_payload.get("groups")
                    if isinstance(account_groups, dict):
                        for group_id in account_groups.keys():
                            add_group_id(group_id)
    return found


def collect_feishu_group_ids_from_sessions() -> list[str]:
    found: list[str] = []
    if not OPENCLAW_AGENTS_ROOT.exists():
        return found
    for path in sorted(OPENCLAW_AGENTS_ROOT.glob("*/sessions/sessions.json")):
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload is None:
            continue
        collect_feishu_group_keys(payload, found=found)
    return found


def resolve_primary_feishu_group_id() -> str | None:
    override = (
        os.environ.get("CLAWSEAT_FEISHU_GROUP_ID")
        or os.environ.get("OPENCLAW_FEISHU_GROUP_ID")
    )
    if override:
        resolved = override.strip()
        if resolved:
            return resolved
    config = load_json(OPENCLAW_CONFIG_PATH) or {}
    group_ids = collect_feishu_group_ids_from_config(config)
    if group_ids:
        return group_ids[0]
    group_ids = collect_feishu_group_ids_from_sessions()
    if group_ids:
        return group_ids[0]
    return None


def stable_dispatch_nonce(project: str, lane: str, task_id: str) -> str:
    seed = f"{project}:{lane}:{task_id}".encode("utf-8")
    return hashlib.sha1(seed).hexdigest()[:8]


def sanitize_report_value(value: str) -> str:
    return " ".join(str(value).split()).strip()


def build_delegation_report_text(
    *,
    project: str,
    lane: str,
    task_id: str,
    dispatch_nonce: str,
    report_status: str,
    decision_hint: str,
    user_gate: str,
    next_action: str,
    summary: str,
    human_summary: str | None = None,
) -> str:
    if lane not in VALID_DELEGATION_LANES:
        raise ValueError(f"invalid delegation lane: {lane}")
    if report_status not in VALID_DELEGATION_REPORT_STATUSES:
        raise ValueError(f"invalid delegation report_status: {report_status}")
    if decision_hint not in VALID_DELEGATION_DECISION_HINTS:
        raise ValueError(f"invalid delegation decision_hint: {decision_hint}")
    if user_gate not in VALID_DELEGATION_USER_GATES:
        raise ValueError(f"invalid delegation user_gate: {user_gate}")
    if next_action not in VALID_DELEGATION_NEXT_ACTIONS:
        raise ValueError(f"invalid delegation next_action: {next_action}")

    ordered_fields = [
        ("project", sanitize_report_value(project)),
        ("lane", sanitize_report_value(lane)),
        ("task_id", sanitize_report_value(task_id)),
        ("dispatch_nonce", sanitize_report_value(dispatch_nonce)),
        ("report_status", sanitize_report_value(report_status)),
        ("decision_hint", sanitize_report_value(decision_hint)),
        ("user_gate", sanitize_report_value(user_gate)),
        ("next_action", sanitize_report_value(next_action)),
        ("summary", sanitize_report_value(summary)),
    ]
    lines = [f"[{DELEGATION_REPORT_HEADER}]"]
    lines.extend(f"{key}={value}" for key, value in ordered_fields)
    lines.append(f"[/{DELEGATION_REPORT_HEADER}]")
    human = sanitize_report_value(human_summary or "")
    if human:
        lines.extend(["", human])
    return "\n".join(lines)


def send_feishu_user_message(
    message: str,
    *,
    group_id: str | None = None,
) -> dict[str, str]:
    resolved_group_id = (group_id or resolve_primary_feishu_group_id() or "").strip()
    payload: dict[str, str] = {
        "status": "skipped",
        "reason": "no_group_id_found",
        "message": message.strip(),
    }
    if not resolved_group_id:
        return payload

    payload["group_id"] = resolved_group_id
    lark_cli = shutil.which("lark-cli")
    if not lark_cli:
        payload["reason"] = "lark_cli_missing"
        return payload

    result = run_command_with_env(
        [
            lark_cli,
            "im",
            "+messages-send",
            "--as",
            "user",
            "--chat-id",
            resolved_group_id,
            "--text",
            message,
        ],
        cwd=OPENCLAW_HOME,
        env={"HOME": str(AGENT_HOME)},
    )
    payload["transport"] = "lark-cli-user"
    payload["returncode"] = str(result.returncode)
    if result.stdout.strip():
        payload["stdout"] = result.stdout.strip()
    if result.stderr.strip():
        payload["stderr"] = result.stderr.strip()
    if result.returncode == 0:
        payload["status"] = "sent"
    else:
        payload["status"] = "failed"
        payload["reason"] = "lark_cli_send_failed"
    return payload


def legacy_feishu_group_broadcast_enabled() -> bool:
    value = os.environ.get("CLAWSEAT_ENABLE_LEGACY_FEISHU_BROADCAST")
    if value is None:
        value = os.environ.get("OPENCLAW_ENABLE_LEGACY_FEISHU_BROADCAST")
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def broadcast_feishu_group_message(
    message: str,
    *,
    group_id: str | None = None,
) -> dict[str, str]:
    resolved_group_id = (group_id or resolve_primary_feishu_group_id() or "").strip()
    payload: dict[str, str] = {
        "status": "skipped",
        "reason": "no_group_id_found",
        "message": message.strip(),
    }
    if not resolved_group_id:
        return payload

    payload["group_id"] = resolved_group_id
    if not legacy_feishu_group_broadcast_enabled():
        payload["reason"] = "legacy_group_broadcast_disabled"
        return payload
    if not OPENCLAW_FEISHU_SEND_SH.exists():
        payload["reason"] = "feishu_send_script_missing"
        payload["send_script"] = str(OPENCLAW_FEISHU_SEND_SH)
        return payload

    result = run_command_with_env(
        [
            "bash",
            str(OPENCLAW_FEISHU_SEND_SH),
            "--target",
            f"group:{resolved_group_id}",
            message,
        ],
        cwd=OPENCLAW_HOME,
        env={"HOME": str(AGENT_HOME)},
    )
    payload["send_script"] = str(OPENCLAW_FEISHU_SEND_SH)
    payload["returncode"] = str(result.returncode)
    if result.stdout.strip():
        payload["stdout"] = result.stdout.strip()
    if result.stderr.strip():
        payload["stderr"] = result.stderr.strip()
    if result.returncode == 0:
        payload["status"] = "sent"
    else:
        payload["status"] = "failed"
        payload["reason"] = "feishu_send_failed"
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return run_command_with_env(args, cwd=cwd, env={"HOME": str(AGENT_HOME)})


def run_command_with_env(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        env=merged_env,
        check=False,
    )


def require_success(result: subprocess.CompletedProcess[str], what: str) -> None:
    if result.returncode == 0:
        return
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    detail = stderr or stdout or f"exit {result.returncode}"
    raise RuntimeError(f"{what} failed: {detail}")


def notify(profile: HarnessProfile, target_seat: str, message: str) -> subprocess.CompletedProcess[str]:
    session_name = resolve_session_name(profile, target_seat)
    return run_command_with_env(
        [str(profile.send_script), session_name, message],
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

def build_notify_message(
    target_seat: str,
    todo_path: Path,
    task_id: str,
    *,
    source: str,
    reply_to: str,
) -> str:
    return (
        f"{task_id} assigned from {source} to {target_seat}. "
        f"Read {todo_path}. When complete, reply to {reply_to} via DELIVERY + notify."
    )


def build_completion_message(task_id: str, delivery_path: Path, *, source: str, target: str) -> str:
    return (
        f"{task_id} complete from {source} to {target}. "
        f"Read {delivery_path} and write a durable Consumed ACK when handled."
    )


def upsert_tasks_row(path: Path, *, task_id: str, title: str, owner: str, status: str, notes: str) -> None:
    existing = read_text(path).splitlines()
    if not existing:
        existing = [
            "# Tasks",
            "",
            "| ID | Title | Owner | Status | Notes |",
            "|----|-------|-------|--------|-------|",
        ]

    new_row = f"| {task_id} | {title} | {owner} | {status} | {notes} |"
    row_index = None
    table_end = None
    for idx, line in enumerate(existing):
        if TASK_ROW_RE.match(line):
            table_end = idx
            if line.startswith(f"| {task_id} |"):
                row_index = idx
        elif table_end is not None and line.strip() and not line.startswith("|"):
            break
    if row_index is not None:
        existing[row_index] = new_row
    else:
        insert_at = table_end + 1 if table_end is not None else len(existing)
        existing.insert(insert_at, new_row)
    write_text(path, "\n".join(existing))


def append_status_note(path: Path, note: str) -> None:
    timestamp = utc_now_iso()
    existing = read_text(path)
    block = f"- {timestamp}: {note}"
    if existing.strip():
        write_text(path, existing.rstrip() + "\n" + block)
    else:
        write_text(path, "# Status\n\n" + block)


def write_todo(
    path: Path,
    *,
    task_id: str,
    project: str,
    owner: str,
    status: str,
    title: str,
    objective: str,
    source: str,
    reply_to: str,
) -> None:
    text = (
        f"task_id: {task_id}\n"
        f"project: {project}\n"
        f"owner: {owner}\n"
        f"status: {status}\n"
        f"title: {title}\n\n"
        f"# Objective\n\n{objective.strip()}\n\n"
        f"# Dispatch\n\n"
        f"source: {source}\n"
        f"reply_to: {reply_to}\n"
        f"dispatched_at: {utc_now_iso()}\n"
    )
    write_text(path, text)


def write_delivery(
    path: Path,
    *,
    task_id: str,
    owner: str,
    target: str,
    title: str,
    summary: str,
    status: str,
    verdict: str | None = None,
    frontstage_disposition: str | None = None,
    user_summary: str | None = None,
    next_action: str | None = None,
) -> None:
    lines = [
        f"task_id: {task_id}",
        f"owner: {owner}",
        f"target: {target}",
        f"status: {status}",
        f"date: {utc_now_iso()}",
        "",
        f"# Delivery: {title}",
        "",
        "## Summary",
        "",
        summary.strip(),
    ]
    if verdict:
        lines.extend(["", f"Verdict: {verdict}"])
    if frontstage_disposition:
        lines.extend(["", f"FrontstageDisposition: {frontstage_disposition}"])
    if user_summary:
        lines.extend(["", f"UserSummary: {user_summary.strip()}"])
    if next_action:
        lines.extend(["", f"NextAction: {next_action.strip()}"])
    write_text(path, "\n".join(lines))


def append_consumed_ack(path: Path, *, task_id: str, source: str) -> str:
    existing = read_text(path)
    for line in existing.splitlines():
        match = CONSUMED_RE.match(line.strip())
        if not match:
            continue
        if match.group("task_id") == task_id and match.group("source") == source:
            return line.strip()
    ack_line = f"Consumed: {task_id} from {source} at {utc_now_iso()}"
    if existing.strip():
        write_text(path, existing.rstrip() + "\n" + ack_line)
    else:
        write_text(path, ack_line)
    return ack_line


def find_consumed_ack(path: Path, *, task_id: str, source: str) -> str | None:
    for line in read_text(path).splitlines():
        match = CONSUMED_RE.match(line.strip())
        if not match:
            continue
        if match.group("task_id") == task_id and match.group("source") == source:
            return line.strip()
    return None


def extract_canonical_verdict(path: Path) -> str | None:
    for line in read_text(path).splitlines():
        if line.startswith("Verdict: "):
            verdict = line.split("Verdict: ", 1)[1].strip()
            return verdict or None
    return None


def extract_prefixed_value(path: Path, prefix: str) -> str | None:
    for line in read_text(path).splitlines():
        if line.startswith(prefix):
            value = line.split(prefix, 1)[1].strip()
            return value or None
    return None


def file_declares_task(path: Path, task_id: str) -> bool:
    return path.exists() and f"task_id: {task_id}" in read_text(path)


def handoff_assigned(
    profile: HarnessProfile,
    *,
    task_id: str,
    source: str,
    target: str,
    kind: str = "dispatch",
    delivery_path: str | None = None,
) -> bool:
    todo_path = profile.todo_path(target)
    source_delivery_path = profile.delivery_path(source)
    if kind == "completion" or str(source_delivery_path) == str(delivery_path or ""):
        return file_declares_task(source_delivery_path, task_id)
    return file_declares_task(todo_path, task_id)


def heartbeat_manifest_fingerprint(manifest: dict[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def heartbeat_receipt_is_verified(
    *,
    receipt: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    seat: str,
    project: str,
) -> bool:
    if not receipt or not manifest:
        return False
    if str(receipt.get("status", "")).strip() != "verified":
        return False
    if str(receipt.get("seat_id", "")).strip() != seat:
        return False
    if str(receipt.get("project", "")).strip() != project:
        return False
    return str(receipt.get("manifest_fingerprint", "")).strip() == heartbeat_manifest_fingerprint(manifest)


def heartbeat_state(profile: HarnessProfile, seat: str) -> dict[str, Any]:
    manifest_path = heartbeat_manifest_path(profile, seat)
    receipt_path = profile.heartbeat_receipt_for(seat)
    manifest = load_toml(manifest_path)
    receipt = load_toml(receipt_path)
    verified = heartbeat_receipt_is_verified(
        receipt=receipt,
        manifest=manifest,
        seat=seat,
        project=profile.project_name,
    )
    if verified:
        state = "verified"
    elif receipt:
        state = "unverified"
    else:
        state = "missing"
    return {
        "owner": seat,
        "configured": verified,
        "state": state,
        "manifest_path": str(manifest_path),
        "receipt_path": str(receipt_path),
        "manifest": manifest or {},
        "receipt": receipt or {},
    }


def make_local_override(profile: HarnessProfile, *, project_name: str, repo_root: Path) -> Path:
    materialized_seats = list(profile.seats)
    lines = [
        "version = 1",
        "",
        f'project_name = "{project_name}"',
        f'repo_root = "{repo_root}"',
        f"seat_order = {json.dumps(materialized_seats)}",
        f"bootstrap_seats = {json.dumps(materialized_seats)}",
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


def summarize_status_lines(lines: Iterable[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def executable_command(path: Path, *extra_args: str) -> list[str]:
    if path.suffix == ".py":
        return ["python3", str(path), *extra_args]
    return [str(path), *extra_args]


def tracked_runtime_seats(profile: HarnessProfile) -> list[str]:
    return [seat for seat in profile.seats if seat != profile.heartbeat_owner]


def heartbeat_manifest_path(profile: HarnessProfile, seat: str) -> Path:
    return profile.workspace_for(seat) / "HEARTBEAT_MANIFEST.toml"


def heartbeat_md_path(profile: HarnessProfile, seat: str) -> Path:
    return profile.workspace_for(seat) / "HEARTBEAT.md"


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
            "提示用户“收到测试消息即可回复希望完成什么任务”，并并行拉起 reviewer 进入审查待命。"
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


def is_managed_runtime_path(profile: HarnessProfile, path: Path) -> bool:
    try:
        path.resolve().relative_to(profile.tasks_root.resolve())
        return True
    except Exception:
        return False


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
        "interval_minutes = 10",
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


def materialize_profile_runtime(profile: HarnessProfile) -> None:
    ensure_dir(profile.tasks_root)
    ensure_dir(profile.handoff_dir)
    all_seats: list[str] = []
    for seat in [*(profile.bootstrap_seats or []), *profile.seats]:
        if seat and seat not in all_seats:
            all_seats.append(seat)
    if not all_seats:
        all_seats = list(profile.seats)
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

    for seat in profile.heartbeat_seats:
        ensure_dir(profile.workspace_for(seat))
        write_text(heartbeat_md_path(profile, seat), render_heartbeat_md(profile, seat))
        write_text(heartbeat_manifest_path(profile, seat), render_heartbeat_manifest(profile, seat))


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
    if not provider_dir.exists():
        return None
    for peer in sorted(provider_dir.glob("*.env")):
        if peer == secret_file or peer.stat().st_size == 0:
            continue
        shutil.copy2(peer, secret_file)
        secret_file.chmod(0o600)
        return peer
    return None


def seed_empty_oauth_runtime_from_peer(profile: HarnessProfile, seat: str) -> Path | None:
    """Disabled: Claude Code OAuth tokens are bound to a specific identity and
    cannot be shared across seats.  Copying credentials.json from a peer causes
    the new seat to fail with 'OAuth error: timeout of 15000ms exceeded' because
    it tries to reuse a token that belongs to a different runtime identity.
    Each seat must complete its own OAuth flow independently."""
    return None
