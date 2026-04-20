"""Tests for the install_openclaw_bundle.py → install_bundled_skills.py +
install_koder_overlay.py split.

Contract under test
-------------------
- ``install_bundled_skills.py`` creates ``~/.openclaw/skills/<skill>``
  symlinks and never touches any per-agent ``workspace-<name>`` directory.
- ``install_koder_overlay.py`` REQUIRES ``--agent``; omitting it is an
  error (argparse exit 2) and prints the memory-query-protocol hint.
- ``install_koder_overlay.py --agent <NAME>`` creates symlinks under
  ``<openclaw-home>/workspace-<NAME>/skills/`` and nowhere else.
- ``install_koder_overlay.py --agent <NAME>`` refuses (exit 3) when the
  target workspace directory does not exist and lists any ``workspace-*``
  candidates it finds as diagnostic info.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


SHELLS_DIR = Path(__file__).resolve().parents[1] / "shells" / "openclaw-plugin"
if str(SHELLS_DIR) not in sys.path:
    sys.path.insert(0, str(SHELLS_DIR))

import install_bundled_skills  # noqa: E402
import install_koder_overlay  # noqa: E402


# ---------------------------------------------------------------------------
# install_bundled_skills
# ---------------------------------------------------------------------------


def test_install_bundled_skills_creates_global_symlinks_only(tmp_path, monkeypatch):
    openclaw_home = tmp_path / ".openclaw"
    # Pre-create a workspace-koder dir so we can assert it stays untouched.
    (openclaw_home / "workspace-koder").mkdir(parents=True)

    # Skip external skill checks — they're asserted separately.
    monkeypatch.setattr(install_bundled_skills, "check_agent_skills", lambda dry_run: [])
    monkeypatch.setattr(install_bundled_skills, "check_gstack_skills", lambda dry_run: [])

    rc = install_bundled_skills.install_bundled_skills(openclaw_home, dry_run=False)
    assert rc == 0

    skills_root = openclaw_home / "skills"
    assert skills_root.is_dir()
    expected = set(install_bundled_skills.GLOBAL_SKILLS.keys())
    actual = {p.name for p in skills_root.iterdir()}
    assert actual == expected

    # workspace-koder/skills must NOT have been created by the bundled
    # skills installer — that is the overlay installer's job.
    koder_skills = openclaw_home / "workspace-koder" / "skills"
    assert not koder_skills.exists(), (
        "install_bundled_skills.py leaked into workspace-koder; that is "
        "install_koder_overlay.py's responsibility now."
    )


def test_install_bundled_skills_idempotent(tmp_path, monkeypatch):
    openclaw_home = tmp_path / ".openclaw"
    monkeypatch.setattr(install_bundled_skills, "check_agent_skills", lambda dry_run: [])
    monkeypatch.setattr(install_bundled_skills, "check_gstack_skills", lambda dry_run: [])

    assert install_bundled_skills.install_bundled_skills(openclaw_home, dry_run=False) == 0
    # Second invocation should not raise and should report already_installed.
    assert install_bundled_skills.install_bundled_skills(openclaw_home, dry_run=False) == 0


def test_install_bundled_skills_reports_missing_external_skills(tmp_path, monkeypatch, capsys):
    openclaw_home = tmp_path / ".openclaw"
    monkeypatch.setattr(
        install_bundled_skills, "check_agent_skills", lambda dry_run: ["lark-shared"]
    )
    monkeypatch.setattr(
        install_bundled_skills, "check_gstack_skills", lambda dry_run: ["gstack-careful"]
    )

    rc = install_bundled_skills.install_bundled_skills(openclaw_home, dry_run=False)
    # 1 missing agent + 1 missing gstack
    assert rc == 2
    out = capsys.readouterr().out
    assert "lark_skills_required" in out
    assert "gstack_skills_required" in out


# ---------------------------------------------------------------------------
# install_koder_overlay
# ---------------------------------------------------------------------------


def test_install_koder_overlay_requires_agent_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        install_koder_overlay.parse_args([])
    assert excinfo.value.code == 2


def test_install_koder_overlay_main_missing_agent_prints_memory_hint(capsys):
    with pytest.raises(SystemExit) as excinfo:
        install_koder_overlay.main([])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "memory-query-protocol.md" in err
    assert "query_memory.py" in err
    assert "--search agents" in err
    assert "--file openclaw --section agents" not in err


def test_install_koder_overlay_installs_into_chosen_agent_workspace(tmp_path):
    openclaw_home = tmp_path / ".openclaw"
    # Create two agent workspaces to prove the script targets only the one
    # we name, never a hardcoded default.
    (openclaw_home / "workspace-koder").mkdir(parents=True)
    (openclaw_home / "workspace-cartooner").mkdir(parents=True)

    rc = install_koder_overlay.install_overlay(
        openclaw_home, "cartooner", dry_run=False
    )
    assert rc == 0

    cartooner_skills = openclaw_home / "workspace-cartooner" / "skills"
    koder_skills = openclaw_home / "workspace-koder" / "skills"

    assert cartooner_skills.is_dir(), "overlay should create the cartooner skills dir"
    expected = set(install_koder_overlay.WORKSPACE_KODER_SKILLS.keys())
    actual = {p.name for p in cartooner_skills.iterdir()}
    assert actual == expected

    assert not koder_skills.exists(), (
        "overlay must never touch a workspace the user did not name via --agent"
    )


def test_install_koder_overlay_missing_workspace_exits_3_and_lists_candidates(
    tmp_path, capsys
):
    openclaw_home = tmp_path / ".openclaw"
    (openclaw_home / "workspace-cartooner").mkdir(parents=True)
    (openclaw_home / "workspace-mor").mkdir(parents=True)

    rc = install_koder_overlay.install_overlay(
        openclaw_home, "does-not-exist", dry_run=False
    )
    assert rc == 3
    err = capsys.readouterr().err
    assert "agent workspace not found" in err
    assert "cartooner" in err
    assert "mor" in err


def test_install_koder_overlay_missing_workspace_no_candidates(tmp_path, capsys):
    openclaw_home = tmp_path / ".openclaw"
    openclaw_home.mkdir(parents=True)

    rc = install_koder_overlay.install_overlay(
        openclaw_home, "koder", dry_run=False
    )
    assert rc == 3
    err = capsys.readouterr().err
    assert "no workspace-* directories found" in err


def test_install_koder_overlay_idempotent(tmp_path):
    openclaw_home = tmp_path / ".openclaw"
    (openclaw_home / "workspace-koder").mkdir(parents=True)

    assert install_koder_overlay.install_overlay(
        openclaw_home, "koder", dry_run=False
    ) == 0
    assert install_koder_overlay.install_overlay(
        openclaw_home, "koder", dry_run=False
    ) == 0


# ---------------------------------------------------------------------------
# install_openclaw_bundle wrapper
# ---------------------------------------------------------------------------


def test_install_openclaw_bundle_wrapper_delegates_and_warns(tmp_path, monkeypatch, capsys):
    # Re-import fresh so the wrapper's module-level side effects are
    # exercised deterministically.
    import importlib

    monkeypatch.setattr(
        install_bundled_skills, "check_agent_skills", lambda dry_run: []
    )
    monkeypatch.setattr(
        install_bundled_skills, "check_gstack_skills", lambda dry_run: []
    )

    openclaw_home = tmp_path / ".openclaw"
    monkeypatch.setattr(
        sys, "argv", ["install_openclaw_bundle.py", "--openclaw-home", str(openclaw_home)]
    )

    import install_openclaw_bundle

    install_openclaw_bundle = importlib.reload(install_openclaw_bundle)

    rc = install_openclaw_bundle.main()
    assert rc == 0

    captured = capsys.readouterr()
    assert "deprecated" in captured.err.lower()
    # Wrapper must NOT have created a workspace-koder/skills dir — that was
    # the hardcoded behavior the split removed.
    assert not (openclaw_home / "workspace-koder" / "skills").exists()
    # But it must have installed the global skills (via delegation).
    assert (openclaw_home / "skills").is_dir()


def test_install_bundled_skills_main_prints_updated_memory_query_steps(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        install_bundled_skills, "check_agent_skills", lambda dry_run: []
    )
    monkeypatch.setattr(
        install_bundled_skills, "check_gstack_skills", lambda dry_run: []
    )
    monkeypatch.setattr(
        sys, "argv", ["install_bundled_skills.py", "--openclaw-home", str(tmp_path / ".openclaw")]
    )

    rc = install_bundled_skills.main()

    assert rc == 0
    out = capsys.readouterr().out
    assert "scan_environment.py" in out
    assert "--memory-dir" in out
    assert "--search agents" in out
    assert "--file openclaw --section agents" not in out
