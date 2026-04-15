#!/usr/bin/env python3
"""
OpenClaw koder → ClawSeat control bridge (production version).

Bridges OpenClaw koder to ClawSeat control plane, allowing OpenClaw to:
- View team seat status
- Dispatch tasks to planner
- Instantiate new seats via TmuxCliAdapter
- Read planner state (brief, pending frontstage)
- Switch projects

Three-layer relationship:
  OpenClaw koder (user entry + agent orchestration)
       ↓ calls ClawSeat adapter
  ClawSeat control plane (seat management + protocol + roster)
       ↓ calls TmuxCliAdapter
  tmux engineer team (claude-code / codex / gemini sessions)

No core protocol logic lives here — this is only OpenClaw → ClawSeat adapter
call wrapping.

Production path: ClawSeat/shells/openclaw-plugin/openclaw_bridge.py
Uses canonical imports from ClawSeat core/ and adapters/.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

# Resolve CLAWSEAT_ROOT using the same 4-layer chain as TmuxCliAdapter:
# 1. CLAWSEAT_ROOT env var
# 2. Traverse upward from __file__ looking for core marker files
# 3. AGENTS_ROOT parent / coding / ClawSeat
# 4. ~/coding/ClawSeat with a warning


def _resolve_clawseat_root(agents_root: Path | None = None) -> Path:
    """Resolve CLAWSEAT_ROOT using the same 4-layer chain as TmuxCliAdapter."""
    configured = os.environ.get("CLAWSEAT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()

    helper_markers = (
        Path("core/scripts/agent_admin.py"),
        Path("core/skills/gstack-harness/scripts/_common.py"),
    )
    module_path = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in module_path.parents:
        candidates.append(parent)
        candidates.append(parent / "ClawSeat")

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if all((candidate / marker).exists() for marker in helper_markers):
            return candidate

    if agents_root is not None:
        agents_root_candidate = agents_root.parent / "coding" / "ClawSeat"
        if all((agents_root_candidate / marker).exists() for marker in helper_markers):
            return agents_root_candidate

    # Try the real home directory path explicitly
    fallback = Path.home() / "coding" / "ClawSeat"
    if all((fallback / marker).exists() for marker in helper_markers):
        return fallback

    fallback = Path.home() / "coding" / "ClawSeat"
    print(
        f"warning: CLAWSEAT_ROOT not set and no repo-relative helper root found; "
        f"falling back to {fallback}",
        file=sys.stderr,
    )
    return fallback


_CLAWSEAT_ROOT = _resolve_clawseat_root()
_BRIDGE_BINDING_LOCK = threading.RLock()

# Add ClawSeat root to sys.path for canonical imports
sys.path.insert(0, str(_CLAWSEAT_ROOT))

# Canonical imports from ClawSeat core/
from core.adapter.clawseat_adapter import (
    AdapterResult,
    BriefState,
    ClawseatAdapter,
    PendingFrontstageItem,
    SessionStatus,
)


def _projects_root() -> Path:
    return Path(os.path.expanduser("~/.agents/projects"))


def _bridge_path_for_project(project: str) -> Path:
    return _projects_root() / project / "BRIDGE.toml"


def _bridge_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quote_toml(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _load_bridge_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    bridge = payload.get("bridge")
    if not isinstance(bridge, dict):
        return None
    return {
        "project": str(bridge.get("project", "")).strip(),
        "group_id": str(bridge.get("group_id", "")).strip(),
        "account_id": str(bridge.get("account_id", "")).strip(),
        "session_key": str(bridge.get("session_key", "")).strip(),
        "bridge_mode": str(bridge.get("bridge_mode", "")).strip(),
        "bound_at": str(bridge.get("bound_at", "")).strip(),
        "bound_by": str(bridge.get("bound_by", "")).strip(),
        "bridge_path": str(path),
    }


def _write_bridge_file(path: Path, binding: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[bridge]",
        f"project = {_quote_toml(binding['project'])}",
        f"group_id = {_quote_toml(binding['group_id'])}",
        f"account_id = {_quote_toml(binding['account_id'])}",
        f"session_key = {_quote_toml(binding['session_key'])}",
        f'bridge_mode = "user_identity"',
        f"bound_at = {_quote_toml(binding['bound_at'])}",
        f"bound_by = {_quote_toml(binding['bound_by'])}",
        "",
    ]
    fd, tmp_path = tempfile.mkstemp(prefix="bridge-", suffix=".toml", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _collect_project_bindings() -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    root = _projects_root()
    if not root.exists():
        return bindings
    for bridge_path in sorted(root.glob("*/BRIDGE.toml")):
        binding = _load_bridge_file(bridge_path)
        if binding is None:
            continue
        bindings.append(binding)
    return bindings


# ---------------------------------------------------------------------------
# TmuxCliAdapter initialization
# ---------------------------------------------------------------------------


_TMUX_ADAPTER_MODULE: Any = None


def _get_tmux_adapter_module() -> Any:
    global _TMUX_ADAPTER_MODULE
    if _TMUX_ADAPTER_MODULE is None:
        _TMUX_ADAPTER_MODULE = _load_tmux_adapter()
    return _TMUX_ADAPTER_MODULE


def _load_tmux_adapter():
    """Load TmuxCliAdapter via importlib from the adapters path."""
    adapter_path = _CLAWSEAT_ROOT / "adapters" / "harness" / "tmux-cli" / "adapter.py"
    spec = importlib.util.spec_from_file_location("clawseat_tmux_cli_adapter", adapter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load TmuxCliAdapter from {adapter_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["clawseat_tmux_cli_adapter"] = module
    spec.loader.exec_module(module)
    return module


def init_tmux_adapter(
    *,
    agents_root: str | Path | None = None,
    sessions_root: str | Path | None = None,
    workspaces_root: str | Path | None = None,
) -> Any:
    """Initialize a TmuxCliAdapter instance."""
    module = _get_tmux_adapter_module()
    return module.TmuxCliAdapter(
        agents_root=agents_root,
        sessions_root=sessions_root,
        workspaces_root=workspaces_root,
    )


# ---------------------------------------------------------------------------
# Profile initialization
# ---------------------------------------------------------------------------


def ensure_clawseat_profile(
    project_name: str,
    *,
    repo_root: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> str:
    """
    Ensure a ClawSeat dynamic profile exists for the given project.

    Returns the resolved profile path.

    Special case: the canonical `install` project auto-seeds its dynamic profile
    from the shipped `examples/starter/profiles/install.toml` when bootstrapping
    on a blank machine.
    """
    if profile_path is not None:
        candidate = Path(profile_path).expanduser()
        if candidate.exists():
            return str(candidate)

    # Check standard locations
    dynamic_path = Path(f"/tmp/{project_name}-profile-dynamic.toml")
    if dynamic_path.exists():
        return str(dynamic_path)

    legacy_path = Path(f"/tmp/{project_name}-profile.toml")
    if legacy_path.exists():
        return str(legacy_path)

    if project_name == "install":
        template_root = Path(repo_root).expanduser() if repo_root is not None else _CLAWSEAT_ROOT
        template_path = template_root / "examples" / "starter" / "profiles" / "install.toml"
        if template_path.exists():
            dynamic_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
            return str(dynamic_path)
        raise FileNotFoundError(
            f"canonical install profile template missing at {template_path}; "
            f"cannot seed /tmp/{project_name}-profile-dynamic.toml"
        )

    # No profile found — need to create one
    raise FileNotFoundError(
        f"no dynamic profile found for project {project_name!r}; "
        f"create /tmp/{project_name}-profile-dynamic.toml from a starter profile "
        f"or run migrate_profile.py if a legacy /tmp/{project_name}-profile.toml already exists"
    )


def init_clawseat_adapter(
    *,
    project_name: str,
    profile_path: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> ClawseatAdapter:
    """
    Initialize a ClawSeatAdapter for the given project.

    ClawSeatAdapter uses repo_root to locate refac/transport/transport_router.py and
    refac/engine/instantiate_seat.py. If repo_root is not provided, defaults to
    _CLAWSEAT_ROOT (the ClawSeat repo root), not the project workspace /tmp/{project}.
    """
    resolved_profile = ensure_clawseat_profile(
        project_name,
        profile_path=profile_path,
    )

    # repo_root must point to the ClawSeat repo root, not the project workspace.
    # ClawSeatAdapter uses repo_root to locate transport_router.py and
    # instantiate_seat.py under refac/ — these resolve correctly when
    # repo_root=_CLAWSEAT_ROOT.
    if repo_root is None:
        repo_root = _CLAWSEAT_ROOT

    resolved_repo = Path(repo_root)
    adapter = ClawseatAdapter(repo_root=resolved_repo)
    adapter.profile_path_for(project_name, resolved_profile)
    return adapter


# ---------------------------------------------------------------------------
# Team status operations
# ---------------------------------------------------------------------------


def list_team_sessions(
    project_name: str,
    *,
    tmux_adapter: Any | None = None,
) -> list[dict[str, Any]]:
    """
    List all tmux sessions for the given project via TmuxCliAdapter.

    Returns a list of session handles with seat_id, tool, runtime_id, etc.
    """
    if tmux_adapter is None:
        tmux_adapter = init_tmux_adapter()

    handles = tmux_adapter.list_sessions(project_name)
    return [
        {
            "seat_id": h.seat_id,
            "project": h.project,
            "tool": h.tool,
            "runtime_id": h.runtime_id,
            "workspace_path": h.workspace_path,
            "session_path": h.session_path,
            "locator": h.locator,
        }
        for h in handles
    ]


def probe_seat_state(
    handle: dict[str, Any],
    *,
    tmux_adapter: Any | None = None,
) -> str:
    """
    Probe the state of a seat session.

    Returns one of: auth_needed, onboarding, running, ready, degraded, dead
    """
    if tmux_adapter is None:
        tmux_adapter = init_tmux_adapter()

    from core.harness_adapter import SessionHandle

    session_handle = SessionHandle(
        seat_id=handle["seat_id"],
        project=handle["project"],
        tool=handle["tool"],
        runtime_id=handle["runtime_id"],
        workspace_path=handle.get("workspace_path", ""),
        session_path=handle.get("session_path", ""),
    )
    return tmux_adapter.probe_state(session_handle).value


def probe_seat_state_detailed(
    handle: dict[str, Any],
    *,
    tmux_adapter: Any | None = None,
) -> dict[str, Any]:
    """
    Probe the state of a seat session with degraded sub-reason classification.

    Returns dict with:
      - state: one of auth_needed, onboarding, running, ready, degraded, dead
      - degraded_reason: 'authz' (403/forbidden), 'quota' (429/rate limit), or None
    """
    if tmux_adapter is None:
        tmux_adapter = init_tmux_adapter()

    from core.harness_adapter import SessionHandle

    session_handle = SessionHandle(
        seat_id=handle["seat_id"],
        project=handle["project"],
        tool=handle["tool"],
        runtime_id=handle["runtime_id"],
        workspace_path=handle.get("workspace_path", ""),
        session_path=handle.get("session_path", ""),
    )
    state, reason, observable = tmux_adapter.probe_state_detailed(session_handle)
    return {
        "state": state.value,
        "degraded_reason": reason,
        "current_task_id": observable.current_task_id,
        "needs_input": observable.needs_input,
        "input_reason": observable.input_reason,
        "last_prompt_excerpt": observable.last_prompt_excerpt,
    }


def resume_seat_if_needed(
    handle: dict[str, Any],
    *,
    tmux_adapter: Any | None = None,
) -> dict[str, Any]:
    """
    Attempt to resume a seat session, with differentiated strategy based on state.

    - 429/quota DEGRADED: auto-send "继续" (resume)
    - 403/authz DEGRADED: do NOT auto-recover, return BLOCKED_ESCALATION
    - Other states: use standard resume logic
    """
    if tmux_adapter is None:
        tmux_adapter = init_tmux_adapter()

    from core.harness_adapter import SessionHandle

    session_handle = SessionHandle(
        seat_id=handle["seat_id"],
        project=handle["project"],
        tool=handle["tool"],
        runtime_id=handle["runtime_id"],
        workspace_path=handle.get("workspace_path", ""),
        session_path=handle.get("session_path", ""),
    )

    state, reason, _observable = tmux_adapter.probe_state_detailed(session_handle)

    if state.value == "degraded":
        if reason == "authz":
            return {
                "action": "BLOCKED_ESCALATION",
                "reason": "authz",
                "state": state.value,
                "delivered": False,
                "detail": "403/forbidden detected — must escalate to user",
            }
        elif reason == "quota":
            result = tmux_adapter.send_message(session_handle, "继续")
            return {
                "action": "auto_resume",
                "reason": "quota",
                "state": state.value,
                "delivered": result.delivered,
                "detail": result.detail,
            }
        else:
            result = tmux_adapter.send_message(session_handle, "继续")
            return {
                "action": "auto_resume",
                "reason": "generic",
                "state": state.value,
                "delivered": result.delivered,
                "detail": result.detail,
            }

    result = tmux_adapter.resume_session(session_handle)
    return {
        "action": "resume",
        "state": result.state.value,
        "resumed": result.resumed,
        "detail": result.detail,
    }


# ---------------------------------------------------------------------------
# Task dispatch
# ---------------------------------------------------------------------------


def dispatch_task_to_planner(
    *,
    project_name: str,
    task_id: str,
    title: str,
    objective: str,
    source: str = "koder",
    target: str | None = None,
    reply_to: str | None = None,
    clawseat_adapter: ClawseatAdapter | None = None,
) -> AdapterResult:
    """
    Dispatch a task to the planner via ClawSeatAdapter.

    Dynamically resolves the planner target if not explicitly provided.
    """
    if clawseat_adapter is None:
        clawseat_adapter = init_clawseat_adapter(project_name=project_name)

    resolved_target = target
    if resolved_target is None:
        try:
            planner_info = clawseat_adapter.resolve_planner(project_name=project_name)
            resolved_target = planner_info["planner_instance"]
        except Exception as primary_err:
            # Fallback: try active_loop_owner from the same profile snapshot
            try:
                planner_info = clawseat_adapter.resolve_planner(project_name=project_name)
                resolved_target = planner_info.get("active_loop_owner", "")
            except Exception:
                pass
            if not resolved_target:
                raise RuntimeError(
                    f"dispatch_task_to_planner: cannot resolve planner target for project "
                    f"{project_name!r} (tried planner_instance and active_loop_owner): {primary_err}"
                )

    return clawseat_adapter.dispatch_task(
        project_name=project_name,
        source=source,
        target=resolved_target,
        task_id=task_id,
        title=title,
        objective=objective,
        reply_to=reply_to,
    )


# ---------------------------------------------------------------------------
# Seat instantiation
# ---------------------------------------------------------------------------


def instantiate_seat(
    *,
    project_name: str,
    template_id: str,
    instance_id: str | None = None,
    repo_root: str | Path | None = None,
    force: bool = False,
    clawseat_adapter: ClawseatAdapter | None = None,
) -> dict[str, Any]:
    """
    Instantiate a new seat via ClawSeatAdapter + TmuxCliAdapter.
    """
    if clawseat_adapter is None:
        clawseat_adapter = init_clawseat_adapter(project_name=project_name)

    result = clawseat_adapter.instantiate_seat(
        project_name=project_name,
        template_id=template_id,
        instance_id=instance_id,
        repo_root=repo_root,
        force=force,
    )
    return result


def start_seat_via_tmux(
    seat_id: str,
    project_name: str,
    *,
    tmux_adapter: Any | None = None,
    clawseat_adapter: ClawseatAdapter | None = None,
) -> dict[str, Any]:
    """
    Start a seat session via TmuxCliAdapter.
    """
    if tmux_adapter is None:
        tmux_adapter = init_tmux_adapter()
    if clawseat_adapter is None:
        clawseat_adapter = init_clawseat_adapter(project_name=project_name)

    from core.harness_adapter import SeatPlan

    session_path = Path(os.environ.get("SESSIONS_ROOT", str(Path.home() / ".agents" / "sessions"))) / project_name / seat_id / "session.toml"
    if not session_path.exists():
        raise FileNotFoundError(f"session binding not found: {session_path}")

    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    with session_path.open("rb") as f:
        binding = tomllib.load(f)

    seat_plan = SeatPlan(
        seat_id=seat_id,
        project=project_name,
        role=binding.get("role", ""),
        tool=binding.get("tool", ""),
        workspace_path=binding.get("workspace", ""),
        contract_content={},
        session_binding_spec=binding,
    )

    handle = tmux_adapter.start_session(seat_id, project_name, seat_plan)
    return {
        "seat_id": handle.seat_id,
        "project": handle.project,
        "tool": handle.tool,
        "runtime_id": handle.runtime_id,
        "workspace_path": handle.workspace_path,
        "session_path": handle.session_path,
    }


# ---------------------------------------------------------------------------
# Planner state reading
# ---------------------------------------------------------------------------


def read_planner_brief(
    project_name: str,
    *,
    profile_path: str | Path | None = None,
    clawseat_adapter: ClawseatAdapter | None = None,
) -> BriefState:
    """
    Read the current PLANNER_BRIEF for the project.
    """
    if clawseat_adapter is None:
        clawseat_adapter = init_clawseat_adapter(project_name=project_name)

    return clawseat_adapter.read_brief(project_name=project_name, profile_path=profile_path)


def read_pending_frontstage(
    project_name: str,
    *,
    profile_path: str | Path | None = None,
    clawseat_adapter: ClawseatAdapter | None = None,
) -> list[PendingFrontstageItem]:
    """
    Read unresolved PENDING_FRONTSTAGE items for the project.
    """
    if clawseat_adapter is None:
        clawseat_adapter = init_clawseat_adapter(project_name=project_name)

    return clawseat_adapter.read_pending_frontstage(project_name=project_name, profile_path=profile_path)


# ---------------------------------------------------------------------------
# Project switching
# ---------------------------------------------------------------------------


def switch_project(
    project_name: str,
    *,
    profile_path: str | Path | None = None,
    clawseat_adapter: ClawseatAdapter | None = None,
) -> dict[str, Any]:
    """
    Switch the ClawSeatAdapter's active project.
    """
    if clawseat_adapter is None:
        clawseat_adapter = init_clawseat_adapter(project_name=project_name)

    return clawseat_adapter.switch_project(project_name=project_name, profile_path=profile_path)


# ---------------------------------------------------------------------------
# Project-group bridge binding
# ---------------------------------------------------------------------------


def list_project_bindings() -> list[dict[str, Any]]:
    """
    List all durable project ↔ group bridge bindings.
    """
    with _BRIDGE_BINDING_LOCK:
        return _collect_project_bindings()


def get_binding_for_group(group_id: str) -> dict[str, Any] | None:
    """
    Return the durable binding for a Feishu group id, if any.
    """
    resolved_group_id = str(group_id).strip()
    if not resolved_group_id:
        raise ValueError("group_id is required")
    with _BRIDGE_BINDING_LOCK:
        for binding in _collect_project_bindings():
            if binding["group_id"] == resolved_group_id:
                return binding
    return None


def bind_project_to_group(
    project: str,
    group_id: str,
    account_id: str,
    session_key: str,
    bound_by: str,
    *,
    authorized: bool = False,
) -> dict[str, Any]:
    """
    Bind one project to one Feishu group with explicit user authorization.

    Constraints:
    - one project -> one group
    - one group -> one project
    """
    resolved_project = str(project).strip()
    resolved_group_id = str(group_id).strip()
    resolved_account_id = str(account_id).strip()
    resolved_session_key = str(session_key).strip()
    resolved_bound_by = str(bound_by).strip()

    if not authorized:
        raise PermissionError("bind_project_to_group requires explicit authorized=True")
    if not resolved_project:
        raise ValueError("project is required")
    if not resolved_group_id:
        raise ValueError("group_id is required")
    if not resolved_account_id:
        raise ValueError("account_id is required")
    if not resolved_session_key:
        raise ValueError("session_key is required")
    if not resolved_bound_by:
        raise ValueError("bound_by is required")

    with _BRIDGE_BINDING_LOCK:
        bindings = _collect_project_bindings()
        for binding in bindings:
            if binding["group_id"] == resolved_group_id and binding["project"] != resolved_project:
                raise ValueError(
                    f"group {resolved_group_id!r} is already bound to project {binding['project']!r}"
                )
            if binding["project"] == resolved_project and binding["group_id"] != resolved_group_id:
                raise ValueError(
                    f"project {resolved_project!r} is already bound to group {binding['group_id']!r}"
                )

        binding = {
            "project": resolved_project,
            "group_id": resolved_group_id,
            "account_id": resolved_account_id,
            "session_key": resolved_session_key,
            "bridge_mode": "user_identity",
            "bound_at": _bridge_now_iso(),
            "bound_by": resolved_bound_by,
        }
        path = _bridge_path_for_project(resolved_project)
        _write_bridge_file(path, binding)
        binding["bridge_path"] = str(path)
        return binding


def unbind_project(project: str) -> dict[str, Any] | None:
    """
    Remove the durable bridge binding for a project.
    """
    resolved_project = str(project).strip()
    if not resolved_project:
        raise ValueError("project is required")
    with _BRIDGE_BINDING_LOCK:
        path = _bridge_path_for_project(resolved_project)
        binding = _load_bridge_file(path)
        if binding is None:
            return None
        path.unlink(missing_ok=True)
        return binding


# ---------------------------------------------------------------------------
# Seat status check
# ---------------------------------------------------------------------------


def check_seat_status(
    project_name: str,
    seat_id: str,
    *,
    clawseat_adapter: ClawseatAdapter | None = None,
) -> SessionStatus:
    """
    Check the status of a specific seat via ClawSeatAdapter.
    """
    if clawseat_adapter is None:
        clawseat_adapter = init_clawseat_adapter(project_name=project_name)

    return clawseat_adapter.check_session(project_name=project_name, seat_id=seat_id)


# ---------------------------------------------------------------------------
# Team summary
# ---------------------------------------------------------------------------


def get_team_summary(
    project_name: str,
    *,
    tmux_adapter: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Return a structured summary of all seat states for the given project.

    Each entry contains: seat_id, state, degraded_reason, current_task_id,
    needs_input, input_reason, last_prompt_excerpt.
    """
    if tmux_adapter is None:
        tmux_adapter = init_tmux_adapter()

    sessions = list_team_sessions(project_name, tmux_adapter=tmux_adapter)
    summary: list[dict[str, Any]] = []

    from core.harness_adapter import SessionHandle

    for session in sessions:
        handle = SessionHandle(
            seat_id=session["seat_id"],
            project=session["project"],
            tool=session["tool"],
            runtime_id=session["runtime_id"],
            workspace_path=session.get("workspace_path", ""),
            session_path=session.get("session_path", ""),
        )
        state, reason, observable = tmux_adapter.probe_state_detailed(handle)
        summary.append({
            "seat_id": session["seat_id"],
            "state": state.value,
            "degraded_reason": reason,
            "current_task_id": observable.current_task_id,
            "needs_input": observable.needs_input,
            "input_reason": observable.input_reason,
            "last_prompt_excerpt": observable.last_prompt_excerpt,
        })

    return summary


# ---------------------------------------------------------------------------
# Safe seat start with preflight
# ---------------------------------------------------------------------------


class EnvironmentNotReady(Exception):
    """Raised when preflight checks reveal hard blocks."""

    def __init__(self, items: list[Any]) -> None:
        self.items = items
        super().__init__(f"environment not ready: {[i.name for i in items]}")


class CLINotAvailable(Exception):
    """Raised when the required CLI tool is not available."""

    def __init__(self, template_id: str, instructions: str) -> None:
        self.template_id = template_id
        self.instructions = instructions
        super().__init__(f"{template_id} CLI not available: {instructions}")


class AuthNotConfigured(Exception):
    """Raised when auth credentials are missing for a seat."""

    def __init__(self, seat_id: str, path: str, instructions: str) -> None:
        self.seat_id = seat_id
        self.path = path
        self.instructions = instructions
        super().__init__(f"auth not configured for {seat_id}: {instructions}")


def safe_start_seat(
    project_name: str,
    seat_id: str,
    template_id: str,
    *,
    clawseat_adapter: ClawseatAdapter | None = None,
    tmux_adapter: Any | None = None,
) -> dict[str, Any]:
    """
    Safely start a seat after running preflight checks.

    Raises EnvironmentNotReady, CLINotAvailable, or AuthNotConfigured on failure.
    Returns the session handle on success.
    """
    from core import preflight

    if clawseat_adapter is None:
        clawseat_adapter = init_clawseat_adapter(project_name=project_name)
    if tmux_adapter is None:
        tmux_adapter = init_tmux_adapter()

    # 1. preflight check
    result = preflight.preflight_check(project_name)
    if result.has_hard_blocked:
        raise EnvironmentNotReady(result.hard_blocked_items)

    # 2. auto-fix retryable items
    for item in result.retryable_items:
        fixed = preflight.auto_fix(item, project_name)
        # Update in result for re-check
        idx = result.retryable_items.index(item)
        result.retryable_items[idx] = fixed

    # 3. re-check after auto-fix
    result = preflight.preflight_check(project_name)
    if not result.all_pass:
        raise EnvironmentNotReady(
            result.hard_blocked_items + result.retryable_items
        )

    # 4. CLI availability — tool-specific guidance
    cli_map = {
        "claude": ("claude", "npm install -g @anthropic-ai/claude-code"),
        "codex": ("codex", "npm install -g @anthropic-ai/codex"),
        "gemini": ("gemini", "pip install google-generativeai && set API_KEY in secrets"),
    }
    cli_name, cli_install = cli_map.get(template_id, (template_id, f"install {template_id}"))
    import shutil as _sh

    if not _sh.which(cli_name):
        raise CLINotAvailable(
            template_id,
            f"CLI {cli_name!r} not found in PATH. Install: {cli_install}",
        )

    # 5. Auth check — tool-specific secret paths and instructions
    session_path = Path(os.environ.get("SESSIONS_ROOT", str(Path.home() / ".agents" / "sessions"))) / project_name / seat_id / "session.toml"
    auth_status = "ok"
    auth_instructions = ""
    auth_missing_path = ""

    # Tool-specific secret file templates
    tool_secrets = {
        "claude": lambda seat: Path(f"~/.agents/secrets/claude/anthropic/{project_name}/{seat}.env"),
        "codex": lambda seat: Path(f"~/.agents/secrets/codex/openai/{project_name}/{seat}.env"),
        "gemini": lambda seat: Path(f"~/.agents/secrets/gemini/google/{project_name}/{seat}.env"),
    }

    if session_path.exists():
        try:
            try:
                import tomllib as _tomllib
            except ModuleNotFoundError:
                import tomli as _tomllib  # type: ignore

            with session_path.open("rb") as f:
                binding = _tomllib.load(f)
            secret_file = binding.get("secret_file", "")
            auth_missing_path = secret_file
            if secret_file:
                sf = Path(secret_file).expanduser()
                if not sf.exists():
                    auth_status = "missing"
                    auth_instructions = (
                        f"Secret file does not exist: {sf}. "
                        f"Create it and add your API key."
                    )
                elif sf.read_text().strip() == "":
                    auth_status = "missing"
                    auth_instructions = f"Secret file is empty: {sf}. Add your API key."
        except Exception:
            pass

    # If no session binding, use tool-specific default secret path
    if auth_status == "ok" and not auth_missing_path:
        default_secret = tool_secrets.get(
            template_id, lambda _seat: Path("~/.agents/secrets/unknown")
        )(seat_id)
        auth_missing_path = str(default_secret.expanduser())
        if not default_secret.exists():
            auth_status = "missing"
            auth_instructions = (
                f"No auth configured for {template_id} seat {seat_id}. "
                f"Create {default_secret} with your API key."
            )

    if auth_status == "missing":
        raise AuthNotConfigured(seat_id, auth_missing_path, auth_instructions)

    # 6. start the session
    handle = start_seat_via_tmux(
        seat_id=seat_id,
        project_name=project_name,
        tmux_adapter=tmux_adapter,
        clawseat_adapter=clawseat_adapter,
    )
    return handle


# ---------------------------------------------------------------------------
# Bootstrap entrypoint
# ---------------------------------------------------------------------------


def bootstrap(
    project_name: str = "install",
    *,
    profile_path: str | Path | None = None,
    skip_preflight: bool = False,
) -> dict[str, Any]:
    """
    Bootstrap the OpenClaw → ClawSeat bridge.

    Runs preflight_check first; auto-fixes retryable items and re-checks.
    Writes BOOTSTRAP_RECEIPT.toml on success. Skips preflight if a valid
    receipt already exists (unless skip_preflight=True).

    Raises EnvironmentNotReady if hard_blocked items prevent bootstrap.
    """
    from core import preflight as _preflight

    # bootstrap_receipt imports tomllib — defer until after preflight to avoid
    # crashing before we can report HARD_BLOCKED in Python < 3.11 without tomli.
    _bootstrap_receipt: Any = None
    try:
        from core import bootstrap_receipt as _bootstrap_receipt_module
        _bootstrap_receipt = _bootstrap_receipt_module
    except ImportError:
        # tomllib unavailable and tomli not installed — will surface as HARD_BLOCKED
        pass

    preflight_result: _preflight.PreflightResult | None = None
    receipt_valid = False

    if not skip_preflight:
        # Check existing receipt if bootstrap_receipt module loaded successfully
        if _bootstrap_receipt is not None:
            existing = _bootstrap_receipt.read_receipt(project_name)
            if existing is not None:
                valid, _reason = _bootstrap_receipt.is_valid(existing)
                if valid:
                    receipt_valid = True
                else:
                    preflight_result = _preflight.preflight_check(project_name)
            else:
                preflight_result = _preflight.preflight_check(project_name)
        else:
            # bootstrap_receipt unavailable — run preflight to surface the tomllib HARD_BLOCKED
            preflight_result = _preflight.preflight_check(project_name)

    if preflight_result is not None:
        if preflight_result.has_hard_blocked:
            raise EnvironmentNotReady(preflight_result.hard_blocked_items)

        # Auto-fix retryable items and re-check
        if preflight_result.has_retryable:
            for item in preflight_result.retryable_items:
                fixed = _preflight.auto_fix(item, project_name)
                idx = preflight_result.items.index(item)
                preflight_result.items[idx] = fixed
            # Re-run full preflight to confirm
            preflight_result = _preflight.preflight_check(project_name)
            if not preflight_result.all_pass:
                raise EnvironmentNotReady(
                    preflight_result.hard_blocked_items + preflight_result.retryable_items
                )

        # Write receipt on success (only when we ran fresh preflight)
        if preflight_result is not None and _bootstrap_receipt is not None:
            _bootstrap_receipt.write_receipt(project_name, preflight_result)

    clawseat_adapter = init_clawseat_adapter(project_name=project_name, profile_path=profile_path)

    tmux_adapter = init_tmux_adapter()

    switch_result = clawseat_adapter.switch_project(project_name=project_name)

    brief = clawseat_adapter.read_brief(project_name=project_name)

    pending_items = clawseat_adapter.read_pending_frontstage(project_name=project_name)

    return {
        "project_name": project_name,
        "profile_path": switch_result["profile_path"],
        "current_project": clawseat_adapter.current_project,
        "frontstage_epoch": clawseat_adapter.frontstage_epoch,
        "clawseat_adapter": "initialized",
        "tmux_adapter": type(tmux_adapter).__name__,
        "planner_brief_title": brief.title,
        "planner_brief_status": brief.status,
        "planner_brief_disposition": brief.frontstage_disposition,
        "pending_frontstage_count": len(pending_items),
    }


__all__ = [
    "AuthNotConfigured",
    "bind_project_to_group",
    "bootstrap",
    "check_seat_status",
    "CLINotAvailable",
    "dispatch_task_to_planner",
    "ensure_clawseat_profile",
    "EnvironmentNotReady",
    "get_binding_for_group",
    "get_team_summary",
    "init_clawseat_adapter",
    "init_tmux_adapter",
    "instantiate_seat",
    "list_project_bindings",
    "list_team_sessions",
    "probe_seat_state",
    "probe_seat_state_detailed",
    "read_pending_frontstage",
    "read_planner_brief",
    "resume_seat_if_needed",
    "safe_start_seat",
    "start_seat_via_tmux",
    "switch_project",
    "unbind_project",
]
