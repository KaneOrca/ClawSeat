"""
transport.py — ClawSeat transport/window extension interfaces.

Current runtime: OpenClaw (tmux via send-and-verify.sh + iTerm AppleScript).
These Protocol classes define the shape of each layer so alternative runtimes
can be plugged in later without changing callers.

Usage (current, no instantiation needed):
    The default implementations below wrap the existing shell scripts.
    Import and use DefaultTransportAdapter / DefaultWindowAdapter directly.

Extension (future standalone or alternative terminals):
    1. Implement TransportAdapter / WindowAdapter in a new module.
    2. Pass your implementation wherever DefaultTransportAdapter is used.
    No other changes required.
"""
from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclasses.dataclass(slots=True)
class TransportResult:
    ok: bool
    output: str = ""
    error: str = ""

# ---------------------------------------------------------------------------
# Transport layer — how ClawSeat sends messages to seats
# ---------------------------------------------------------------------------

@runtime_checkable
class TransportAdapter(Protocol):
    """
    Abstraction over the mechanism used to push messages into a seat's TUI.

    Current implementation: core/shell-scripts/send-and-verify.sh
    Planned alternatives:
      - OpenClaw built-in tmux skill (avoids shell exec)
      - WebSocket tunnel (future standalone mode)
    """

    def send_message(self, session: str, text: str) -> TransportResult:
        """Send *text* to the tmux session named *session*."""
        ...

    def capture_output(self, session: str, lines: int = 50) -> str:
        """Capture the last *lines* lines of output from *session*."""
        ...


@runtime_checkable
class WindowAdapter(Protocol):
    """
    Abstraction over how ClawSeat opens and arranges terminal windows/tabs.

    Current implementation: iTerm AppleScript via agent_admin.py window commands.
    Planned alternatives:
      - tmux-only mode (no iTerm dependency)
      - VS Code integrated terminal (future standalone mode)
    """

    def open_project_window(self, project: str, seats: list[str]) -> None:
        """Open a window/tab layout for *project* showing *seats*."""
        ...

    def focus_seat(self, project: str, seat: str) -> None:
        """Bring the window/pane for *seat* into focus."""
        ...

# ---------------------------------------------------------------------------
# Default implementations (current runtime: send-and-verify.sh + agent_admin)
# ---------------------------------------------------------------------------

def _clawseat_root() -> Path:
    import os
    root = os.environ.get("CLAWSEAT_ROOT")
    if root:
        return Path(root)
    # Fallback: infer from this file's location (core/transport.py → project root)
    return Path(__file__).resolve().parent.parent


class DefaultTransportAdapter:
    """Wraps core/shell-scripts/send-and-verify.sh."""

    def __init__(self, project: str | None = None):
        self._project = project
        self._send_script = _clawseat_root() / "core" / "shell-scripts" / "send-and-verify.sh"

    def send_message(self, session: str, text: str) -> TransportResult:
        cmd: list[str] = [str(self._send_script)]
        if self._project:
            cmd += ["--project", self._project]
        cmd += [session, text]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return TransportResult(
            ok=result.returncode == 0,
            output=result.stdout.strip(),
            error=result.stderr.strip(),
        )

    def capture_output(self, session: str, lines: int = 50) -> str:
        result = subprocess.run(
            ["/opt/homebrew/bin/tmux", "capture-pane", "-t", session, "-p", "-e"],
            capture_output=True, text=True, check=False,
            env={**__import__("os").environ, "TMUX": ""},
        )
        pane = result.stdout
        return "\n".join(pane.splitlines()[-lines:]) if pane else ""


class DefaultWindowAdapter:
    """
    Wraps agent_admin.py window commands (iTerm AppleScript).

    Extension point: replace with a tmux-only or VS Code adapter.
    """

    def __init__(self, agent_admin_path: Path | str | None = None):
        if agent_admin_path:
            self._agent_admin = Path(agent_admin_path)
        else:
            self._agent_admin = _clawseat_root() / "core" / "scripts" / "agent_admin.py"

    def open_project_window(self, project: str, seats: list[str]) -> None:
        # ClawSeat uses open-monitor for the project overview window.
        subprocess.run(
            ["python3", str(self._agent_admin), "window", "open-monitor", project],
            check=False,
        )

    def focus_seat(self, project: str, seat: str) -> None:
        subprocess.run(
            ["python3", str(self._agent_admin), "window", "open-engineer", seat,
             "--project", project],
            check=False,
        )
