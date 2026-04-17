"""Shared utilities — file I/O, subprocess, TOML quoting.

Extracted from _common.py. All harness scripts import these via _common.py
re-exports, so backward compatibility is preserved.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


# ── Path constants ───────────────────────────────────────────────────

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

# ── Regex constants ──────────────────────────────────────────────────

TASK_ROW_RE = re.compile(r"^\|\s*([A-Za-z0-9_-]+)\s*\|")
CONSUMED_RE = re.compile(
    r"^Consumed:\s*(?P<task_id>\S+)\s+from\s+(?P<source>\S+)\s+at\s+(?P<ts>.+)$"
)
PLACEHOLDER_RE = re.compile(r"\{([A-Z0-9_]+)\}")


# ── TOML quoting (unified, safe for all strings including newlines) ──

def q(value: object) -> str:
    """Quote a value for TOML embedding. Uses json.dumps for correct escaping."""
    return json.dumps(value, ensure_ascii=False)


def q_array(values: Iterable[str]) -> str:
    """Format a list of strings as a TOML array."""
    return "[" + ", ".join(q(v) for v in values) + "]"


# ── Time ─────────────────────────────────────────────────────────────

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── File I/O ─────────────────────────────────────────────────────────

def sanitize_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ── Subprocess ───────────────────────────────────────────────────────

def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return run_command_with_env(args, cwd=cwd, env={"HOME": str(AGENT_HOME)})


def run_command_with_env(
    args: list[str],
    *,
    cwd: Path | str | None = None,
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
    """Raise RuntimeError on any non-zero exit."""
    if result.returncode == 0:
        return
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    detail = stderr or stdout or f"exit {result.returncode}"
    raise RuntimeError(f"{what} failed: {detail}")


def require_success_allow_skip(result: subprocess.CompletedProcess[str], what: str) -> None:
    """Like require_success but tolerates exit code 2 (transport skipped)."""
    if result.returncode == 0:
        return
    if result.returncode == 2:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or "skipped"
        print(f"warn: {what} skipped: {detail}", file=sys.stderr)
        return
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    detail = stderr or stdout or f"exit {result.returncode}"
    raise RuntimeError(f"{what} failed: {detail}")


# ── Misc helpers ─────────────────────────────────────────────────────

def summarize_status_lines(lines: Iterable[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def executable_command(path: Path, *extra_args: str) -> list[str]:
    if path.suffix == ".py":
        return ["python3", str(path), *extra_args]
    return [str(path), *extra_args]
