"""Tests for init_specialist.py — IDENTITY/SOUL/MEMORY scaffolding for specialist seats.

Covers:
- Positive path: --dry-run exits 0, prints would_write for IDENTITY/SOUL/MEMORY
- Failure: --seat koder (heartbeat_owner) → exit 2
- Failure: unknown seat id → exit 2
- Failure: missing --profile → argparse error
- Failure: nonexistent profile path → exit 2
- Failure: workspace does not exist → exit 1
- Bonus: _resolve_workspace() tilde expansion under CLAWSEAT_REAL_HOME override
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "core" / "skills" / "clawseat-install" / "scripts" / "init_specialist.py"


def _clean_env(extra: dict | None = None) -> dict:
    """Minimal env — no seat-sandbox HOME pollution."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/Users/ywf"),
        "GSTACK_SKILLS_ROOT": os.environ.get(
            "GSTACK_SKILLS_ROOT",
            "/Users/ywf/.gstack/repos/gstack/.agents/skills",
        ),
        "CLAWSEAT_ROOT": str(REPO),
        # Clear any seat-sandbox vars so real_user_home() uses pwd
        "AGENT_HOME": "",
        "CLAWSEAT_SANDBOX_HOME_STRICT": "",
        "CLAWSEAT_REAL_HOME": "",
    }
    if extra:
        env.update(extra)
    return env


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("timeout", 30)
    kwargs["env"] = _clean_env(kwargs.get("env"))
    return subprocess.run(args, **kwargs)


def _make_profile(tmp_path: Path, heartbeat_owner: str = "koder", workspace_root: Path | None = None) -> Path:
    """Write a minimal valid profile TOML for init_specialist testing."""
    ws = workspace_root or (tmp_path / "workspaces" / "install")
    profile = tmp_path / "test-profile.toml"
    profile.write_text(
        f'version = 2\n'
        f'profile_name = "test"\n'
        f'heartbeat_owner = "{heartbeat_owner}"\n'
        f'heartbeat_transport = "tmux"\n'
        f'project_name = "test"\n'
        f'workspace_root = "{ws}"\n'
        f'seats = ["memory", "koder", "planner", "builder-1", "reviewer-1"]\n'
        f'runtime_seats = ["memory", "koder", "planner", "builder-1", "reviewer-1"]\n'
        f'\n[seat_roles]\n'
        f'memory = "memory-oracle"\n'
        f'koder = "frontstage-supervisor"\n'
        f'planner = "planner-dispatcher"\n'
        f'builder-1 = "builder"\n'
        f'reviewer-1 = "reviewer"\n'
        f'\n[seat_overrides.reviewer-1]\n'
        f'tool = "claude"\n'
        f'auth_mode = "api"\n'
        f'provider = "minimax"\n'
        f'role = "reviewer"\n',
        encoding="utf-8",
    )
    return profile


# ─────────────────────────────────────────────────────────────────────────────
# Positive path
# ─────────────────────────────────────────────────────────────────────────────

def test_init_specialist_dry_run_exits_zero(tmp_path):
    """--dry-run with a valid profile + existing workspace exits 0."""
    workspace = tmp_path / "workspaces" / "install" / "reviewer-1"
    workspace.mkdir(parents=True)
    profile = _make_profile(tmp_path, workspace_root=tmp_path / "workspaces" / "install")

    r = _run([
        sys.executable, str(SCRIPT),
        "--profile", str(profile),
        "--seat", "reviewer-1",
        "--dry-run",
    ])

    assert r.returncode == 0, (
        f"init_specialist --dry-run exited {r.returncode}.\n"
        f"stdout:{r.stdout}\nstderr:{r.stderr}"
    )
    # --dry-run prints would_write for each managed file
    for fname in ("IDENTITY.md", "SOUL.md", "MEMORY.md"):
        assert f"would_write:" in r.stdout, (
            f"expected 'would_write' in output for {fname}.\nstdout:{r.stdout}"
        )
    assert "reviewer-1" in r.stdout


def test_init_specialist_would_write_all_three_files(tmp_path):
    """--dry-run reports all three managed files are produced."""
    workspace = tmp_path / "workspaces" / "install" / "reviewer-1"
    workspace.mkdir(parents=True)
    profile = _make_profile(tmp_path, workspace_root=tmp_path / "workspaces" / "install")

    r = _run([
        sys.executable, str(SCRIPT),
        "--profile", str(profile),
        "--seat", "reviewer-1",
        "--dry-run",
    ])

    assert r.returncode == 0
    assert "IDENTITY.md" in r.stdout
    assert "SOUL.md" in r.stdout
    assert "MEMORY.md" in r.stdout


# ─────────────────────────────────────────────────────────────────────────────
# Failure: heartbeat_owner seat rejected
# ─────────────────────────────────────────────────────────────────────────────

def test_init_specialist_heartbeat_owner_rejected(tmp_path):
    """Passing --seat equal to heartbeat_owner exits 2 with clear message."""
    # Profile heartbeat_owner = "koder"; try to init koder as specialist
    workspace = tmp_path / "workspaces" / "install" / "koder"
    workspace.mkdir(parents=True)
    profile = _make_profile(tmp_path, heartbeat_owner="koder", workspace_root=tmp_path / "workspaces" / "install")

    r = _run([
        sys.executable, str(SCRIPT),
        "--profile", str(profile),
        "--seat", "koder",
        "--dry-run",
    ])

    assert r.returncode == 2, (
        f"expected exit 2 for heartbeat_owner seat, got {r.returncode}.\n"
        f"stdout:{r.stdout}\nstderr:{r.stderr}"
    )
    combined = r.stdout + r.stderr
    assert "heartbeat_owner" in combined.lower() or "init_koder" in combined, (
        f"expected heartbeat_owner refusal message.\ncombined:{combined}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Failure: unknown seat id
# ─────────────────────────────────────────────────────────────────────────────

def test_init_specialist_unknown_seat_exits_2(tmp_path):
    """Unknown seat id exits 2 with a RuntimeError from _find_engineer_spec."""
    workspace = tmp_path / "workspaces" / "install" / "nobody"
    workspace.mkdir(parents=True)
    profile = _make_profile(tmp_path, workspace_root=tmp_path / "workspaces" / "install")

    r = _run([
        sys.executable, str(SCRIPT),
        "--profile", str(profile),
        "--seat", "nonexistent-engineer",
        "--dry-run",
    ])

    assert r.returncode == 2, f"expected exit 2, got {r.returncode}"
    combined = r.stdout + r.stderr
    assert "not found" in combined.lower(), (
        f"expected 'not found' in error output.\ncombined:{combined}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Failure: missing --profile
# ─────────────────────────────────────────────────────────────────────────────

def test_init_specialist_missing_profile_argparse_error(tmp_path):
    """Omitting --profile causes argparse to exit with an error."""
    r = _run([
        sys.executable, str(SCRIPT),
        "--seat", "reviewer-1",
    ])

    assert r.returncode != 0, "expected non-zero exit without --profile"
    combined = r.stdout + r.stderr
    assert "profile" in combined.lower() or "required" in combined.lower(), (
        f"expected argparse --profile error.\ncombined:{combined}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Failure: nonexistent profile path
# ─────────────────────────────────────────────────────────────────────────────

def test_init_specialist_nonexistent_profile_exits_nonzero(tmp_path):
    """Profile path that doesn't exist exits non-zero (1 from uncaught FileNotFoundError)."""
    r = _run([
        sys.executable, str(SCRIPT),
        "--profile", str(tmp_path / "does-not-exist.toml"),
        "--seat", "reviewer-1",
        "--dry-run",
    ])

    assert r.returncode != 0, f"expected non-zero exit for missing profile, got {r.returncode}"
    combined = r.stdout + r.stderr
    assert "not found" in combined.lower(), (
        f"expected 'not found' in error output.\ncombined:{combined}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Failure: workspace does not exist
# ─────────────────────────────────────────────────────────────────────────────

def test_init_specialist_workspace_not_exists_exits_1(tmp_path):
    """Workspace directory missing causes exit 1 with clear message."""
    profile = _make_profile(tmp_path, workspace_root=tmp_path / "workspaces" / "install")
    # workspace reviewer-1 does NOT exist

    r = _run([
        sys.executable, str(SCRIPT),
        "--profile", str(profile),
        "--seat", "reviewer-1",
        "--dry-run",
    ])

    # Even --dry-run checks workspace existence before writing
    assert r.returncode == 1, (
        f"expected exit 1 for missing workspace, got {r.returncode}.\n"
        f"stdout:{r.stdout}\nstderr:{r.stderr}"
    )
    combined = r.stdout + r.stderr
    assert "workspace" in combined.lower() or "exist" in combined.lower(), (
        f"expected workspace-not-found message.\ncombined:{combined}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bonus: _resolve_workspace() tilde expansion under CLAWSEAT_REAL_HOME override
# ─────────────────────────────────────────────────────────────────────────────

def test_resolve_workspace_resolves_tilde_via_real_user_home(tmp_path):
    """workspace_root = "~/" expands to the real home, not sandbox HOME.

    This verifies that _resolve_workspace() uses real_user_home() for tilde
    expansion so sandbox seats resolve to the operator's real workspace tree.
    """
    real_home = tmp_path / "real-home"
    real_home.mkdir()

    # Write a profile with workspace_root = "~/workspaces/install"
    profile = tmp_path / "tilde-profile.toml"
    profile.write_text(
        f'version = 2\n'
        f'profile_name = "test"\n'
        f'heartbeat_owner = "koder"\n'
        f'project_name = "test"\n'
        f'workspace_root = "~/workspaces/install"\n'
        f'seats = ["reviewer-1"]\n'
        f'runtime_seats = ["reviewer-1"]\n'
        f'\n[seat_roles]\n'
        f'reviewer-1 = "reviewer"\n',
        encoding="utf-8",
    )

    # Workspace must exist at the resolved path (under real_home, not tmp_path)
    workspace_reviewer = real_home / "workspaces" / "install" / "reviewer-1"
    workspace_reviewer.mkdir(parents=True)

    # Without CLAWSEAT_REAL_HOME: real_user_home() uses pwd → would not expand to real_home
    # With CLAWSEAT_REAL_HOME=real_home: real_user_home() returns real_home
    r = _run([
        sys.executable, str(SCRIPT),
        "--profile", str(profile),
        "--seat", "reviewer-1",
        "--dry-run",
    ], env={**_clean_env(), "CLAWSEAT_REAL_HOME": str(real_home)})

    assert r.returncode == 0, (
        f"expected exit 0 with CLAWSEAT_REAL_HOME override.\n"
        f"stdout:{r.stdout}\nstderr:{r.stderr}"
    )
    # The script resolves workspace to <CLAWSEAT_REAL_HOME>/workspaces/install/reviewer-1
    # which exists (we created it), so dry-run should print would_write lines.
    assert "would_write:" in r.stdout
