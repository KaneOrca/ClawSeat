"""Shared pytest fixtures for ClawSeat test suite."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# ── Path bootstrapping ────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]

_EXTRA_PATHS = [
    str(REPO_ROOT),
    str(REPO_ROOT / "core"),
    str(REPO_ROOT / "core" / "skills" / "gstack-harness" / "scripts"),
    str(REPO_ROOT / "core" / "skills" / "clawseat-install" / "scripts"),
    str(REPO_ROOT / "shells" / "openclaw-plugin"),
]

for _p in _EXTRA_PATHS:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def repo_root() -> Path:
    """Return the ClawSeat repository root."""
    return REPO_ROOT


@pytest.fixture()
def harness_profile(tmp_path: Path) -> Path:
    """Write a minimal but complete harness profile TOML and return its path.

    The profile contains every required field so that ``load_profile()``
    succeeds without hitting validation errors.
    """
    tasks_root = tmp_path / "tasks" / "test-project"
    workspace_root = tmp_path / "workspaces" / "test-project"
    handoff_dir = tasks_root / "patrol" / "handoffs"

    profile_path = tmp_path / "install-profile.toml"
    profile_path.write_text(
        "\n".join(
            [
                'version = 1',
                'profile_name = "test-harness-profile"',
                'template_name = "gstack-harness"',
                'project_name = "test-project"',
                f'repo_root = "{REPO_ROOT}"',
                f'tasks_root = "{tasks_root}"',
                f'project_doc = "{tasks_root / "PROJECT.md"}"',
                f'tasks_doc = "{tasks_root / "TASKS.md"}"',
                f'status_doc = "{tasks_root / "STATUS.md"}"',
                f'send_script = "{REPO_ROOT / "core" / "shell-scripts" / "send-and-verify.sh"}"',
                f'status_script = "{tasks_root / "patrol" / "check-status.sh"}"',
                f'patrol_script = "{tasks_root / "patrol" / "patrol-supervisor.sh"}"',
                f'agent_admin = "{REPO_ROOT / "core" / "scripts" / "agent_admin.py"}"',
                f'workspace_root = "{workspace_root}"',
                f'handoff_dir = "{handoff_dir}"',
                'heartbeat_owner = "koder"',
                'active_loop_owner = "planner"',
                'default_notify_target = "planner"',
                f'heartbeat_receipt = "{workspace_root / "koder" / "HEARTBEAT_RECEIPT.toml"}"',
                'seats = ["koder", "planner", "reviewer-1"]',
                'heartbeat_seats = ["koder"]',
                '',
                '[seat_roles]',
                'koder = "frontstage-supervisor"',
                'planner = "planner-dispatcher"',
                'reviewer-1 = "reviewer"',
                '',
                '[dynamic_roster]',
                'enabled = true',
                f'session_root = "{tmp_path / "sessions"}"',
                'bootstrap_seats = ["koder"]',
                'default_start_seats = ["koder", "planner"]',
                'compat_legacy_seats = false',
                '',
            ]
        ),
        encoding="utf-8",
    )
    return profile_path


@pytest.fixture()
def fake_skill_dir(tmp_path: Path) -> Path:
    """Create a temporary skill directory with a SKILL.md file."""
    skill_dir = tmp_path / "fake-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# Fake Skill\nA placeholder skill for testing.\n",
        encoding="utf-8",
    )
    return skill_dir


@pytest.fixture()
def monkeypatch_clawseat_root(monkeypatch: pytest.MonkeyPatch, repo_root: Path):
    """Set CLAWSEAT_ROOT env var to the real repo root.

    Not autouse -- tests must request this fixture explicitly.
    """
    monkeypatch.setenv("CLAWSEAT_ROOT", str(repo_root))
