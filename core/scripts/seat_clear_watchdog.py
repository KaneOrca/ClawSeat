#!/usr/bin/env python3
"""Universal pane-content watchdog for [CLEAR-REQUESTED] and [COMPACT-REQUESTED]."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path


MARKER_RE = re.compile(r"\[(CLEAR|COMPACT)-REQUESTED\]")
THINKING_RE = re.compile(r"(thinking|wibbling|working|honking)", re.IGNORECASE)


def _home() -> Path:
    return Path(os.environ.get("CLAWSEAT_REAL_HOME") or os.environ.get("HOME") or str(Path.home())).expanduser()


def _runtime_root() -> Path:
    return Path(os.environ.get("CLAWSEAT_RUNTIME_ROOT") or (_home() / ".agent-runtime")).expanduser()


def _project_names() -> list[str]:
    root = _home() / ".agents" / "projects"
    if not root.exists():
        return []
    return sorted((path.name for path in root.iterdir() if path.is_dir()), key=len, reverse=True)


def _session_project(session: str, projects: list[str]) -> str | None:
    for project in projects:
        if session == project or session.startswith(f"{project}-"):
            return project
    if "-" in session:
        return session.split("-", 1)[0]
    return None


def _list_live_sessions(tmux_bin: str = "tmux") -> list[str]:
    try:
        out = subprocess.check_output(
            [tmux_bin, "list-sessions", "-F", "#{session_name}"],
            text=True,
            env={**os.environ, "TMUX": ""},
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _capture_pane(session: str, *, tmux_bin: str = "tmux", lines: int = 120) -> str:
    try:
        return subprocess.check_output(
            [tmux_bin, "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
            text=True,
            env={**os.environ, "TMUX": ""},
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _send_command(session: str, command: str, *, tmux_bin: str = "tmux") -> None:
    subprocess.run(
        [tmux_bin, "send-keys", "-t", session, command, "Enter"],
        check=True,
        env={**os.environ, "TMUX": ""},
    )


def _marker_line(pane_text: str, match: re.Match[str]) -> str:
    start = pane_text.rfind("\n", 0, match.start()) + 1
    end = pane_text.find("\n", match.end())
    if end < 0:
        end = len(pane_text)
    return pane_text[start:end].strip()


def _marker_hash(session: str, action: str, marker_line: str) -> str:
    seed = f"{session}:{action}:{marker_line}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _seen_path(session: str, runtime_root: Path | None = None) -> Path:
    safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "_", session)
    return (runtime_root or _runtime_root()) / "watchdog" / f"{safe_session}.seen"


def _mark_seen_if_new(session: str, marker_hash: str, runtime_root: Path | None = None) -> bool:
    path = _seen_path(session, runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        seen = {line.strip() for line in handle if line.strip()}
        if marker_hash in seen:
            return False
        handle.write(marker_hash + "\n")
        handle.flush()
        return True


def _scan_session(
    session: str,
    *,
    tmux_bin: str = "tmux",
    lines: int = 120,
    runtime_root: Path | None = None,
    dry_run: bool = False,
) -> tuple[str, str | None]:
    pane_text = _capture_pane(session, tmux_bin=tmux_bin, lines=lines)
    if not pane_text:
        return "empty", None
    if THINKING_RE.search(pane_text):
        return "thinking", None
    match = MARKER_RE.search(pane_text)
    if not match:
        return "none", None

    action = match.group(1).lower()
    command = f"/{action}"
    marker_hash = _marker_hash(session, action, _marker_line(pane_text, match))
    if dry_run:
        print(f"[dry-run] {session}: {command}")
        return "sent", command
    if not _mark_seen_if_new(session, marker_hash, runtime_root):
        return "seen", command
    _send_command(session, command, tmux_bin=tmux_bin)
    print(f"sent {command} to {session}")
    return "sent", command


def scan_once(
    *,
    project: str | None = None,
    tmux_bin: str = "tmux",
    lines: int = 120,
    runtime_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    stats = {"sessions": 0, "sent": 0, "seen": 0, "thinking": 0, "none": 0, "empty": 0}
    projects = _project_names()
    for session in _list_live_sessions(tmux_bin):
        if project:
            if _session_project(session, projects) != project:
                continue
        elif projects and _session_project(session, projects) not in projects:
            continue
        stats["sessions"] += 1
        status, _command = _scan_session(
            session,
            tmux_bin=tmux_bin,
            lines=lines,
            runtime_root=runtime_root,
            dry_run=dry_run,
        )
        stats[status] = stats.get(status, 0) + 1
    return stats


def run_loop(
    *,
    interval: int,
    project: str | None = None,
    tmux_bin: str = "tmux",
    lines: int = 120,
    runtime_root: Path | None = None,
    dry_run: bool = False,
) -> int:
    while True:
        stats = scan_once(
            project=project,
            tmux_bin=tmux_bin,
            lines=lines,
            runtime_root=runtime_root,
            dry_run=dry_run,
        )
        print(" ".join(f"{key}={value}" for key, value in stats.items()))
        time.sleep(interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Scan once and exit.")
    parser.add_argument("--interval", type=int, default=None, help="Run as a daemon, scanning every N seconds.")
    parser.add_argument("--project", help="Limit scan to one project.")
    parser.add_argument("--lines", type=int, default=120, help="Pane tail lines to inspect.")
    parser.add_argument("--tmux-bin", default="tmux", help="tmux executable path.")
    parser.add_argument("--runtime-root", help="Override ~/.agent-runtime for tests.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without tmux send-keys.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else None
    if args.interval is not None and not args.once:
        return run_loop(
            interval=args.interval,
            project=args.project,
            tmux_bin=args.tmux_bin,
            lines=args.lines,
            runtime_root=runtime_root,
            dry_run=args.dry_run,
        )
    stats = scan_once(
        project=args.project,
        tmux_bin=args.tmux_bin,
        lines=args.lines,
        runtime_root=runtime_root,
        dry_run=args.dry_run,
    )
    print(" ".join(f"{key}={value}" for key, value in stats.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
