from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

CLAWSEAT_ROOT = Path(__file__).resolve().parents[3]
CORE_ROOT = CLAWSEAT_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from harness_adapter import (
    AuthConfig,
    HarnessAdapter,
    RecoverResult,
    ResumeResult,
    SeatPlan,
    SendResult,
    SessionHandle,
    SessionState,
)

AUTH_KEYWORDS = (
    "sign in",
    "oauth",
    "login successful",
    "paste code here",
    "api key",
    "authentication",
)
ONBOARDING_KEYWORDS = (
    "quick safety check",
    "accessing workspace",
    "bypass permissions",
    "/theme",
    "onboarding",
)
DEGRADED_KEYWORDS = (
    "traceback",
    "exception",
    "error:",
    "retry",
    "forbidden",
    "rate limit",
    "exceeded retry",
    "usage limit",
    "crash",
)
READY_KEYWORDS = ("ready", "idle", "waiting for input", "bypass permissions on")


class TmuxCliAdapter(HarnessAdapter):
    def __init__(
        self,
        *,
        agents_root: str | Path | None = None,
        sessions_root: str | Path | None = None,
        workspaces_root: str | Path | None = None,
    ) -> None:
        inferred_agents_root = self._default_agents_root()
        home = Path.home()
        self.agents_root = Path(
            agents_root or os.environ.get("AGENTS_ROOT", str(inferred_agents_root or (home / ".agents")))
        ).expanduser()
        self.clawseat_root = self._resolve_clawseat_root(self.agents_root)
        self.sessions_root = Path(
            sessions_root or os.environ.get("SESSIONS_ROOT", str(self.agents_root / "sessions"))
        ).expanduser()
        self.workspaces_root = Path(
            workspaces_root or os.environ.get("WORKSPACES_ROOT", str(self.agents_root / "workspaces"))
        ).expanduser()
        self.agent_admin = None
        self.harness_common = None

    def materialize(self, plan: SeatPlan) -> SessionHandle:
        workspace_path = Path(plan.workspace_path).expanduser()
        workspace_path.mkdir(parents=True, exist_ok=True)

        session_binding = dict(plan.session_binding_spec)
        session_name = str(session_binding.get("session_name", f"{plan.project}-{plan.seat_id}-{plan.tool}"))
        session_path = Path(
            str(
                session_binding.get(
                    "session_path",
                    self.sessions_root / plan.project / plan.seat_id / "session.toml",
                )
            )
        ).expanduser()
        contract_path = Path(
            str(session_binding.get("contract_path", workspace_path / "WORKSPACE_CONTRACT.toml"))
        ).expanduser()
        workspace_binding_path = Path(
            str(session_binding.get("workspace_binding_path", workspace_path / "SESSION_BINDING.toml"))
        ).expanduser()

        session_binding.setdefault("version", 1)
        session_binding.setdefault("project", plan.project)
        session_binding.setdefault("engineer_id", plan.seat_id)
        session_binding.setdefault("tool", plan.tool)
        session_binding.setdefault("role", plan.role)
        session_binding.setdefault("workspace", str(workspace_path))
        session_binding["session"] = session_name
        session_binding["session_name"] = session_name
        session_binding["contract_path"] = str(contract_path)
        session_binding["session_path"] = str(session_path)
        session_binding["workspace_binding_path"] = str(workspace_binding_path)

        self._write_toml(contract_path, plan.contract_content)
        self._write_toml(session_path, session_binding)
        self._write_toml(workspace_binding_path, session_binding)

        return self._make_handle(
            seat_id=plan.seat_id,
            project=plan.project,
            tool=plan.tool,
            runtime_id=session_name,
            workspace_path=str(workspace_path),
            session_path=str(session_path),
        )

    def start_session(self, seat_id: str, project: str, plan: SeatPlan) -> SessionHandle:
        self._ensure_helpers()
        handle = self.materialize(plan)
        session = self.agent_admin.load_session(project, seat_id)
        self.agent_admin.session_start_engineer(session)
        return handle

    def stop_session(self, handle: SessionHandle) -> None:
        self._ensure_helpers()
        if not self._session_exists(handle.runtime_id):
            return
        session = self.agent_admin.load_session(handle.project, handle.seat_id)
        self.agent_admin.session_stop_engineer(session)

    def destroy_session(self, handle: SessionHandle) -> None:
        if self._session_exists(handle.runtime_id):
            self._run(["tmux", "kill-session", "-t", handle.runtime_id], "destroy session")

    def resume_session(self, handle: SessionHandle) -> ResumeResult:
        if not self._session_exists(handle.runtime_id):
            return ResumeResult(resumed=False, state=SessionState.DEAD, detail="runtime is not running")
        send_result = self.send_message(handle, "继续")
        state = self.probe_state(handle)
        return ResumeResult(
            resumed=send_result.delivered,
            state=state,
            detail=send_result.detail,
        )

    def recover_session(self, handle: SessionHandle) -> RecoverResult:
        self._ensure_helpers()
        if self._session_exists(handle.runtime_id):
            resumed = self.resume_session(handle)
            return RecoverResult(
                recovered=resumed.resumed,
                resumed=resumed.resumed,
                restarted=False,
                state=resumed.state,
                detail=resumed.detail,
            )
        session = self.agent_admin.load_session(handle.project, handle.seat_id)
        self.agent_admin.session_start_engineer(session)
        state = self.probe_state(handle)
        return RecoverResult(
            recovered=state is not SessionState.DEAD,
            resumed=False,
            restarted=True,
            state=state,
            detail="started session via agent_admin.session_start_engineer",
        )

    def send_message(self, handle: SessionHandle, text: str) -> SendResult:
        if not self._session_exists(handle.runtime_id):
            return SendResult(delivered=False, transport="tmux", detail="runtime is not running")
        result = subprocess.run(
            ["tmux", "send-keys", "-t", handle.runtime_id, text, "C-m"],
            text=True,
            capture_output=True,
            check=False,
        )
        detail = result.stderr.strip() or result.stdout.strip()
        return SendResult(
            delivered=result.returncode == 0,
            transport="tmux",
            detail=detail,
        )

    def get_output(self, handle: SessionHandle, lines: int = 50) -> str:
        self._ensure_helpers()
        if not self._session_exists(handle.runtime_id):
            return ""
        profile = self._profile_for_handle(handle)
        return self.harness_common.capture_session_pane(profile, handle.seat_id, lines=max(lines, 1))

    def probe_state(self, handle: SessionHandle) -> SessionState:
        if not self._session_exists(handle.runtime_id):
            return SessionState.DEAD
        output = self.get_output(handle, lines=80)
        lowered = output.lower()
        if any(keyword in lowered for keyword in AUTH_KEYWORDS):
            return SessionState.AUTH_NEEDED
        if any(keyword in lowered for keyword in DEGRADED_KEYWORDS):
            return SessionState.DEGRADED
        if any(keyword in lowered for keyword in ONBOARDING_KEYWORDS):
            return SessionState.ONBOARDING

        nonempty = [line.strip() for line in output.splitlines() if line.strip()]
        tail = nonempty[-5:]
        if any(keyword in lowered for keyword in READY_KEYWORDS):
            return SessionState.READY
        if any(line.startswith("❯") or line.startswith(">") or line.startswith("$") for line in tail):
            return SessionState.READY
        return SessionState.RUNNING

    def list_sessions(self, project: str) -> list[SessionHandle]:
        handles: list[SessionHandle] = []
        project_root = self.sessions_root / project
        if project_root.exists():
            for session_path in sorted(project_root.glob("*/session.toml")):
                binding = self._read_toml(session_path)
                session_name = str(binding.get("session", binding.get("session_name", ""))).strip()
                tool = str(binding.get("tool", "")).strip()
                workspace = str(binding.get("workspace", "")).strip()
                handles.append(
                    self._make_handle(
                        seat_id=str(binding.get("engineer_id", session_path.parent.name)).strip(),
                        project=project,
                        tool=tool,
                        runtime_id=session_name,
                        workspace_path=workspace,
                        session_path=str(session_path),
                    )
                )
            if handles:
                return handles

        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            text=True,
            capture_output=True,
            check=False,
        )
        prefix = f"{project}-"
        for raw in result.stdout.splitlines():
            session_name = raw.strip()
            if not session_name.startswith(prefix):
                continue
            remainder = session_name[len(prefix) :]
            if "-" not in remainder:
                continue
            seat_id, tool = remainder.rsplit("-", 1)
            handles.append(
                self._make_handle(
                    seat_id=seat_id,
                    project=project,
                    tool=tool,
                    runtime_id=session_name,
                )
            )
        return handles

    def get_auth_config(self, seat_id: str, project: str) -> AuthConfig:
        session_path = self.sessions_root / project / seat_id / "session.toml"
        if not session_path.exists():
            return AuthConfig(
                seat_id=seat_id,
                project=project,
                auth_mode="",
                provider="",
                identity="",
            )
        binding = self._read_toml(session_path)
        return AuthConfig(
            seat_id=seat_id,
            project=project,
            auth_mode=str(binding.get("auth_mode", "")),
            provider=str(binding.get("provider", "")),
            identity=str(binding.get("identity", "")),
            secret_file=str(binding.get("secret_file", "")),
            runtime_dir=str(binding.get("runtime_dir", "")),
            locator={
                "session_path": str(session_path),
                "runtime_id": str(binding.get("session", binding.get("session_name", ""))),
            },
        )

    def _session_exists(self, runtime_id: str) -> bool:
        result = subprocess.run(
            ["tmux", "has-session", "-t", runtime_id],
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0

    def _load_session_binding(
        self,
        handle: SessionHandle,
        *,
        required: bool = True,
    ) -> dict[str, Any]:
        session_path = Path(handle.session_path).expanduser() if handle.session_path else Path()
        if not handle.session_path and handle.project and handle.seat_id:
            session_path = self.sessions_root / handle.project / handle.seat_id / "session.toml"
        if not session_path.exists():
            if required:
                raise FileNotFoundError(f"session binding missing: {session_path}")
            return {}
        return self._read_toml(session_path)

    def _read_toml(self, path: Path) -> dict[str, Any]:
        with path.open("rb") as handle:
            return tomllib.load(handle)

    def _run(self, args: list[str], label: str) -> None:
        result = subprocess.run(args, text=True, capture_output=True, check=False)
        if result.returncode == 0:
            return
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{label} failed: {detail}")

    def _write_toml(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._render_toml_dict(data).rstrip() + "\n", encoding="utf-8")

    def _default_agents_root(self) -> Path | None:
        cwd = Path.cwd().resolve()
        for parent in (cwd, *cwd.parents):
            if parent.name == ".agents":
                return parent
        return None

    def _load_helpers(self) -> None:
        agent_admin_root = self.clawseat_root / "core" / "scripts"
        harness_root = self.clawseat_root / "core" / "skills" / "gstack-harness" / "scripts"
        for path in (agent_admin_root, harness_root):
            path_str = str(path)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
        import agent_admin  # type: ignore
        import _common as harness_common  # type: ignore

        self.agent_admin = agent_admin
        self.harness_common = harness_common

    def _ensure_helpers(self) -> None:
        if self.agent_admin is not None and self.harness_common is not None:
            return
        self._load_helpers()

    def _resolve_clawseat_root(self, agents_root: Path) -> Path:
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

        agents_root_candidate = agents_root.parent / "coding" / "ClawSeat"
        if all((agents_root_candidate / marker).exists() for marker in helper_markers):
            return agents_root_candidate

        fallback = (Path.home() / "coding" / "ClawSeat").expanduser()
        print(
            f"warning: CLAWSEAT_ROOT not set and no repo-relative helper root found; "
            f"falling back to {fallback}",
            file=sys.stderr,
        )
        return fallback

    def _profile_for_handle(self, handle: SessionHandle) -> Any:
        binding = self._load_session_binding(handle)
        workspace = Path(str(binding.get("workspace", handle.workspace_path or ""))).expanduser()
        workspace_root = workspace.parent if workspace.name == handle.seat_id else Path(str(handle.workspace_path)).expanduser().parent
        repo_root = Path(str(binding.get("repo_root", Path.cwd()))).expanduser()
        return SimpleNamespace(
            workspace_root=workspace_root,
            project_name=handle.project,
            repo_root=repo_root,
        )

    def _make_handle(
        self,
        *,
        seat_id: str,
        project: str,
        tool: str,
        runtime_id: str,
        workspace_path: str = "",
        session_path: str = "",
    ) -> SessionHandle:
        return SessionHandle(
            seat_id=seat_id,
            project=project,
            tool=tool,
            runtime_id=runtime_id,
            locator={
                "runtime_id": runtime_id,
                "transport": "tmux",
                "workspace_path": workspace_path,
                "session_path": session_path,
            },
            workspace_path=workspace_path,
            session_path=session_path,
        )

    def _render_toml_dict(self, data: dict[str, Any], prefix: str = "") -> str:
        lines: list[str] = []
        nested: list[tuple[str, dict[str, Any]]] = []
        for key, value in data.items():
            if isinstance(value, dict):
                nested.append((key, value))
                continue
            lines.append(f"{key} = {self._render_toml_value(value)}")
        for key, value in nested:
            section = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            if lines:
                lines.append("")
            lines.append(f"[{section}]")
            nested_text = self._render_toml_dict(value, prefix=section)
            if nested_text:
                lines.append(nested_text)
        return "\n".join(lines)

    def _render_toml_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return repr(value)
        if isinstance(value, list):
            return "[" + ", ".join(self._render_toml_value(item) for item in value) + "]"
        return json.dumps(str(value), ensure_ascii=False)
