"""Tests for core/launchers/ — the merged desktop launcher.

Covers portability (no hardcoded user paths), thin-wrapper correctness,
dry-run output shape, and env-var overrides for fuzzy roots / favorites.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_LAUNCHERS = _REPO / "core" / "launchers"
_DETERMINISTIC_LAUNCHER_SOURCES = (
    "agent-launcher.sh",
    "agent-launcher-common.sh",
    "agent-launcher-fuzzy.py",
)
_FORBIDDEN_INTERACTIVE_PATTERNS = (
    "osascript",
    "AppleScript",
    "display dialog",
    "choose from list",
    "choose folder",
    "curses",
    "launcher_choose_",
    "launcher_prompt_",
    "--prompt-auth",
)


# ─────────────────────────────────────────────────────────────────────
# Portability — no hard-coded /Users/ywf paths outside legacy fallbacks
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "agent-launcher.sh",
    "agent-launcher-common.sh",
    "agent-launcher-discover.py",
    "agent-launcher-fuzzy.py",
    "claude.sh",
    "codex.sh",
    "gemini.sh",
])
def test_no_hardcoded_user_paths(name):
    """Source must not reference /Users/ywf anywhere — clawseat is multi-user."""
    path = _LAUNCHERS / name
    text = path.read_text()
    assert "/Users/ywf" not in text, (
        f"{name}: hard-coded /Users/ywf path found — not portable"
    )


def test_desktop_references_are_legacy_or_workspace_bookmark_only():
    """Every Desktop/ appearance must fall into one of 3 legitimate buckets:

      1. Header/comment: doc notes about where we migrated from.
      2. Legacy-fallback branch: reads $HOME/Desktop/.agent-launcher-*.json
         so users migrating from the desktop era don't lose state.
      3. Workspace bookmark: user-facing "Desktop work" menu entry that
         points at $HOME/Desktop/work as a chooser default.

    Regression guard: no UNCONDITIONAL primary write to ~/Desktop/.
    """
    for name in ("agent-launcher.sh", "agent-launcher-common.sh"):
        path = _LAUNCHERS / name
        for i, line in enumerate(path.read_text().splitlines(), start=1):
            if "Desktop/" not in line:
                continue
            stripped = line.lstrip()
            is_comment = stripped.startswith("#")
            is_legacy_probe = "legacy" in line.lower() or (
                # `-f $VAR/Desktop/.something` is a test, part of a fallback chain
                re.search(r"-f\s+['\"]?\$\w+/Desktop/\.", line) is not None
            )
            is_legacy_assign = (
                # Assignments to preset/state store ONLY after an `elif` test
                ("CUSTOM_PRESET_STORE" in line or "launcher-state" in line)
                and "Desktop/.agent-launcher-" in line
            )
            is_workspace_bookmark = "Desktop work" in line or "Desktop/work" in line
            legal = is_comment or is_legacy_probe or is_legacy_assign or is_workspace_bookmark
            assert legal, (
                f"{name}:{i} has a non-legacy Desktop/ reference: {line!r}"
            )


# ─────────────────────────────────────────────────────────────────────
# Thin wrappers — each must delegate to agent-launcher.sh with correct --tool
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("wrapper,tool", [
    ("claude.sh", "claude"),
    ("codex.sh", "codex"),
    ("gemini.sh", "gemini"),
])
def test_wrapper_delegates_to_main(wrapper, tool):
    path = _LAUNCHERS / wrapper
    text = path.read_text()
    assert "agent-launcher.sh" in text, f"{wrapper}: must delegate to agent-launcher.sh"
    assert f'--tool {tool}' in text, f"{wrapper}: must pass --tool {tool}"
    assert 'exec' in text, f"{wrapper}: must use exec for proper process replacement"


# ─────────────────────────────────────────────────────────────────────
# Dry-run shape — resolved config is printed, no side effects
# ─────────────────────────────────────────────────────────────────────

def _run(
    args: list[str],
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        cwd=cwd,
        timeout=10,
    )


@pytest.mark.parametrize("tool,auth", [
    ("claude", "oauth_token"),
    ("codex", "chatgpt"),
    ("gemini", "oauth"),
])
def test_dry_run_prints_expected_fields(tool, auth):
    result = _run([
        str(_LAUNCHERS / "agent-launcher.sh"),
        "--tool", tool,
        "--auth", auth,
        "--session", "test-session",
        "--dir", str(Path.home()),
        "--dry-run",
    ])
    assert result.returncode == 0, f"dry-run failed: {result.stderr}"
    out = result.stdout
    assert f"tool:     {tool}" in out
    assert "session:  test-session" in out
    assert "dir:" in out


def test_dry_run_via_wrapper():
    """The thin wrappers should produce identical dry-run output."""
    direct = _run([
        str(_LAUNCHERS / "agent-launcher.sh"),
        "--tool", "claude", "--auth", "oauth_token",
        "--session", "dup", "--dir", str(Path.home()), "--dry-run",
    ]).stdout
    via_wrapper = _run([
        str(_LAUNCHERS / "claude.sh"),
        "--auth", "oauth_token",
        "--session", "dup", "--dir", str(Path.home()), "--dry-run",
    ]).stdout
    assert direct == via_wrapper, (
        f"wrapper output diverges from direct:\ndirect:\n{direct}\nwrapper:\n{via_wrapper}"
    )


def test_help_exits_zero():
    result = _run([str(_LAUNCHERS / "agent-launcher.sh"), "--help"])
    assert result.returncode == 0
    assert "--tool" in result.stdout
    assert "--headless" in result.stdout
    assert "--prompt-auth" not in result.stdout


@pytest.mark.parametrize("name", _DETERMINISTIC_LAUNCHER_SOURCES)
def test_deterministic_launcher_sources_have_no_interactive_primitives(name):
    text = (_LAUNCHERS / name).read_text(encoding="utf-8")
    for pattern in _FORBIDDEN_INTERACTIVE_PATTERNS:
        assert pattern not in text, f"{name}: found retired interactive primitive {pattern!r}"


def test_missing_auth_exits_two_with_explicit_error():
    result = _run([
        str(_LAUNCHERS / "agent-launcher.sh"),
        "--tool", "claude",
        "--dry-run",
    ])
    assert result.returncode == 2
    assert "error: --auth is required" in result.stderr


def test_dry_run_defaults_dir_and_session_from_cwd(tmp_path: Path):
    workspace = tmp_path / "Agent Launcher Workspace"
    workspace.mkdir()

    result = _run([
        str(_LAUNCHERS / "agent-launcher.sh"),
        "--tool", "claude",
        "--auth", "oauth_token",
        "--dry-run",
    ], cwd=str(workspace))

    assert result.returncode == 0, result.stderr
    assert f"dir:      {workspace.resolve()}" in result.stdout
    assert "session:  claude-oauth_token-agent-launcher-workspace" in result.stdout


# ─────────────────────────────────────────────────────────────────────
# Fuzzy picker — env override lists take effect
# ─────────────────────────────────────────────────────────────────────

def _load_fuzzy_module(env: dict[str, str] | None = None):
    """Import agent-launcher-fuzzy.py under controlled env."""
    spec = importlib.util.spec_from_file_location(
        "agent_launcher_fuzzy",
        str(_LAUNCHERS / "agent-launcher-fuzzy.py"),
    )
    module = importlib.util.module_from_spec(spec)
    # Apply env just for the exec phase
    saved = {}
    try:
        for k, v in (env or {}).items():
            saved[k] = os.environ.get(k)
            os.environ[k] = v
        spec.loader.exec_module(module)
        return module
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_fuzzy_root_specs_from_env():
    m = _load_fuzzy_module({"CLAWSEAT_LAUNCHER_ROOTS": "/tmp:7,/var:3"})
    roots = m.ROOT_SPECS
    assert (Path("/tmp"), 7) in roots
    assert (Path("/var"), 3) in roots


def test_fuzzy_favorites_from_env():
    m = _load_fuzzy_module({"CLAWSEAT_LAUNCHER_FAVORITES": "/tmp,/var/log"})
    assert m.FAVORITES == ["/tmp", "/var/log"]


def test_fuzzy_defaults_are_home_relative(tmp_path):
    """Without env override, defaults must be under the caller's HOME."""
    m = _load_fuzzy_module({"HOME": str(tmp_path), "REAL_HOME": str(tmp_path)})
    for root, _ in m.ROOT_SPECS:
        assert str(root).startswith(str(tmp_path)), (
            f"fuzzy root {root} is not under HOME {tmp_path}"
        )
    for fav in m.FAVORITES:
        assert fav.startswith(str(tmp_path)), (
            f"fuzzy favorite {fav} is not under HOME {tmp_path}"
        )


def test_fuzzy_script_runs_under_system_python3(tmp_path: Path):
    root = tmp_path / "repos"
    target = root / "alpha-launcher"
    target.mkdir(parents=True)

    result = _run([
        "python3",
        str(_LAUNCHERS / "agent-launcher-fuzzy.py"),
        "--query", "alpha",
        "--limit", "1",
    ], env={
        "HOME": str(tmp_path),
        "REAL_HOME": str(tmp_path),
        "CLAWSEAT_LAUNCHER_ROOTS": f"{root}:2",
        "CLAWSEAT_LAUNCHER_FAVORITES": "",
    })

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(target.resolve())


# ─────────────────────────────────────────────────────────────────────
# Launcher directory self-relative resolution
# ─────────────────────────────────────────────────────────────────────

def test_launcher_dir_is_self_relative():
    """agent-launcher.sh must compute LAUNCHER_DIR from BASH_SOURCE, not HOME."""
    text = (_LAUNCHERS / "agent-launcher.sh").read_text()
    # The canonical incantation for self-relative dir in bash:
    assert 'LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in text, (
        "agent-launcher.sh must use BASH_SOURCE-based LAUNCHER_DIR"
    )


def test_helper_paths_are_self_relative():
    """HELPER and DISCOVER_HELPER must live next to the main launcher."""
    text = (_LAUNCHERS / "agent-launcher.sh").read_text()
    assert 'HELPER="$LAUNCHER_DIR/agent-launcher-common.sh"' in text
    assert 'DISCOVER_HELPER="$LAUNCHER_DIR/agent-launcher-discover.py"' in text


# ─────────────────────────────────────────────────────────────────────
# Headless mode contract — no iTerm/Terminal launch attempt
# ─────────────────────────────────────────────────────────────────────

def test_headless_flag_exists():
    """`--headless` must be documented so install_entrypoint.py can trust it."""
    help_out = _run([str(_LAUNCHERS / "agent-launcher.sh"), "--help"]).stdout
    assert "--headless" in help_out


def test_dry_run_shows_headless_state():
    """Dry-run output must include the headless flag value — the install flow
    parses this field to confirm tmux-only mode before opening its own window."""
    result = _run([
        str(_LAUNCHERS / "agent-launcher.sh"),
        "--tool", "claude", "--auth", "oauth_token",
        "--session", "h", "--dir", str(Path.home()),
        "--headless", "--dry-run",
    ])
    assert result.returncode == 0
    assert "headless: 1" in result.stdout


# ─────────────────────────────────────────────────────────────────────
# README present and accurate
# ─────────────────────────────────────────────────────────────────────

def test_readme_present():
    assert (_LAUNCHERS / "README.md").is_file()


def test_readme_documents_env_vars():
    text = (_LAUNCHERS / "README.md").read_text()
    for env_var in (
        "CLAWSEAT_LAUNCHER_ROOTS",
        "CLAWSEAT_LAUNCHER_FAVORITES",
        "AGENT_LAUNCHER_CUSTOM_PRESET_STORE",
    ):
        assert env_var in text, f"README missing docs for {env_var}"
