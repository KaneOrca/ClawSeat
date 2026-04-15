from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
CARTOONER_ADAPTER_ROOT = REPO_ROOT / "adapters" / "cartooner"
CARTOONER_CHECK_SCRIPT = CARTOONER_ADAPTER_ROOT / "scripts" / "check-cartooner-status.sh"
CARTOONER_SUPERVISOR_SCRIPT = CARTOONER_ADAPTER_ROOT / "scripts" / "patrol_supervisor.py"


def detect_claude_onboarding_step(text: str, markers: list[tuple[str, str]]) -> str | None:
    for marker, step in markers:
        if marker in text:
            return step
    return None


def is_claude_onboarding_text(text: str, markers: list[tuple[str, str]]) -> bool:
    return detect_claude_onboarding_step(text, markers) is not None


def capture_session_pane_text(session_name: str) -> str:
    proc = subprocess.run(
        ["tmux", "capture-pane", "-pt", f"{session_name}:0.0", "-S", "-200"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else ""


def wait_for_claude_ui_state(
    session: Any,
    *,
    markers: list[tuple[str, str]],
    timeout_seconds: int = 8,
    stable_reads_required: int = 2,
) -> tuple[str, str | None, bool]:
    last_text = ""
    stable_reads = 0
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        pane_text = capture_session_pane_text(session.session)
        onboarding_step = detect_claude_onboarding_step(pane_text, markers)
        if onboarding_step is not None:
            return pane_text, onboarding_step, False
        if pane_text.strip():
            if pane_text == last_text:
                stable_reads += 1
            else:
                last_text = pane_text
                stable_reads = 1
            if stable_reads >= stable_reads_required:
                return pane_text, None, True
        time.sleep(1)

    final_text = last_text or capture_session_pane_text(session.session)
    return final_text, detect_claude_onboarding_step(final_text, markers), False


def extract_cron_create_success(text: str) -> dict[str, str] | None:
    legacy_matches = list(
        re.finditer(r"Scheduled(?: recurring job)? ([A-Za-z0-9-]+) \(([^)]+)\)", text)
    )
    if legacy_matches:
        match = legacy_matches[-1]
        return {
            "job_id": match.group(1),
            "schedule": match.group(2),
            "line": match.group(0),
        }

    modern_matches = list(
        re.finditer(
            r"Heartbeat loop scheduled [—-] every (\d+) minute(?:s)?, cron job ([A-Za-z0-9-]+)\.",
            text,
        )
    )
    if not modern_matches:
        return None
    match = modern_matches[-1]
    interval = int(match.group(1))
    schedule = "Every minute" if interval == 1 else f"Every {interval} minutes"
    return {
        "job_id": match.group(2),
        "schedule": schedule,
        "line": match.group(0),
    }


def extract_scheduled_task_activity(text: str) -> dict[str, str] | None:
    matches = list(re.finditer(r"Running scheduled task \(([^)]+)\)", text))
    if not matches:
        return None
    match = matches[-1]
    return {
        "at": match.group(1),
        "line": match.group(0),
    }


def line_is_newer(after: str, before: str, line: str) -> bool:
    return after.count(line) > before.count(line)


def verify_heartbeat_install_from_pane(session: Any, previous_text: str) -> dict[str, str] | None:
    for attempt in range(12):
        if attempt:
            time.sleep(1)
        pane_text = capture_session_pane_text(session.session)
        success = extract_cron_create_success(pane_text)
        if success and line_is_newer(pane_text, previous_text, success["line"]):
            return {
                "verification_method": "cron_create_ack",
                "evidence": success["line"],
                "job_id": success["job_id"],
                "schedule": success["schedule"],
            }
    return None


def build_claude_loop_command(manifest: dict) -> str:
    interval = int(manifest.get("interval_minutes", 10))
    workspace = str(manifest.get("workspace", "")).strip()
    active_loop_owner = str(manifest.get("active_loop_owner", "planner")).strip() or "planner"
    heartbeat_md = f"{workspace}/HEARTBEAT.md" if workspace else "HEARTBEAT.md"
    heartbeat_manifest = (
        f"{workspace}/HEARTBEAT_MANIFEST.toml" if workspace else "HEARTBEAT_MANIFEST.toml"
    )
    prompt = (
        f"Read {heartbeat_md} and {heartbeat_manifest}. "
        "Follow HEARTBEAT.md exactly. "
        "Run the listed heartbeat commands as needed. "
        f"If there is no meaningful state change or no real reminder is needed for {active_loop_owner}, "
        "reply exactly HEARTBEAT_OK. "
        f"If there is a real stall or delivery-not-consumed condition, remind {active_loop_owner} only and do not take over dispatch."
    )
    return f"/loop {interval}m {prompt}"


CLAUDE_ONBOARDING_MARKERS: tuple[tuple[str, str], ...] = (
    ("Let's get started.", "welcome"),
    ("Choose the text style", "text_style"),
    ("WARNING: Claude Code running in Bypass Permissions mode", "bypass_permissions"),
    ("Bypass Permissions mode", "bypass_permissions"),
    ("Accessing workspace:", "workspace_trust"),
    ("Quick safety check:", "workspace_trust"),
    ("Browser didn't open? Use the url below to sign in", "oauth_login"),
    ("Paste code here if prompted >", "oauth_code"),
    ("Login successful. Press Enter to continue", "oauth_continue"),
    ("OAuth error:", "oauth_error"),
    ("/theme", "theme_setup"),
)


@dataclass
class HeartbeatHooks:
    error_cls: type[Exception]
    send_and_verify_sh: str
    q: Callable[[str], str]
    q_array: Callable[[list[str]], str]
    ensure_dir: Callable[[Path], None]
    write_text: Callable[[Path, str], None]
    load_toml: Callable[[Path], dict]
    tmux_has_session: Callable[[str], bool]
    find_active_loop_owner: Callable[..., str | None]


class HeartbeatHandlers:
    def __init__(self, hooks: HeartbeatHooks) -> None:
        self.hooks = hooks

    def manifest_path(self, session: Any) -> Path:
        return Path(session.workspace) / "HEARTBEAT_MANIFEST.toml"

    def receipt_path(self, session: Any) -> Path:
        return Path(session.workspace) / "HEARTBEAT_RECEIPT.toml"

    def load_manifest(self, session: Any) -> dict | None:
        path = self.manifest_path(session)
        if not path.exists():
            return None
        return self.hooks.load_toml(path)

    def load_receipt(self, session: Any) -> dict | None:
        path = self.receipt_path(session)
        if not path.exists():
            return None
        return self.hooks.load_toml(path)

    def manifest_fingerprint(self, manifest: dict) -> str:
        encoded = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def install_fingerprint(self, session: Any, manifest: dict) -> str:
        payload = {
            "tool": session.tool,
            "session": session.session,
            "command": build_claude_loop_command(manifest),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def receipt_matches_manifest(self, receipt: dict | None, manifest: dict, session: Any) -> bool:
        if not receipt:
            return False
        if receipt.get("status") != "verified":
            return False
        if str(receipt.get("seat_id", "")) != session.engineer_id:
            return False
        if str(receipt.get("session", "")) != session.session:
            return False
        install_fingerprint = self.install_fingerprint(session, manifest)
        if str(receipt.get("install_fingerprint", "")) == install_fingerprint:
            return True
        return str(receipt.get("manifest_fingerprint", "")) == self.manifest_fingerprint(manifest)

    def write_receipt(
        self,
        session: Any,
        manifest: dict,
        *,
        verification_method: str,
        evidence: str,
        status: str = "verified",
        job_id: str = "",
        schedule: str = "",
    ) -> None:
        receipt_path = self.receipt_path(session)
        lines = [
            "version = 1",
            f"seat_id = {self.hooks.q(session.engineer_id)}",
            f"project = {self.hooks.q(session.project)}",
            f"session = {self.hooks.q(session.session)}",
            f"status = {self.hooks.q(status)}",
            f"manifest_path = {self.hooks.q(str(self.manifest_path(session)))}",
            f"install_fingerprint = {self.hooks.q(self.install_fingerprint(session, manifest))}",
            f"manifest_fingerprint = {self.hooks.q(self.manifest_fingerprint(manifest))}",
            f"verified_at = {self.hooks.q(datetime.now().isoformat(timespec='seconds'))}",
            f"verification_method = {self.hooks.q(verification_method)}",
        ]
        if job_id:
            lines.append(f"job_id = {self.hooks.q(job_id)}")
        if schedule:
            lines.append(f"schedule = {self.hooks.q(schedule)}")
        if evidence:
            lines.append(f"evidence = {self.hooks.q(evidence)}")
        lines.append("")
        self.hooks.write_text(receipt_path, "\n".join(lines))

    def render_heartbeat_text(self, session: Any, project: Any, engineer: Any) -> str | None:
        if not (engineer.patrol_authority and engineer.remind_active_loop_owner):
            return None
        if project.name != "cartooner":
            return None
        active_loop_owner = self.hooks.find_active_loop_owner(project) or "planner"
        frontstage_seat = session.engineer_id or "koder"
        check_script = str(CARTOONER_CHECK_SCRIPT)
        supervisor_script = str(CARTOONER_SUPERVISOR_SCRIPT)
        send_script = str(self.hooks.send_and_verify_sh)
        lines = [
            f"# {session.engineer_id} heartbeat",
            "",
            f"Runtime seat id: `{session.engineer_id}`",
            f"Canonical role: `{engineer.role}`",
        ]
        if engineer.aliases:
            lines.append(f"Aliases: {', '.join(f'`{alias}`' for alias in engineer.aliases)}")
        lines.extend(
            [
                "",
                "Provisioning assets:",
                "",
                "- `HEARTBEAT_MANIFEST.toml` is the desired heartbeat contract.",
                "- `HEARTBEAT_RECEIPT.toml` is the framework-owned verified install receipt.",
                "",
                "When a scheduled heartbeat poll arrives:",
                "",
                "1. Stay in lightweight patrol mode; do not enter plan mode for a routine heartbeat run.",
                "2. Do not re-read `KODER.md` or broad project strategy docs unless the classifier or patrol script returns an ambiguous contradiction that cannot be resolved from the scripted facts.",
                f"3. Run `{check_script}` as the first-pass classifier.",
                f"4. Use `{supervisor_script}` to decide whether `{active_loop_owner}` actually needs a reminder.",
                "5. If patrol shows no meaningful state change or no real stall, reply exactly `HEARTBEAT_OK`.",
                f"6. If patrol shows a real delivery-not-consumed or stalled-seat condition, use `{frontstage_seat}`'s unblock authority to clear the procedural wait and remind `{active_loop_owner}` if needed; do not take over dispatch or next-hop planning.",
                "7. Only if the scripts fail or disagree, read the smallest necessary project docs (`TASKS.md` / `STATUS.md` first) and return a short blocker summary instead of loading the full frontstage context.",
                "",
                "Reliable handoff model:",
                "",
                "- `assigned` = target `TODO.md` exists",
                f"- `notified` = `{send_script}` returned success",
                "- `consumed` = target seat durable ACK exists in `TODO.md`",
                "- only `assigned + notified + consumed` counts as a healthy handoff",
                "",
                "Review verdict routing matrix:",
                "",
                f"- `APPROVED` -> `{frontstage_seat}`",
                f"- `APPROVED_WITH_NITS` -> `{frontstage_seat}`",
                "- `CHANGES_REQUESTED` -> builder seat",
                f"- `BLOCKED` -> `{frontstage_seat}`",
                f"- `DECISION_NEEDED` -> `{frontstage_seat}`",
                f"- Reviewer seat only delivers the verdict; `{active_loop_owner}` still chooses the next hop",
                "",
                "Default heartbeat commands:",
                "",
                "```bash",
                f"python {supervisor_script}",
                f"python {supervisor_script} --send",
                "```",
                "",
                "Guardrails:",
                "",
                f"- `{active_loop_owner}` remains the active loop owner and decision owner.",
                f"- `{frontstage_seat}` owns confirmations, approvals, reminders, and other procedural unblock actions.",
                "- Do not write downstream specialist TODOs from a heartbeat run.",
                "- Do not change TASKS.md or STATUS.md unless the patrol protocol explicitly requires a supervision note.",
                "- Keep heartbeat replies short and factual; avoid restating full project context on every poll.",
                "- If there is no real reminder to send, stay silent with `HEARTBEAT_OK`.",
            ]
        )
        return "\n".join(lines) + "\n"

    def render_heartbeat_manifest_text(
        self,
        session: Any,
        project: Any,
        engineer: Any,
        *,
        project_engineers: dict[str, Any] | None = None,
        engineer_order: list[str] | None = None,
    ) -> str | None:
        if not (engineer.patrol_authority and engineer.remind_active_loop_owner):
            return None
        if project.name != "cartooner":
            return None

        active_loop_owner = (
            self.hooks.find_active_loop_owner(
                project,
                project_engineers=project_engineers,
                engineer_order=engineer_order,
            )
            or "planner"
        )
        commands = [
            f"python {CARTOONER_SUPERVISOR_SCRIPT}",
            f"python {CARTOONER_SUPERVISOR_SCRIPT} --send",
        ]
        lines = [
            "version = 1",
            f"seat_id = {self.hooks.q(session.engineer_id)}",
            f"project = {self.hooks.q(project.name)}",
            f"role = {self.hooks.q(engineer.role)}",
            f"aliases = {self.hooks.q_array(engineer.aliases)}",
            'kind = "heartbeat"',
            "enabled = true",
            "interval_minutes = 10",
            f"active_loop_owner = {self.hooks.q(active_loop_owner)}",
            'expected_idle_reply = "HEARTBEAT_OK"',
            f"workspace = {self.hooks.q(session.workspace)}",
            f"repo_root = {self.hooks.q(project.repo_root)}",
            f"receipt_path = {self.hooks.q(str(self.receipt_path(session)))}",
            f"patrol_entrypoint = {self.hooks.q(str(CARTOONER_CHECK_SCRIPT))}",
            f"supervisor_entrypoint = {self.hooks.q(str(CARTOONER_SUPERVISOR_SCRIPT))}",
            f"send_script = {self.hooks.q(str(self.hooks.send_and_verify_sh))}",
            f"commands = {self.hooks.q_array(commands)}",
            f"human_facing = {'true' if engineer.human_facing else 'false'}",
            f"patrol_authority = {'true' if engineer.patrol_authority else 'false'}",
            f"unblock_authority = {'true' if engineer.unblock_authority else 'false'}",
            f"remind_active_loop_owner = {'true' if engineer.remind_active_loop_owner else 'false'}",
            f"dispatch_authority = {'true' if engineer.dispatch_authority else 'false'}",
            f"active_loop_owner_authority = {'true' if engineer.active_loop_owner else 'false'}",
            "",
        ]
        return "\n".join(lines)

    def provision_session_heartbeat(
        self,
        session: Any,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        if session.tool != "claude":
            return False, f"{session.engineer_id}: heartbeat provisioning currently targets Claude sessions only"

        manifest = self.load_manifest(session)
        if not manifest:
            return False, f"{session.engineer_id}: no HEARTBEAT_MANIFEST.toml present"

        if not self.hooks.tmux_has_session(session.session):
            return False, f"{session.engineer_id}: session {session.session} is not running"

        pane_text, onboarding_step, pane_stable = wait_for_claude_ui_state(
            session,
            markers=list(CLAUDE_ONBOARDING_MARKERS),
        )
        if onboarding_step is not None:
            return (
                False,
                f"{session.engineer_id}: Claude onboarding still visible ({onboarding_step}); finish onboarding before provisioning heartbeat",
            )
        if not pane_stable:
            return (
                False,
                f"{session.engineer_id}: Claude UI is still settling; retry heartbeat provisioning after the TUI reaches a stable prompt",
            )

        receipt = self.load_receipt(session)
        if self.receipt_matches_manifest(receipt, manifest, session) and not force:
            return (
                False,
                f"{session.engineer_id}: heartbeat already verified in {self.receipt_path(session)}",
            )

        if not force:
            existing_ack = extract_cron_create_success(pane_text)
            receipt_job_id = str(receipt.get("job_id", "")) if receipt else ""
            receipt_install_fingerprint = str(receipt.get("install_fingerprint", "")) if receipt else ""
            if existing_ack and (
                not receipt
                or not receipt_install_fingerprint
                or existing_ack["job_id"] != receipt_job_id
            ):
                self.write_receipt(
                    session,
                    manifest,
                    verification_method="pane_cron_ack_reconcile",
                    evidence=existing_ack["line"],
                    job_id=existing_ack["job_id"],
                    schedule=existing_ack["schedule"],
                )
                return (
                    True,
                    f"{session.engineer_id}: reconciled existing heartbeat from pane ack into {self.receipt_path(session)}",
                )
            existing_activity = extract_scheduled_task_activity(pane_text)
            if existing_activity and not receipt:
                self.write_receipt(
                    session,
                    manifest,
                    verification_method="pane_activity_reconcile",
                    evidence=existing_activity["line"],
                )
                return (
                    True,
                    f"{session.engineer_id}: reconciled existing heartbeat activity into {self.receipt_path(session)}",
                )

        command = build_claude_loop_command(manifest)
        if dry_run:
            return True, command

        previous_text = pane_text
        result = subprocess.run(
            [self.hooks.send_and_verify_sh, session.session, command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            detail = stderr or stdout or "unknown send failure"
            raise self.hooks.error_cls(
                f"Heartbeat provision failed for {session.engineer_id}: {detail}"
            )

        verification = verify_heartbeat_install_from_pane(session, previous_text)
        if verification:
            self.write_receipt(
                session,
                manifest,
                verification_method=verification["verification_method"],
                evidence=verification["evidence"],
                job_id=verification.get("job_id", ""),
                schedule=verification.get("schedule", ""),
            )
            detail = (
                f"{session.engineer_id}: heartbeat verified and recorded in {self.receipt_path(session)}"
            )
            return True, detail

        return (
            False,
            f"{session.engineer_id}: /loop command was sent but no verifiable install ack was observed; inspect {session.session} before treating heartbeat as installed",
        )
