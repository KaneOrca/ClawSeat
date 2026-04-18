"""Feishu / Lark messaging helpers — extracted from _common.py."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from _utils import (
    AGENT_HOME,
    OPENCLAW_AGENTS_ROOT,
    OPENCLAW_CONFIG_PATH,
    OPENCLAW_FEISHU_SEND_SH,
    OPENCLAW_HOME,
    load_json,
    load_toml,
    run_command_with_env,
)


# ── Real-user-home resolution ─────────────────────────────────────────
#
# Seats run inside a sandbox HOME at
#   ~/.agents/runtime/identities/<tool>/<auth>/<identity>/home/
# so Path.home() inside a seat returns THAT, not the operator's real HOME.
# Many resources live at the operator's real HOME — lark-cli config,
# OpenClaw workspace-koder WORKSPACE_CONTRACT.toml with the per-project
# feishu_group_id, the OpenClaw openclaw.json — and if we resolve them
# against the sandbox HOME they all miss and we silently fall off canonical
# paths. That is EXACTLY what caused planner→koder `complete_handoff.py`
# to route through tmux (because resolve_primary_feishu_group_id returned
# None under sandbox HOME) and hard-fail when koder's phantom tmux
# session was missing.
#
# This helper is the single source of truth for "where is the operator's
# real HOME, regardless of which sandbox we are running in". Used by every
# resource lookup below.

def _real_user_home() -> Path:
    """Return the operator's real HOME, bypassing any seat runtime isolation.

    Resolution priority (most-authoritative first):

    1. Explicit env override (CLAWSEAT_REAL_HOME / LARK_CLI_HOME) — set by
       the installer / harness when it knows the real answer.
    2. Explicit AGENT_HOME env differing from Path.home() — harness injected
       the real path.
    3. pwd.getpwuid(os.getuid()).pw_dir — the OS's own answer for "which
       directory is this user's home". Reliable regardless of HOME env
       override, regardless of sandbox residue. This is authoritative.
    4. Path.home() as last-resort fallback (only if pwd lookup fails, which
       should not happen on normal macOS/Linux).

    NOTE on canary heuristics: an earlier version checked
    `(Path.home() / ".lark-cli/config.json").exists()` as a "am I in a
    sandbox?" signal. That was unsafe because sandbox HOMEs inherit / get
    seeded with stale lark-cli config from earlier test runs, falsely
    telling us the sandbox was the real HOME. pwd is the correct primary.
    """
    # 1. Explicit override
    override = (
        os.environ.get("CLAWSEAT_REAL_HOME")
        or os.environ.get("LARK_CLI_HOME")
    )
    if override:
        return Path(override).expanduser()
    # 2. AGENT_HOME differs from Path.home() — harness told us where real is
    if str(AGENT_HOME) != str(Path.home()):
        return AGENT_HOME
    # 3. pwd database — authoritative OS answer, immune to HOME env override
    try:
        import pwd
        pw = pwd.getpwuid(os.getuid())
        if pw and pw.pw_dir:
            return Path(pw.pw_dir)
    except (ImportError, KeyError):  # silent-ok: pwd module or uid key unavailable; fall back to Path.home()
        pass
    # 4. Last-resort fallback
    return Path.home()


# ── Delegation report constants ──────────────────────────────────────

DELEGATION_REPORT_HEADER = "OC_DELEGATION_REPORT_V1"
VALID_DELEGATION_LANES = {
    "planning", "builder", "reviewer", "qa", "designer", "frontstage",
}
VALID_DELEGATION_REPORT_STATUSES = {
    "in_progress", "done", "needs_decision", "blocked",
}
VALID_DELEGATION_DECISION_HINTS = {
    "hold", "proceed", "ask_user", "retry", "escalate", "close",
}
VALID_DELEGATION_USER_GATES = {"none", "optional", "required"}
VALID_DELEGATION_NEXT_ACTIONS = {
    "wait", "consume_closeout", "ask_user",
    "retry_current_lane", "surface_blocker", "finalize_chain",
}


# ── Group ID resolution ──────────────────────────────────────────────

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
        except (json.JSONDecodeError, OSError):
            continue
        if payload is None:
            continue
        collect_feishu_group_keys(payload, found=found)
    return found


def resolve_primary_feishu_group_id(project: str | None = None) -> str | None:
    """Resolve the feishu group ID for this project.

    Priority:
    1. Env var override (CLAWSEAT_FEISHU_GROUP_ID / OPENCLAW_FEISHU_GROUP_ID)
    2. Project WORKSPACE_CONTRACT.toml feishu_group_id field
    3. OpenClaw config (fallback, may return wrong group for multi-project setups)
    """
    # 1. Env var override
    override = (
        os.environ.get("CLAWSEAT_FEISHU_GROUP_ID")
        or os.environ.get("OPENCLAW_FEISHU_GROUP_ID")
    )
    if override:
        resolved = override.strip()
        if resolved:
            return resolved

    # 2. Project contract binding (SSOT for per-project group).
    # Resolve against the operator's REAL home, not Path.home() — when a
    # seat runs inside a sandbox HOME (ClawSeat runtime identity), Path.home()
    # points at an empty sandbox tree and every project contract path below
    # would miss, silently routing planner→koder complete_handoff through
    # tmux instead of Feishu.
    if project:
        real_home = _real_user_home()
        contract_paths = [
            # OpenClaw koder workspace
            real_home / ".openclaw" / "workspace-koder" / "WORKSPACE_CONTRACT.toml",
            # ClawSeat managed workspace
            real_home / ".agents" / "workspaces" / project / "koder" / "WORKSPACE_CONTRACT.toml",
        ]
        for cp in contract_paths:
            if cp.exists():
                contract = load_toml(cp)
                if contract:
                    gid = str(contract.get("feishu_group_id", "")).strip()
                    if gid:
                        return gid

    # 3. OpenClaw config fallback (may return wrong group in multi-project).
    # OPENCLAW_CONFIG_PATH is derived from OPENCLAW_HOME which respects
    # CLAWSEAT_REAL_HOME / pwd resolution where relevant. But in a sandbox
    # HOME the default resolves under the sandbox too — force real home here.
    config_path = _real_user_home() / ".openclaw" / "openclaw.json"
    if not config_path.exists():
        config_path = OPENCLAW_CONFIG_PATH
    config = load_json(config_path) or {}
    group_ids = collect_feishu_group_ids_from_config(config)
    if group_ids:
        return group_ids[0]
    group_ids = collect_feishu_group_ids_from_sessions()
    if group_ids:
        return group_ids[0]
    return None


# ── Nonce & report building ──────────────────────────────────────────

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


# ── Auth & CLI helpers ───────────────────────────────────────────────

def _lark_cli_real_home() -> str:
    """Return the REAL user home for lark-cli, bypassing any seat runtime isolation.

    lark-cli stores config at $HOME/.lark-cli/ and auth tokens at
    $HOME/Library/Application Support/lark-cli/. These are user-level,
    not seat-level. When a seat runs with an isolated HOME (ClawSeat
    runtime identity), we must restore the real user HOME so lark-cli
    can find its config and tokens.

    Shares resolution logic with _real_user_home(); the .lark-cli canary
    inside _real_user_home() makes this identical for lark-cli callers.
    """
    return str(_real_user_home())


def _lark_cli_env() -> dict[str, str]:
    return {
        "HOME": _lark_cli_real_home(),
        "OPENCLAW_HOME": str(OPENCLAW_HOME),
    }


def check_feishu_auth() -> dict[str, str]:
    """Check lark-cli availability and auth token status."""
    lark_cli = shutil.which("lark-cli")
    if not lark_cli:
        return {
            "status": "missing",
            "reason": "lark-cli not found in PATH",
            "fix": "brew install larksuite/cli/lark-cli",
        }
    result = run_command_with_env(
        [lark_cli, "auth", "status"],
        cwd=str(OPENCLAW_HOME),
        env=_lark_cli_env(),
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        return {
            "status": "error",
            "reason": f"lark-cli auth status failed (rc={result.returncode}): {stderr}",
            "fix": "lark-cli auth login",
        }
    stdout = result.stdout.strip()
    try:
        auth_info = json.loads(stdout)
    except (ValueError, TypeError):
        return {
            "status": "error",
            "reason": f"unexpected lark-cli auth output: {stdout[:200]}",
            "fix": "lark-cli auth login",
        }
    token_status = auth_info.get("tokenStatus", "unknown")
    identity = auth_info.get("identity", "unknown")
    user_name = auth_info.get("userName", "")
    if token_status == "valid":
        payload: dict[str, str] = {
            "status": "ok",
            "reason": "auth token is valid",
            "identity": identity,
        }
        if user_name:
            payload["userName"] = user_name
        return payload
    if token_status in ("expired", "needs_refresh"):
        return {
            "status": token_status,
            "reason": f"lark-cli token is {token_status}",
            "fix": "lark-cli auth login",
        }
    return {
        "status": "error",
        "reason": f"unexpected token status: {token_status}",
        "fix": "lark-cli auth login",
    }


def _classify_send_failure(stderr: str) -> tuple[str, str]:
    lower = stderr.lower()
    if "token" in lower and ("expired" in lower or "invalid" in lower or "refresh" in lower):
        return "auth_expired", "lark-cli auth login"
    if "permission" in lower or "scope" in lower or "forbidden" in lower:
        return "permission_denied", "lark-cli auth login  (ensure im:message scope is granted)"
    if "not found" in lower or "no such" in lower or "404" in lower:
        return "group_not_found", "check that the group ID is correct and the bot is in the group"
    if "timeout" in lower or "connection" in lower or "network" in lower:
        return "network_error", "check network connectivity and retry"
    return "lark_cli_send_failed", "run `lark-cli auth status` to diagnose"


# ── Send functions ───────────────────────────────────────────────────

def send_feishu_user_message(
    message: str,
    *,
    group_id: str | None = None,
    project: str | None = None,
    pre_check_auth: bool = False,
) -> dict[str, str]:
    resolved_group_id = (group_id or resolve_primary_feishu_group_id(project=project) or "").strip()
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
        payload["fix"] = "brew install larksuite/cli/lark-cli"
        return payload
    if pre_check_auth:
        auth = check_feishu_auth()
        if auth["status"] != "ok":
            payload["status"] = "failed"
            payload["reason"] = f"auth_{auth['status']}"
            payload["fix"] = auth.get("fix", "lark-cli auth login")
            payload["auth_detail"] = auth.get("reason", "")
            return payload
    result = run_command_with_env(
        [lark_cli, "im", "+messages-send", "--as", "user",
         "--chat-id", resolved_group_id, "--text", message],
        cwd=str(OPENCLAW_HOME),
        env=_lark_cli_env(),
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
        reason, fix = _classify_send_failure(result.stderr)
        payload["reason"] = reason
        payload["fix"] = fix
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
    project: str | None = None,
) -> dict[str, str]:
    resolved_group_id = (group_id or resolve_primary_feishu_group_id(project=project) or "").strip()
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
        ["bash", str(OPENCLAW_FEISHU_SEND_SH), "--target",
         f"group:{resolved_group_id}", message],
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
