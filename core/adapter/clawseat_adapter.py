#!/usr/bin/env python3
from __future__ import annotations
import tempfile

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]


def _get_migration_root() -> Path:
    """Compute MIGRATION_ROOT at call time, not import time."""
    refac_override = os.environ.get("CLAWSEAT_REFAC_ROOT", "").strip()
    if refac_override:
        return Path(refac_override) / "migration"
    # Canonical production path: ClawSeat/core/migration/
    clawseat_root = os.environ.get("CLAWSEAT_ROOT", "").strip()
    if clawseat_root:
        return Path(clawseat_root) / "core" / "migration"
    return Path.home() / "coding" / "ClawSeat" / "core" / "migration"


@dataclass
class AdapterResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class BriefAction:
    requested_operation: str
    target_role: str
    target_instance: str
    template_id: str
    reason: str
    resume_task: str


@dataclass
class BriefState:
    project_name: str
    profile_path: str
    brief_path: str
    title: str
    owner: str
    status: str
    updated: str
    frontstage_disposition: str
    user_summary: str
    action: BriefAction


@dataclass
class SessionStatus:
    project_name: str
    seat_id: str
    session_path: str
    session_name: str
    exists: bool
    tmux_running: bool
    runtime_dir: str
    workspace: str
    tool: str
    provider: str
    auth_mode: str


@dataclass
class PendingFrontstageItem:
    item_id: str
    item_type: str
    related_task: str
    summary: str
    planner_recommendation: str
    koder_default_action: str
    user_input_needed: bool
    blocking: bool
    options: list[str]
    resolved: bool
    resolved_by: str
    resolved_at: str
    resolution: str
    section: str


@dataclass
class PendingProjectOperation:
    kind: str
    project_name: str
    frontstage_epoch: int
    profile_path: str
    payload: dict[str, Any]


def _default_python_bin() -> str:
    return shutil.which("python3.12") or shutil.which("python3.11") or sys.executable


class ClawseatAdapter:
    def __init__(self, *, repo_root: str | Path = REPO_ROOT, python_bin: str | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.python_bin = python_bin or _default_python_bin()
        self.engine_script = self.repo_root / "core" / "engine" / "instantiate_seat.py"
        self.transport_router = self.repo_root / "core" / "transport" / "transport_router.py"
        self.current_project: str | None = None
        self.frontstage_epoch = 0
        self._project_profiles: dict[str, Path] = {}
        self._pending_inbox: dict[str, list[PendingProjectOperation]] = {}

    def profile_path_for(self, project_name: str, profile_path: str | Path | None = None) -> Path:
        if profile_path is not None:
            candidate = Path(profile_path).expanduser()
        else:
            from resolve import dynamic_profile_path
            dynamic = dynamic_profile_path(project_name)
            if dynamic.exists():
                candidate = dynamic
            else:
                legacy = Path(f"/tmp/{project_name}-profile.toml")
                if legacy.exists():
                    candidate = legacy
                else:
                    raise FileNotFoundError(f"no profile found for project {project_name}")
        declared_project = self._profile_project_name(candidate)
        if declared_project != project_name:
            raise ValueError(
                f"profile {candidate} declares project_name={declared_project!r}, expected {project_name!r}"
            )
        self._project_profiles[project_name] = candidate
        return candidate

    def switch_project(
        self,
        *,
        project_name: str,
        profile_path: str | Path | None = None,
    ) -> dict[str, Any]:
        previous_project = self.current_project
        drained: list[AdapterResult] = []
        if previous_project:
            drained = self.drain_pending_ops(project_name=previous_project)
        self.frontstage_epoch += 1
        resolved_profile = self.profile_path_for(project_name, profile_path)
        self.current_project = project_name
        brief = self.read_brief(project_name=project_name, profile_path=resolved_profile)
        return {
            "previous_project": previous_project,
            "current_project": self.current_project,
            "frontstage_epoch": self.frontstage_epoch,
            "profile_path": str(resolved_profile),
            "drained_operations": [self._serialize_adapter_result(item) for item in drained],
            "pending_inbox_depth": len(self._pending_inbox.get(project_name, [])),
            "brief": asdict(brief),
        }

    def pending_inbox(self, *, project_name: str | None = None) -> list[PendingProjectOperation]:
        selected = project_name or self.current_project
        if not selected:
            return []
        return list(self._pending_inbox.get(selected, []))

    def drain_pending_ops(self, *, project_name: str | None = None) -> list[AdapterResult]:
        selected = project_name or self.current_project
        if not selected:
            return []
        if self.current_project and selected != self.current_project:
            raise RuntimeError("may only drain the current_project inbox")
        queued = list(self._pending_inbox.get(selected, []))
        self._pending_inbox[selected] = []
        results: list[AdapterResult] = []
        for operation in queued:
            if operation.kind == "dispatch":
                results.append(
                    self._execute_dispatch(
                        project_name=operation.project_name,
                        profile_path=operation.profile_path,
                        **operation.payload,
                    )
                )
            elif operation.kind == "notify":
                results.append(
                    self._execute_notify(
                        project_name=operation.project_name,
                        profile_path=operation.profile_path,
                        **operation.payload,
                    )
                )
            elif operation.kind == "complete":
                results.append(
                    self._execute_complete(
                        project_name=operation.project_name,
                        profile_path=operation.profile_path,
                        **operation.payload,
                    )
                )
        return results

    def instantiate_seat(
        self,
        *,
        project_name: str,
        template_id: str,
        instance_id: str | None = None,
        repo_root: str | Path | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        command = [
            self.python_bin,
            str(self.engine_script),
            "--template-id",
            template_id,
            "--project-name",
            project_name,
            "--repo-root",
            str(Path(repo_root).expanduser() if repo_root else self.repo_root),
        ]
        if instance_id:
            command.extend(["--instance-id", instance_id])
        if force:
            command.append("--force")
        if dry_run:
            command.append("--dry-run")
        result = self._run_json(command)
        result["command"] = command
        return result

    def dispatch_task(
        self,
        *,
        project_name: str,
        source: str,
        target: str,
        task_id: str,
        title: str,
        objective: str,
        reply_to: str | None = None,
        profile_path: str | Path | None = None,
        notes: str | None = None,
        status_note: str | None = None,
        skip_notify: bool = False,
    ) -> AdapterResult:
        if not self._can_execute_for(project_name):
            return self._queue_operation(
                kind="dispatch",
                project_name=project_name,
                profile_path=profile_path,
                payload={
                    "source": source,
                    "target": target,
                    "task_id": task_id,
                    "title": title,
                    "objective": objective,
                    "reply_to": reply_to,
                    "notes": notes,
                    "status_note": status_note,
                    "skip_notify": skip_notify,
                },
            )
        return self._execute_dispatch(
            project_name=project_name,
            source=source,
            target=target,
            task_id=task_id,
            title=title,
            objective=objective,
            reply_to=reply_to,
            profile_path=profile_path,
            notes=notes,
            status_note=status_note,
            skip_notify=skip_notify,
        )

    def _execute_dispatch(
        self,
        *,
        project_name: str,
        source: str,
        target: str,
        task_id: str,
        title: str,
        objective: str,
        reply_to: str | None = None,
        profile_path: str | Path | None = None,
        notes: str | None = None,
        status_note: str | None = None,
        skip_notify: bool = False,
    ) -> AdapterResult:
        command = [
            self.python_bin,
            str(self.transport_router),
            "dispatch",
            "--profile",
            str(self.profile_path_for(project_name, profile_path)),
            "--source",
            source,
            "--target",
            target,
            "--task-id",
            task_id,
            "--title",
            title,
            "--objective",
            objective,
        ]
        if reply_to:
            command.extend(["--reply-to", reply_to])
        if notes:
            command.extend(["--notes", notes])
        if status_note:
            command.extend(["--status-note", status_note])
        if skip_notify:
            command.append("--skip-notify")
        return self._run(command)

    def notify_seat(
        self,
        *,
        project_name: str,
        source: str,
        target: str,
        message: str,
        task_id: str | None = None,
        reply_to: str | None = None,
        kind: str = "notice",
        profile_path: str | Path | None = None,
        skip_receipt: bool = False,
    ) -> AdapterResult:
        if not self._can_execute_for(project_name):
            return self._queue_operation(
                kind="notify",
                project_name=project_name,
                profile_path=profile_path,
                payload={
                    "source": source,
                    "target": target,
                    "message": message,
                    "task_id": task_id,
                    "reply_to": reply_to,
                    "kind": kind,
                    "skip_receipt": skip_receipt,
                },
            )
        return self._execute_notify(
            project_name=project_name,
            source=source,
            target=target,
            message=message,
            task_id=task_id,
            reply_to=reply_to,
            kind=kind,
            profile_path=profile_path,
            skip_receipt=skip_receipt,
        )

    def _execute_notify(
        self,
        *,
        project_name: str,
        source: str,
        target: str,
        message: str,
        task_id: str | None = None,
        reply_to: str | None = None,
        kind: str = "notice",
        profile_path: str | Path | None = None,
        skip_receipt: bool = False,
    ) -> AdapterResult:
        command = [
            self.python_bin,
            str(self.transport_router),
            "notify",
            "--profile",
            str(self.profile_path_for(project_name, profile_path)),
            "--source",
            source,
            "--target",
            target,
            "--message",
            message,
            "--kind",
            kind,
        ]
        if task_id:
            command.extend(["--task-id", task_id])
        if reply_to:
            command.extend(["--reply-to", reply_to])
        if skip_receipt:
            command.append("--skip-receipt")
        return self._run(command)

    def complete_handoff(
        self,
        *,
        project_name: str,
        source: str,
        task_id: str,
        target: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        status: str = "completed",
        verdict: str | None = None,
        frontstage_disposition: str | None = None,
        user_summary: str | None = None,
        next_action: str | None = None,
        profile_path: str | Path | None = None,
        ack_only: bool = False,
        skip_notify: bool = False,
    ) -> AdapterResult:
        if not self._can_execute_for(project_name):
            return self._queue_operation(
                kind="complete",
                project_name=project_name,
                profile_path=profile_path,
                payload={
                    "source": source,
                    "task_id": task_id,
                    "target": target,
                    "title": title,
                    "summary": summary,
                    "status": status,
                    "verdict": verdict,
                    "frontstage_disposition": frontstage_disposition,
                    "user_summary": user_summary,
                    "next_action": next_action,
                    "ack_only": ack_only,
                    "skip_notify": skip_notify,
                },
            )
        return self._execute_complete(
            project_name=project_name,
            source=source,
            task_id=task_id,
            target=target,
            title=title,
            summary=summary,
            status=status,
            verdict=verdict,
            frontstage_disposition=frontstage_disposition,
            user_summary=user_summary,
            next_action=next_action,
            profile_path=profile_path,
            ack_only=ack_only,
            skip_notify=skip_notify,
        )

    def _execute_complete(
        self,
        *,
        project_name: str,
        source: str,
        task_id: str,
        target: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        status: str = "completed",
        verdict: str | None = None,
        frontstage_disposition: str | None = None,
        user_summary: str | None = None,
        next_action: str | None = None,
        profile_path: str | Path | None = None,
        ack_only: bool = False,
        skip_notify: bool = False,
    ) -> AdapterResult:
        command = [
            self.python_bin,
            str(self.transport_router),
            "complete",
            "--profile",
            str(self.profile_path_for(project_name, profile_path)),
            "--source",
            source,
            "--task-id",
            task_id,
            "--status",
            status,
        ]
        if target:
            command.extend(["--target", target])
        if title:
            command.extend(["--title", title])
        if summary:
            command.extend(["--summary", summary])
        if verdict:
            command.extend(["--verdict", verdict])
        if frontstage_disposition:
            command.extend(["--frontstage-disposition", frontstage_disposition])
        if user_summary:
            command.extend(["--user-summary", user_summary])
        if next_action:
            command.extend(["--next-action", next_action])
        if ack_only:
            command.append("--ack-only")
        if skip_notify:
            command.append("--skip-notify")
        return self._run(command)

    def read_brief(self, *, project_name: str, profile_path: str | Path | None = None) -> BriefState:
        resolved_profile = self.profile_path_for(project_name, profile_path)
        snapshot = self._profile_snapshot(resolved_profile)
        brief_path = Path(snapshot.get("planner_brief_path", f"/tmp/{project_name}/.tasks/planner/PLANNER_BRIEF.md"))
        parsed = self._parse_brief(Path(brief_path))
        return BriefState(
            project_name=project_name,
            profile_path=snapshot.get("profile_path", str(resolved_profile)),
            brief_path=str(brief_path),
            title=parsed.get("title", ""),
            owner=parsed.get("owner", ""),
            status=parsed.get("status", ""),
            updated=parsed.get("updated", ""),
            frontstage_disposition=parsed.get("frontstage_disposition", ""),
            user_summary=parsed.get("user_summary", ""),
            action=BriefAction(
                requested_operation=parsed.get("requested_operation", ""),
                target_role=parsed.get("target_role", ""),
                target_instance=parsed.get("target_instance", ""),
                template_id=parsed.get("template_id", ""),
                reason=parsed.get("reason", ""),
                resume_task=parsed.get("resume_task", ""),
            ),
        )

    def check_session(self, *, project_name: str, seat_id: str) -> SessionStatus:
        session_path = Path(os.environ.get("SESSIONS_ROOT", str(Path.home() / ".agents" / "sessions"))) / project_name / seat_id / "session.toml"
        if not session_path.exists():
            return SessionStatus(
                project_name=project_name,
                seat_id=seat_id,
                session_path=str(session_path),
                session_name="",
                exists=False,
                tmux_running=False,
                runtime_dir="",
                workspace="",
                tool="",
                provider="",
                auth_mode="",
            )
        session_data = self._load_toml_like(session_path)
        session_name = session_data.get("session", "")
        running = False
        if session_name:
            probe = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                text=True,
                capture_output=True,
                check=False,
            )
            running = probe.returncode == 0
        return SessionStatus(
            project_name=project_name,
            seat_id=seat_id,
            session_path=str(session_path),
            session_name=session_name,
            exists=True,
            tmux_running=running,
            runtime_dir=session_data.get("runtime_dir", ""),
            workspace=session_data.get("workspace", ""),
            tool=session_data.get("tool", ""),
            provider=session_data.get("provider", ""),
            auth_mode=session_data.get("auth_mode", ""),
        )

    def resolve_planner(self, *, project_name: str, profile_path: str | Path | None = None) -> dict[str, Any]:
        resolved_profile = self.profile_path_for(project_name, profile_path)
        snapshot = self._profile_snapshot(resolved_profile)
        planner = snapshot.get("planner_instance", "")
        if not planner:
            raise RuntimeError(f"unable to resolve planner for project {project_name}")
        session = self.check_session(project_name=project_name, seat_id=planner)
        return {
            "project_name": project_name,
            "profile_path": snapshot.get("profile_path", str(resolved_profile)),
            "planner_instance": planner,
            "active_loop_owner": snapshot.get("active_loop_owner", ""),
            "heartbeat_owner": snapshot.get("heartbeat_owner", ""),
            "seats": snapshot.get("seats", []),
            "session": asdict(session),
        }

    def read_pending_frontstage(
        self,
        *,
        project_name: str,
        profile_path: str | Path | None = None,
    ) -> list[PendingFrontstageItem]:
        path = self._pending_frontstage_path(project_name, profile_path)
        items = self._parse_pending_frontstage(path)
        return [item for item in items if not item.resolved]

    def resolve_frontstage_item(
        self,
        *,
        project_name: str,
        item_id: str,
        resolution: str,
        resolved_by: str,
        profile_path: str | Path | None = None,
    ) -> PendingFrontstageItem:
        if resolved_by not in {"koder", "user"}:
            raise ValueError("resolved_by must be 'koder' or 'user'")
        path = self._pending_frontstage_path(project_name, profile_path)
        items = self._parse_pending_frontstage(path)
        target: PendingFrontstageItem | None = None
        updated: list[PendingFrontstageItem] = []
        for item in items:
            if item.item_id == item_id:
                target = PendingFrontstageItem(
                    item_id=item.item_id,
                    item_type=item.item_type,
                    related_task=item.related_task,
                    summary=item.summary,
                    planner_recommendation=item.planner_recommendation,
                    koder_default_action=item.koder_default_action,
                    user_input_needed=item.user_input_needed,
                    blocking=item.blocking,
                    options=list(item.options),
                    resolved=True,
                    resolved_by=resolved_by,
                    resolved_at=self._utc_now_iso(),
                    resolution=resolution,
                    section="archived",
                )
                updated.append(target)
                continue
            updated.append(item)
        if target is None:
            raise FileNotFoundError(f"pending frontstage item not found: {item_id}")
        self._write_pending_frontstage(path, updated)
        return target

    def _run(self, command: list[str]) -> AdapterResult:
        result = subprocess.run(
            command,
            cwd=str(self.repo_root),
            text=True,
            capture_output=True,
            check=False,
        )
        return AdapterResult(
            command=command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def _run_json(self, command: list[str]) -> dict[str, Any]:
        result = self._run(command)
        if not result.ok:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise RuntimeError(detail)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"expected JSON output from {' '.join(command)}: {exc}") from exc

    def _profile_snapshot(self, profile_path: Path) -> dict[str, Any]:
        # Write profile_path to a temp file to avoid shell injection via special chars
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp.write(str(profile_path))
        tmp.close()
        _tmp_path = tmp.name
        helper = (
            "import importlib.util, json, sys\n"
            "module_path = sys.argv[1]\n"
            "import pathlib\nprofile_path = pathlib.Path(sys.argv[2]).read_text().strip()\n"
            "spec = importlib.util.spec_from_file_location('clawseat_dynamic_common_helper', module_path)\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "assert spec.loader is not None\n"
            "sys.modules[spec.name] = module\n"
            "spec.loader.exec_module(module)\n"
            "profile = module.load_profile(profile_path)\n"
            "preferred = getattr(module, 'preferred_planner_seat', None)\n"
            "planner = preferred(profile) if callable(preferred) else profile.active_loop_owner\n"
            "planner_brief = getattr(profile, 'planner_brief_path', profile.tasks_root / 'planner' / 'PLANNER_BRIEF.md')\n"
            "payload = {\n"
            "  'profile_path': str(profile.profile_path),\n"
            "  'project_name': profile.project_name,\n"
            "  'tasks_root': str(profile.tasks_root),\n"
            "  'planner_brief_path': str(planner_brief),\n"
            "  'active_loop_owner': profile.active_loop_owner,\n"
            "  'heartbeat_owner': profile.heartbeat_owner,\n"
            "  'planner_instance': planner,\n"
            "  'seats': list(profile.seats),\n"
            "}\n"
            "print(json.dumps(payload))\n"
        )
        result = self._run(
            [
                self.python_bin,
                "-c",
                helper,
                str(_get_migration_root() / "dynamic_common.py"),
                _tmp_path,
            ]
        )
        if not result.ok:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise RuntimeError(f"failed to load profile snapshot for {profile_path}: {detail}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid profile snapshot output for {profile_path}: {exc}") from exc

    def _load_toml_like(self, path: Path) -> dict[str, str]:
        data: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value.startswith('"') and raw_value.endswith('"'):
                data[key] = raw_value[1:-1]
            elif raw_value in {"true", "false"}:
                data[key] = raw_value
        return data

    def _parse_brief(self, path: Path) -> dict[str, str]:
        parsed = {
            "title": "",
            "owner": "",
            "status": "",
            "updated": "",
            "frontstage_disposition": "",
            "user_summary": "",
            "requested_operation": "",
            "target_role": "",
            "target_instance": "",
            "template_id": "",
            "reason": "",
            "resume_task": "",
        }
        if not path.exists():
            return parsed
        in_user_summary = False
        summary_lines: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if not parsed["title"] and stripped.startswith("# "):
                parsed["title"] = stripped[2:].strip()
                continue
            for field in (
                "owner",
                "status",
                "updated",
                "frontstage_disposition",
                "requested_operation",
                "target_role",
                "target_instance",
                "template_id",
                "reason",
                "resume_task",
            ):
                prefix = f"{field}:"
                if not parsed[field] and stripped.startswith(prefix):
                    parsed[field] = stripped.split(":", 1)[1].strip()
                    break
            else:
                if stripped == "## 用户摘要":
                    in_user_summary = True
                    continue
                if in_user_summary and stripped.startswith("## "):
                    in_user_summary = False
                    continue
                if in_user_summary:
                    summary_lines.append(stripped)
        parsed["user_summary"] = " ".join(summary_lines).strip()
        return parsed

    def _profile_project_name(self, path: Path) -> str:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        return str(data.get("project_name", "")).strip()

    def _can_execute_for(self, project_name: str) -> bool:
        if self.current_project is None:
            self.current_project = project_name
            return True
        return project_name == self.current_project

    def _queue_operation(
        self,
        *,
        kind: str,
        project_name: str,
        profile_path: str | Path | None,
        payload: dict[str, Any],
    ) -> AdapterResult:
        resolved_profile = self.profile_path_for(project_name, profile_path)
        queued = PendingProjectOperation(
            kind=kind,
            project_name=project_name,
            frontstage_epoch=self.frontstage_epoch,
            profile_path=str(resolved_profile),
            payload=payload,
        )
        self._pending_inbox.setdefault(project_name, []).append(queued)
        current = self.current_project or "<unset>"
        return AdapterResult(
            command=[],
            returncode=0,
            stdout=f"queued {kind} for project {project_name} in pending inbox; current_project={current}; epoch={self.frontstage_epoch}",
            stderr="",
        )

    def _serialize_adapter_result(self, result: AdapterResult) -> dict[str, Any]:
        return {
            "command": result.command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _pending_frontstage_path(self, project_name: str, profile_path: str | Path | None = None) -> Path:
        resolved_profile = self.profile_path_for(project_name, profile_path)
        snapshot = self._profile_snapshot(resolved_profile)
        tasks_root = Path(snapshot.get("tasks_root", f"/tmp/{project_name}/.tasks"))
        return tasks_root / "planner" / "PENDING_FRONTSTAGE.md"

    def _parse_pending_frontstage(self, path: Path) -> list[PendingFrontstageItem]:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        section = ""
        current_heading = ""
        current_lines: list[str] = []
        items: list[PendingFrontstageItem] = []

        def flush() -> None:
            nonlocal current_heading, current_lines
            if not current_heading:
                return
            items.append(self._parse_pending_item(current_heading, current_lines, section))
            current_heading = ""
            current_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped == "## 待处理事项":
                flush()
                section = "pending"
                continue
            if stripped == "## 已归档":
                flush()
                section = "archived"
                continue
            if stripped.startswith("### "):
                flush()
                current_heading = stripped[4:].strip()
                current_lines = []
                continue
            if current_heading:
                current_lines.append(line)
        flush()
        return items

    def _parse_pending_item(self, heading: str, lines: list[str], section: str) -> PendingFrontstageItem:
        fields = {
            "id": heading,
            "type": "",
            "related_task": "",
            "summary": "",
            "planner_recommendation": "",
            "koder_default_action": "",
            "user_input_needed": "false",
            "blocking": "false",
            "resolved": "false",
            "resolved_by": "",
            "resolved_at": "",
            "resolution": "",
        }
        options: list[str] = []
        in_options = False
        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped == "options:":
                in_options = True
                continue
            if in_options and stripped.startswith("- "):
                options.append(stripped[2:].strip())
                continue
            if in_options and ":" in stripped:
                in_options = False
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key in fields:
                    fields[key] = value
        return PendingFrontstageItem(
            item_id=fields["id"] or heading,
            item_type=fields["type"],
            related_task=fields["related_task"],
            summary=fields["summary"],
            planner_recommendation=fields["planner_recommendation"],
            koder_default_action=fields["koder_default_action"],
            user_input_needed=fields["user_input_needed"].lower() == "true",
            blocking=fields["blocking"].lower() == "true",
            options=options,
            resolved=fields["resolved"].lower() == "true",
            resolved_by=fields["resolved_by"],
            resolved_at=fields["resolved_at"],
            resolution=fields["resolution"],
            section=section or "pending",
        )

    def _write_pending_frontstage(self, path: Path, items: list[PendingFrontstageItem]) -> None:
        pending = [item for item in items if item.section != "archived" and not item.resolved]
        archived = [item for item in items if item.section == "archived" or item.resolved]
        lines = [
            "# PENDING_FRONTSTAGE",
            "",
            "## 字段定义",
            "",
            "- `id`: 唯一事项 id，例如 `PF-001`",
            "- `type`: `decision | clarification`",
            "- `related_task`: 关联任务 id",
            "- `summary`: 一句话中文摘要",
            "- `planner_recommendation`: planner 建议方案",
            "- `koder_default_action`: koder 不上浮用户时的默认动作",
            "- `user_input_needed`: `true | false`",
            "- `blocking`: `true | false`",
            "- `options`: 可选项列表",
            "- `resolved`: `true | false`",
            "- `resolved_by`: `koder | user`",
            "- `resolved_at`: ISO timestamp",
            "- `resolution`: 最终决定或补充说明",
            "",
            "## 待处理事项",
            "",
        ]
        if pending:
            for item in pending:
                lines.extend(self._render_pending_item(item))
        lines.extend(
            [
                "## 已归档",
                "",
            ]
        )
        if archived:
            for item in archived:
                lines.extend(self._render_pending_item(item))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _render_pending_item(self, item: PendingFrontstageItem) -> list[str]:
        lines = [
            f"### {item.item_id}",
            f"id: {item.item_id}",
            f"type: {item.item_type}",
            f"related_task: {item.related_task}",
            f"summary: {item.summary}",
            f"planner_recommendation: {item.planner_recommendation}",
            f"koder_default_action: {item.koder_default_action}",
            f"user_input_needed: {'true' if item.user_input_needed else 'false'}",
            f"blocking: {'true' if item.blocking else 'false'}",
            "options:",
        ]
        for option in item.options:
            lines.append(f"  - {option}")
        lines.extend(
            [
                f"resolved: {'true' if item.resolved else 'false'}",
                f"resolved_by: {item.resolved_by}",
                f"resolved_at: {item.resolved_at}",
                f"resolution: {item.resolution}",
                "",
            ]
        )
        return lines

    def _utc_now_iso(self) -> str:
        result = self._run(
            [
                self.python_bin,
                "-c",
                "from datetime import datetime, timezone; print(datetime.now(timezone.utc).replace(microsecond=0).isoformat())",
            ]
        )
        if not result.ok:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise RuntimeError(f"failed to generate UTC timestamp: {detail}")
        return result.stdout.strip()


__all__ = [
    "AdapterResult",
    "BriefAction",
    "BriefState",
    "ClawseatAdapter",
    "PendingFrontstageItem",
    "PendingProjectOperation",
    "SessionStatus",
]
