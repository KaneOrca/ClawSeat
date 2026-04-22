from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


TMUX_COMMAND_RETRIES = 2
TMUX_COMMAND_TIMEOUT_SECONDS = 8.0
TMUX_COMMAND_RETRY_DELAY_SECONDS = 1.0

# ── iTerm integration ─────────────────────────────────────────────────────────

_ITERM_CLOSE_SCRIPT_TEMPLATE = """\
tell application "iTerm"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if tty of s is "{tty}" then
                    close t
                    return "ok"
                end if
            end repeat
        end repeat
    end repeat
    return "not_found"
end tell\
"""


def _get_tmux_tty(session_name: str) -> str | None:
    """Return the tty of the first attached client for a tmux session, or None."""
    try:
        result = subprocess.run(
            ["tmux", "list-clients", "-t", session_name, "-F", "#{client_tty}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0].strip() or None
    except Exception:  # silent-ok: best-effort tty lookup; missing client is normal (no attached client)
        pass
    return None


def _close_iterm_tab_by_tty(tty: str) -> dict:
    """Close the iTerm tab owning the given tty via osascript.

    Returns {"status": "ok"|"not_found"|"error", "detail": str|None}.
    Never raises — all errors are returned in the dict.
    """
    script = _ITERM_CLOSE_SCRIPT_TEMPLATE.format(tty=tty)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "detail": result.stderr.strip() or f"rc={result.returncode}",
            }
        output = result.stdout.strip()
        if output == "ok":
            return {"status": "ok", "detail": None}
        return {"status": "not_found", "detail": output}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


class SessionStartError(RuntimeError):
    """Raised when a seat session cannot be created into a verified running tmux state."""


@dataclass
class SessionHooks:
    agentctl_path: str
    launcher_path: str
    load_project: Callable[[str], Any]
    apply_template: Callable[[Any, Any], None]
    reconcile_session_runtime: Callable[[Any], Any]
    ensure_api_secret_ready: Callable[[Any], None]
    write_session: Callable[[Any], None]
    load_project_sessions: Callable[[str], dict[str, Any]]
    project_template_context: Callable[[Any], Any]
    load_engineers: Callable[[], dict[str, Any]]
    tmux_has_session: Callable[[str], bool]
    build_monitor_layout: Callable[[Any, dict[str, Any]], None]


class SessionService:
    def __init__(self, hooks: SessionHooks) -> None:
        self.hooks = hooks

    def _run_tmux_with_retry(
        self,
        args: list[str],
        *,
        reason: str,
        check: bool = False,
        retries: int = TMUX_COMMAND_RETRIES,
        timeout: float = TMUX_COMMAND_TIMEOUT_SECONDS,
    ) -> subprocess.CompletedProcess:
        last: subprocess.CompletedProcess | None = None
        for attempt in range(1, retries + 1):
            if not check:
                try:
                    return subprocess.run(
                        ["tmux", *args],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                except subprocess.TimeoutExpired as exc:
                    print(
                        f"tmux_retry: {reason} attempt={attempt}/{retries} timeout={timeout}s",
                        file=sys.stderr,
                    )
                    if attempt >= retries:
                        raise SessionStartError(
                            f"{reason} timeout after {retries} attempt(s) for args={args}"
                        ) from exc
                except OSError as exc:
                    raise SessionStartError(f"{reason} failed before executing tmux: {exc}") from exc
                if attempt < retries:
                    time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)
                    continue
                raise SessionStartError(f"{reason} failed for tmux args={args}")
            try:
                result = subprocess.run(
                    ["tmux", *args],
                    check=check,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if result.returncode == 0:
                    return result
                last = result
            except subprocess.CalledProcessError as exc:
                last = exc
            except subprocess.TimeoutExpired as exc:
                last = None
                print(
                    f"tmux_retry: {reason} attempt={attempt}/{retries} timeout={timeout}s",
                    file=sys.stderr,
                )
                if attempt >= retries:
                    raise SessionStartError(
                        f"{reason} timeout after {retries} attempt(s) for args={args}"
                    ) from exc
            except OSError as exc:
                raise SessionStartError(f"{reason} failed before executing tmux: {exc}") from exc
            else:
                if result.returncode == 0:
                    return result
                print(
                    f"tmux_retry: {reason} attempt={attempt}/{retries} rc={result.returncode}",
                    file=sys.stderr,
                )
            if attempt < retries:
                time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)

        if last is not None:
            detail = (last.stderr or last.stdout or "").strip()
            raise SessionStartError(
                f"{reason} failed after {retries} attempt(s), exit={last.returncode}, detail={detail}, args={args}"
            )
        raise SessionStartError(f"{reason} failed for tmux args={args}")

    def _session_window_state(self, session_name: str) -> str:
        if not self.hooks.tmux_has_session(session_name):
            return "session=missing"
        result = self._run_tmux_with_retry(
            ["list-panes", "-t", session_name, "-F", "#{session_name}|#{pane_id}|#{pane_current_command}"],
            reason=f"snapshot session windows for {session_name}",
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"session={session_name}, panes={result.stdout.strip()}"
        return f"session={session_name}, panes=empty"

    def _assert_session_running(self, session: Any, *, operation: str) -> None:
        if not self.hooks.tmux_has_session(session.session):
            raise SessionStartError(
                f"{operation} failed for '{session.session}': session missing after startup; state={self._session_window_state(session.session)}"
            )
        output = self._run_tmux_with_retry(
            [
                "list-panes",
                "-t",
                session.session,
                "-F",
                "#{pane_id}|#{pane_current_command}",
            ],
            reason=f"{operation} verify panes for {session.session}",
            check=False,
        )
        if output.returncode != 0 or not output.stdout.strip():
            raise SessionStartError(
                f"{operation} failed for '{session.session}': no active panes detected; state={self._session_window_state(session.session)}"
            )

    def _parse_env_file(self, path: str) -> dict[str, str]:
        values: dict[str, str] = {}
        if not path:
            return values
        env_path = Path(path)
        if not env_path.exists():
            return values
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, sep, value = line.partition("=")
            if not sep:
                continue
            values[key.strip()] = shlex.split(value.strip(), posix=True)[0] if value.strip() else ""
        return values

    def _launcher_auth_for(self, session: Any) -> str:
        if session.tool == "claude":
            if session.auth_mode == "oauth":
                return "oauth"
            if session.auth_mode == "oauth_token":
                return "oauth_token"
            if session.auth_mode == "ccr":
                return "custom"
            if session.auth_mode == "api":
                # Keep Claude API seats aligned with install.sh: all non-oauth
                # Claude providers land in the same launcher "custom" sandbox
                # namespace, keyed by session name rather than provider label.
                return "custom"
        if session.tool == "codex":
            if session.auth_mode == "oauth":
                return "chatgpt"
            if session.auth_mode == "api":
                return "custom"
        if session.tool == "gemini":
            if session.auth_mode == "oauth":
                return "oauth"
            if session.auth_mode == "api":
                return {
                    "google-api-key": "primary",
                }.get(session.provider, "custom")
        raise SessionStartError(
            f"unsupported launcher auth mapping for {session.engineer_id}: "
            f"tool={session.tool} auth_mode={session.auth_mode} provider={session.provider}"
        )

    def _launcher_secret_target(self, session: Any, launcher_auth: str) -> Path | None:
        operator_home = Path.home()
        if session.tool == "claude":
            if launcher_auth == "oauth_token":
                return operator_home / ".agents" / ".env.global"
        if session.tool == "gemini" and launcher_auth == "primary":
            return operator_home / ".agent-runtime" / "secrets" / "gemini" / "primary.env"
        return None

    def _sync_launcher_secret_file(self, session: Any, launcher_auth: str) -> None:
        if not session.secret_file:
            return
        source = Path(session.secret_file)
        target = self._launcher_secret_target(session, launcher_auth)
        if target is None or not source.exists() or not source.read_text(encoding="utf-8").strip():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        target.chmod(0o600)

    def _custom_env_payload(self, session: Any) -> dict[str, str]:
        if session.tool == "claude" and session.auth_mode == "ccr":
            return {
                "LAUNCHER_CUSTOM_API_KEY": "ccr-local-dummy",
                "LAUNCHER_CUSTOM_BASE_URL": os.environ.get("CLAWSEAT_CCR_BASE_URL", "http://127.0.0.1:3456"),
            }

        secret_env = self._parse_env_file(session.secret_file)
        if session.tool == "claude":
            api_key = (
                secret_env.get("ANTHROPIC_AUTH_TOKEN")
                or secret_env.get("ANTHROPIC_API_KEY")
                or secret_env.get("OPENAI_API_KEY")
            )
            if not api_key:
                raise SessionStartError(
                    f"custom launcher env for {session.engineer_id} is missing a Claude-compatible API key"
                )
            payload = {
                "LAUNCHER_CUSTOM_API_KEY": api_key,
            }
            base_url = (
                secret_env.get("ANTHROPIC_BASE_URL")
                or secret_env.get("OPENAI_BASE_URL")
                or secret_env.get("OPENAI_API_BASE")
                or ""
            )
            if session.provider == "anthropic-console" and not base_url:
                base_url = "https://api.anthropic.com"
            if session.provider == "minimax" and not base_url:
                base_url = "https://api.minimaxi.com/anthropic"
            if session.provider == "xcode-best" and not base_url:
                base_url = "https://xcode.best"
            if base_url:
                payload["LAUNCHER_CUSTOM_BASE_URL"] = base_url
            model = secret_env.get("ANTHROPIC_MODEL") or secret_env.get("OPENAI_MODEL", "")
            if session.provider == "minimax" and not model:
                model = "MiniMax-M2.7-highspeed"
            if model:
                payload["LAUNCHER_CUSTOM_MODEL"] = model
            return payload

        if session.tool == "codex":
            api_key = secret_env.get("OPENAI_API_KEY", "")
            if not api_key:
                raise SessionStartError(
                    f"custom launcher env for {session.engineer_id} is missing OPENAI_API_KEY"
                )
            base_url = (
                secret_env.get("OPENAI_BASE_URL")
                or secret_env.get("OPENAI_API_BASE")
                or ""
            )
            if session.provider == "xcode-best" and not base_url:
                base_url = "https://api.xcode.best/v1"
            payload = {
                "LAUNCHER_CUSTOM_API_KEY": api_key,
                "LAUNCHER_CUSTOM_BASE_URL": base_url or "https://api.openai.com/v1",
            }
            model = secret_env.get("OPENAI_MODEL", "") or getattr(session, "_template_model", "")
            if session.provider == "xcode-best" and not model:
                model = "gpt-5.4"
            if model:
                payload["LAUNCHER_CUSTOM_MODEL"] = model
            return payload

        if session.tool == "gemini":
            api_key = secret_env.get("GEMINI_API_KEY") or secret_env.get("GOOGLE_API_KEY", "")
            if not api_key:
                raise SessionStartError(
                    f"custom launcher env for {session.engineer_id} is missing GEMINI_API_KEY / GOOGLE_API_KEY"
                )
            payload = {
                "LAUNCHER_CUSTOM_API_KEY": api_key,
                "LAUNCHER_CUSTOM_BASE_URL": secret_env.get(
                    "GOOGLE_GEMINI_BASE_URL",
                    secret_env.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"),
                ),
            }
            model = secret_env.get("GEMINI_MODEL", "") or getattr(session, "_template_model", "")
            if model:
                payload["LAUNCHER_CUSTOM_MODEL"] = model
            return payload

        raise SessionStartError(f"custom launcher env not implemented for tool={session.tool}")

    def _write_launcher_custom_env_file(self, session: Any) -> str:
        safe_session = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in session.session)
        payload = self._custom_env_payload(session)
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            prefix=f"agent-admin-custom-{safe_session}.",
            dir="/tmp",
            delete=False,
            encoding="utf-8",
        )
        try:
            for key, value in payload.items():
                handle.write(f"export {key}={shlex.quote(value)}\n")
        finally:
            handle.close()
        os.chmod(handle.name, 0o600)
        return handle.name

    def _launcher_runtime_dir(self, session: Any, launcher_auth: str) -> Path | None:
        operator_home = Path.home()
        if session.tool == "claude":
            if launcher_auth == "oauth":
                return None
            if launcher_auth == "oauth_token":
                return operator_home / ".agent-runtime" / "identities" / "claude" / "oauth_token" / f"{launcher_auth}-{session.session}"
            return operator_home / ".agent-runtime" / "identities" / "claude" / "api" / f"{launcher_auth}-{session.session}"
        if session.tool == "codex":
            if launcher_auth == "chatgpt":
                return None
            return operator_home / ".agent-runtime" / "identities" / "codex" / "api" / f"{launcher_auth}-{session.session}"
        if session.tool == "gemini":
            if launcher_auth == "oauth":
                return None
            return operator_home / ".agent-runtime" / "identities" / "gemini" / "api" / f"{launcher_auth}-{session.session}"
        return None

    def build_engineer_exec(self, session: Any) -> list[str]:
        if session.wrapper:
            return [session.wrapper]
        return [self.hooks.agentctl_path, "run-engineer", "--project", session.project, session.engineer_id]

    def start_engineer(self, session: Any, reset: bool = False) -> None:
        session = self.hooks.reconcile_session_runtime(session)
        self.hooks.ensure_api_secret_ready(session)
        project = self.hooks.load_project(session.project)
        self.hooks.apply_template(session, project)
        if reset and self.hooks.tmux_has_session(session.session):
            self._run_tmux_with_retry(
                ["kill-session", "-t", session.session],
                reason=f"reset existing session {session.session}",
                check=False,
            )
        if self.hooks.tmux_has_session(session.session):
            self._assert_session_running(session, operation=f"start_engineer idempotent check for {session.session}")
            return
        launcher_auth = self._launcher_auth_for(session)
        runtime_dir = self._launcher_runtime_dir(session, launcher_auth)
        if runtime_dir is not None and session.runtime_dir != str(runtime_dir):
            session.runtime_dir = str(runtime_dir)
            self.hooks.write_session(session)
            self.hooks.apply_template(session, project)
        for attempt in range(1, TMUX_COMMAND_RETRIES + 1):
            custom_env_file = ""
            try:
                self._sync_launcher_secret_file(session, launcher_auth)
                if launcher_auth == "custom":
                    custom_env_file = self._write_launcher_custom_env_file(session)
                cmd = [
                    "bash",
                    self.hooks.launcher_path,
                    "--headless",
                    "--tool",
                    session.tool,
                    "--auth",
                    launcher_auth,
                    "--dir",
                    session.workspace,
                    "--session",
                    session.session,
                ]
                if custom_env_file:
                    cmd.extend(["--custom-env-file", custom_env_file])
                env = dict(os.environ)
                env["CLAWSEAT_ROOT"] = str(Path(self.hooks.launcher_path).resolve().parents[2])
                result = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=TMUX_COMMAND_TIMEOUT_SECONDS,
                    env=env,
                )
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "").strip()
                    raise SessionStartError(
                        f"start engineer {session.session} via launcher failed, "
                        f"exit={result.returncode}, detail={detail}"
                    )
                self._assert_session_running(session, operation=f"start engineer {session.session}")
                break
            except SessionStartError as exc:
                last_error = exc
                if self.hooks.tmux_has_session(session.session):
                    self._run_tmux_with_retry(
                        ["kill-session", "-t", session.session],
                        reason=f"cleanup partial session {session.session}",
                        check=False,
                    )
                if attempt < TMUX_COMMAND_RETRIES:
                    print(
                        f"start_engineer_retry: session={session.session} attempt={attempt}/"
                        f"{TMUX_COMMAND_RETRIES} rc_waiting=retry",
                        file=sys.stderr,
                    )
                    time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)
                    continue
                detail = self._session_window_state(session.session)
                raise SessionStartError(
                    f"start engineer '{session.session}' failed after {TMUX_COMMAND_RETRIES} attempts; "
                    f"window_state={detail}; reason={exc}"
                ) from exc
            finally:
                if custom_env_file and os.path.exists(custom_env_file):
                    os.unlink(custom_env_file)
        # Enable tmux terminal titles so iTerm tabs show session name.
        # set-titles-string '#{session_name}' uses the session identifier as the tab title.
        self._run_tmux_with_retry(
            ["set", "-g", "set-titles", "on"],
            reason=f"enable titles on {session.session}",
            check=False,
        )
        self._run_tmux_with_retry(
            ["set", "-g", "set-titles-string", "#{session_name}"],
            reason=f"set session title on {session.session}",
            check=False,
        )

    def stop_engineer(self, session: Any, *, close_iterm_tab: bool = False) -> None:
        if close_iterm_tab:
            tty = _get_tmux_tty(session.session)
            if tty:
                result = _close_iterm_tab_by_tty(tty)
                if result["status"] == "ok":
                    print(f"iterm_tab_closed: tty={tty} session={session.session}")
                elif result["status"] == "not_found":
                    print(
                        f"warn: iterm_tab_not_found: tty={tty} session={session.session}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"warn: iterm_tab_close_failed: tty={tty} session={session.session} detail={result['detail']}",
                        file=sys.stderr,
                    )
        self._run_tmux_with_retry(
            ["kill-session", "-t", session.session],
            reason=f"stop engineer {session.session}",
            check=False,
        )

    def status(self, session: Any) -> str:
        return "running" if self.hooks.tmux_has_session(session.session) else "stopped"

    def project_engineer_context(self, project: Any) -> tuple[dict[str, Any], list[str]]:
        context = self.hooks.project_template_context(project)
        if context:
            template_profiles, engineer_order, _ = context
            return template_profiles, engineer_order
        engineers = self.hooks.load_engineers()
        return engineers, list(project.engineers)

    def project_autostart_engineer_ids(self, project: Any, *, ensure_monitor: bool = False) -> list[str]:
        engineer_map, engineer_order = self.project_engineer_context(project)
        ordered_ids = [engineer_id for engineer_id in engineer_order if engineer_id in project.engineers]
        if not ordered_ids:
            ordered_ids = list(project.engineers)

        if ensure_monitor and project.window_mode != "tabs-1up":
            # Skip frontstage engineers (koder/frontstage) — they are
            # OpenClaw-managed agents, not tmux seats. Auto-spawning them
            # creates a ghost tmux session that displaces the real OpenClaw
            # identity. See agent_admin_window._is_frontstage_engineer.
            visible_ids = [
                engineer_id
                for engineer_id in project.monitor_engineers[: max(1, project.monitor_max_panes)]
                if engineer_id in project.engineers
                and engineer_id not in {"koder", "frontstage"}
            ]
            if visible_ids:
                return visible_ids

        frontstage_ids = [
            engineer_id
            for engineer_id in ordered_ids
            if engineer_map.get(engineer_id)
            and engineer_map[engineer_id].patrol_authority
            and engineer_map[engineer_id].remind_active_loop_owner
        ]
        if frontstage_ids:
            return frontstage_ids

        human_facing_ids = [
            engineer_id
            for engineer_id in ordered_ids
            if engineer_map.get(engineer_id) and engineer_map[engineer_id].human_facing
        ]
        if human_facing_ids:
            return human_facing_ids[:1]

        return ordered_ids[:1]

    def start_project(self, project: Any, ensure_monitor: bool = True, reset: bool = False) -> None:
        sessions = self.hooks.load_project_sessions(project.name)
        start_ids = self.project_autostart_engineer_ids(project, ensure_monitor=ensure_monitor)
        for engineer_id in start_ids:
            if engineer_id in sessions:
                self.start_engineer(sessions[engineer_id], reset=reset)
        if (
            ensure_monitor
            and project.window_mode != "tabs-1up"
            and (reset or not self.hooks.tmux_has_session(project.monitor_session))
        ):
            self._start_monitor_with_retry(project, sessions, reset=reset)

    def seat_requires_launch_confirmation(self, project: Any, engineer_id: str) -> bool:
        engineer_map, _ = self.project_engineer_context(project)
        engineer = engineer_map.get(engineer_id)
        if engineer is None:
            return True
        return not (engineer.patrol_authority and engineer.remind_active_loop_owner)

    def _start_monitor_with_retry(self, project: Any, sessions: dict[str, Any], *, reset: bool) -> None:
        last_error: SessionStartError | None = None
        for attempt in range(1, TMUX_COMMAND_RETRIES + 1):
            try:
                if reset and self.hooks.tmux_has_session(project.monitor_session):
                    self._run_tmux_with_retry(
                        ["kill-session", "-t", project.monitor_session],
                        reason=f"recycle monitor session {project.monitor_session}",
                        check=False,
                    )
                if self.hooks.tmux_has_session(project.monitor_session):
                    # Re-run layout from scratch to avoid partial state.
                    self._run_tmux_with_retry(
                        ["kill-session", "-t", project.monitor_session],
                        reason=f"rebuild monitor session {project.monitor_session}",
                        check=False,
                    )
                self.hooks.build_monitor_layout(project, sessions)
                if not self.hooks.tmux_has_session(project.monitor_session):
                    raise SessionStartError(
                        f"monitor session {project.monitor_session} missing after layout build"
                    )
                # Verify monitor session contains at least one pane.
                monitor_state = self._session_window_state(project.monitor_session)
                if ", panes=empty" in monitor_state:
                    raise SessionStartError(f"monitor session empty after layout build: {monitor_state}")
                return
            except Exception as exc:
                wrapped_error = exc if isinstance(exc, SessionStartError) else SessionStartError(str(exc))
                window_state = self._session_window_state(project.monitor_session)
                last_error = SessionStartError(
                    f"monitor session '{project.monitor_session}' error={wrapped_error}; window_state={window_state}"
                )
                if self.hooks.tmux_has_session(project.monitor_session):
                    self._run_tmux_with_retry(
                        ["kill-session", "-t", project.monitor_session],
                        reason=f"cleanup monitor session {project.monitor_session}",
                        check=False,
                    )
                if attempt < TMUX_COMMAND_RETRIES:
                    print(
                        f"start_monitor_retry: project={project.name} attempt={attempt}/{TMUX_COMMAND_RETRIES}",
                        file=sys.stderr,
                    )
                    time.sleep(TMUX_COMMAND_RETRY_DELAY_SECONDS)
                    continue
        raise SessionStartError(
            f"start monitor for {project.name} failed after {TMUX_COMMAND_RETRIES} attempts; reason={last_error}"
        ) from last_error
