"""Smoke tests for core/tui/install_entrypoint.py.

The entrypoint is a thin orchestrator that chains:
    install_wizard → verify PROJECT_BINDING → seat-auth preflight
    → ancestor_brief → agent-launcher.sh

These tests isolate each stage. Subprocess calls to install_wizard,
ancestor_brief, and agent-launcher.sh are mocked; real filesystem is
scoped to tmp_path so the operator's ~/.agents is untouched.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO = Path(__file__).resolve().parents[1]
# Don't pollute global sys.path with bare-name modules from core/tui or
# core/lib (install_wizard, real_home, etc. have top-level names that
# collide with other tests' monkeypatches). Instead, import via the
# canonical package path. core/ already has __init__.py so this works
# when pytest's rootdir is the repo.
from core.tui import install_entrypoint as ie  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".agents" / "profiles").mkdir(parents=True)
    (home / ".agents" / "tasks").mkdir(parents=True)
    (home / ".agents" / "engineers").mkdir(parents=True)
    clawseat = home / ".clawseat"
    (clawseat / "core" / "launchers").mkdir(parents=True)
    (clawseat / "core" / "scripts").mkdir(parents=True)
    (clawseat / "core" / "templates").mkdir(parents=True)
    (clawseat / "core" / "tui").mkdir(parents=True)
    (clawseat / "core" / "skills" / "clawseat-install" / "scripts").mkdir(parents=True)
    launcher = clawseat / "core" / "launchers" / "agent-launcher.sh"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    iterm_driver = clawseat / "core" / "scripts" / "iterm_panes_driver.py"
    iterm_driver.write_text("#!/usr/bin/env python3\nprint('{\"status\":\"ok\"}')\n")
    iterm_driver.chmod(0o755)
    entry_skills = clawseat / "core" / "skills" / "clawseat-install" / "scripts" / "install_entry_skills.py"
    entry_skills.write_text("#!/usr/bin/env python3\nprint('ok')\n")
    entry_skills.chmod(0o755)
    ancestor_template = clawseat / "core" / "templates" / "ancestor-engineer.toml"
    ancestor_template.write_text(
        'skills = ["{CLAWSEAT_ROOT}/core/skills/clawseat-ancestor/SKILL.md"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAWSEAT_ROOT", str(clawseat))
    # Point module globals at the fake layout.
    monkeypatch.setattr(ie, "CLAWSEAT_ROOT", clawseat)
    monkeypatch.setattr(ie, "LAUNCHER", launcher)
    monkeypatch.setattr(ie, "ITERM_DRIVER", iterm_driver)
    monkeypatch.setattr(ie, "INSTALL_ENTRY_SKILLS", entry_skills)
    monkeypatch.setattr(ie, "ANCESTOR_ENGINEER_TEMPLATE", ancestor_template)
    monkeypatch.setattr(ie, "PROFILE_DIR", home / ".agents" / "profiles")
    monkeypatch.setattr(ie, "TASKS_DIR", home / ".agents" / "tasks")
    monkeypatch.setattr(ie, "ENGINEERS_DIR", home / ".agents" / "engineers")
    return home


def _write_v2_profile(home: Path, project: str, overrides: dict | None = None) -> Path:
    ov = overrides or {
        "ancestor": {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
        "planner":  {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
        "builder":  {"tool": "claude", "auth_mode": "api", "provider": "minimax", "parallel_instances": 1},
    }
    lines = [
        "version = 2",
        f'project_name = "{project}"',
        'openclaw_frontstage_agent = "yu"',
        'seats = ["ancestor", "planner", "builder"]',
    ]
    for role, cfg in ov.items():
        lines.append(f"[seat_overrides.{role}]")
        for k, v in cfg.items():
            if isinstance(v, int):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
    path = home / ".agents" / "profiles" / f"{project}-profile-dynamic.toml"
    path.write_text("\n".join(lines) + "\n")
    return path


def _write_binding(home: Path, project: str, chat_id: str) -> Path:
    d = home / ".agents" / "tasks" / project
    d.mkdir(parents=True, exist_ok=True)
    path = d / "PROJECT_BINDING.toml"
    path.write_text(
        "version = 1\n"
        f'project = "{project}"\n'
        f'feishu_group_id = "{chat_id}"\n'
    )
    return path


# ── Auth mapping table ────────────────────────────────────────────────

class TestAuthMapping:
    """The v0.4 profile uses clawseat semantics (auth_mode + provider),
    the launcher accepts shorter labels. The mapping must be total for
    the canonical §4 install profile."""

    def test_canonical_install_seats_all_map(self):
        assert ie._clawseat_auth_to_launcher("claude", "oauth_token", "anthropic") == "oauth_token"
        assert ie._clawseat_auth_to_launcher("claude", "api", "anthropic-console") == "anthropic-console"
        assert ie._clawseat_auth_to_launcher("claude", "api", "minimax") == "minimax"
        assert ie._clawseat_auth_to_launcher("codex", "api", "xcode-best") == "xcode"
        assert ie._clawseat_auth_to_launcher("gemini", "oauth", "google") == "oauth"

    def test_unknown_combo_returns_none(self):
        assert ie._clawseat_auth_to_launcher("claude", "telepathy", "anthropic") is None
        assert ie._clawseat_auth_to_launcher("bizarre-tool", "api", "x") is None

    def test_legacy_keychain_claude_oauth_maps(self):
        assert ie._clawseat_auth_to_launcher("claude", "oauth", "anthropic") == "oauth"

    def test_custom_always_maps(self):
        assert ie._clawseat_auth_to_launcher("claude", "api", "custom") == "custom"
        assert ie._clawseat_auth_to_launcher("codex", "api", "custom") == "custom"
        assert ie._clawseat_auth_to_launcher("gemini", "api", "custom") == "custom"


# ── Profile resolution ────────────────────────────────────────────────

class TestProfileResolution:

    def test_missing_profile_returns_none(self, fake_home):
        assert ie.load_profile_if_v2("ghost") is None

    def test_v1_profile_returns_none(self, fake_home):
        (fake_home / ".agents" / "profiles" / "legacy-profile-dynamic.toml").write_text(
            "version = 1\nproject_name = \"legacy\"\n"
        )
        assert ie.load_profile_if_v2("legacy") is None

    def test_v2_profile_parses(self, fake_home):
        _write_v2_profile(fake_home, "demo")
        raw = ie.load_profile_if_v2("demo")
        assert raw is not None
        assert raw["version"] == 2
        assert raw["project_name"] == "demo"
        assert "ancestor" in raw["seats"]

    def test_malformed_profile_returns_none(self, fake_home):
        (fake_home / ".agents" / "profiles" / "bad-profile-dynamic.toml").write_text(
            "version = \"not a number\"\ngibberish {{"
        )
        assert ie.load_profile_if_v2("bad") is None


# ── Binding verification ──────────────────────────────────────────────

class TestBindingVerify:

    def test_happy_path_returns_chat_id(self, fake_home, capsys):
        _write_binding(fake_home, "demo", "oc_abc123")
        got = ie.verify_binding("demo")
        assert got == "oc_abc123"

    def test_missing_file_raises(self, fake_home):
        with pytest.raises(SystemExit) as exc_info:
            ie.verify_binding("ghost")
        assert "PROJECT_BINDING.toml missing" in str(exc_info.value)

    def test_empty_group_id_raises(self, fake_home):
        _write_binding(fake_home, "demo", "")
        with pytest.raises(SystemExit) as exc_info:
            ie.verify_binding("demo")
        assert "feishu_group_id is empty" in str(exc_info.value)


# ── check_seat_secret (subprocess boundary) ───────────────────────────

class TestCheckSeatSecret:
    """agent-launcher.sh --check-secrets emits one JSON line. This
    boundary test mocks the subprocess and verifies parsing."""

    def _mock_run(self, monkeypatch, *, stdout: str = "", stderr: str = "", rc: int = 0):
        result = subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)

    def test_ok_status(self, monkeypatch):
        self._mock_run(monkeypatch, stdout='{"status":"ok","file":"/x/y.env","key":"KEY"}\n')
        ok, msg = ie.check_seat_secret("claude", "oauth_token")
        assert ok is True
        assert "/x/y.env" in msg

    def test_missing_file(self, monkeypatch):
        self._mock_run(monkeypatch, stdout='{"status":"missing-file","file":"/a/b.env","key":"K","hint":"create it"}\n', rc=1)
        ok, msg = ie.check_seat_secret("claude", "minimax")
        assert ok is False
        assert "create it" in msg

    def test_missing_key(self, monkeypatch):
        self._mock_run(monkeypatch, stdout='{"status":"missing-key","hint":"add K=..."}\n', rc=1)
        ok, msg = ie.check_seat_secret("claude", "oauth_token")
        assert ok is False
        assert "add K=..." in msg

    def test_error_from_stderr(self, monkeypatch):
        self._mock_run(monkeypatch, stderr='{"status":"error","reason":"unknown auth"}\n', rc=2)
        ok, msg = ie.check_seat_secret("claude", "nope")
        assert ok is False
        assert "unknown auth" in msg

    def test_unparseable_output(self, monkeypatch):
        self._mock_run(monkeypatch, stdout="not json at all", rc=1)
        ok, msg = ie.check_seat_secret("claude", "oauth_token")
        assert ok is False
        assert "unparseable" in msg


# ── preflight_seats (end-to-end, mocked subprocess) ───────────────────

class TestPreflightSeats:

    def test_all_ok_when_launcher_says_ok(self, fake_home, monkeypatch):
        path = _write_v2_profile(fake_home, "demo")
        profile = ie.load_profile_if_v2("demo")
        monkeypatch.setattr(
            ie, "check_seat_secret",
            lambda tool, auth: (True, f"{tool}/{auth} ok"),
        )
        results = ie.preflight_seats(profile)
        assert len(results) == 3
        assert all(ok for _, _, ok in results)

    def test_unknown_auth_mapping_reported_as_not_ok(self, fake_home, monkeypatch):
        _write_v2_profile(fake_home, "demo", overrides={
            "ancestor": {"tool": "claude", "auth_mode": "mystery", "provider": "anthropic"},
            "planner":  {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
        })
        profile = ie.load_profile_if_v2("demo")
        # Force the seats list to match override keys
        profile["seats"] = ["ancestor", "planner"]
        monkeypatch.setattr(
            ie, "check_seat_secret",
            lambda tool, auth: (True, "launcher ok"),
        )
        results = ie.preflight_seats(profile)
        by_seat = {seat: (msg, ok) for seat, msg, ok in results}
        assert by_seat["ancestor"][1] is False
        assert "no launcher mapping" in by_seat["ancestor"][0]
        assert by_seat["planner"][1] is True


# ── End-to-end: ensure_profile happy path skips wizard ────────────────

class TestEnsureProfile:

    def test_existing_v2_profile_is_reused(self, fake_home, monkeypatch, capsys):
        _write_v2_profile(fake_home, "demo")

        def fake_wizard(**kwargs):
            raise AssertionError("run_wizard must not be called when v2 exists")
        monkeypatch.setattr(ie, "run_wizard", fake_wizard)

        profile = ie.ensure_profile("demo", clone_from=None)
        assert profile["version"] == 2

    def test_missing_profile_invokes_wizard(self, fake_home, monkeypatch):
        calls = []

        def fake_wizard(*, project, clone_from):
            calls.append((project, clone_from))
            _write_v2_profile(fake_home, project)
        monkeypatch.setattr(ie, "run_wizard", fake_wizard)

        profile = ie.ensure_profile("newproj", clone_from=None)
        assert profile["version"] == 2
        assert calls == [("newproj", None)]

    def test_clone_from_on_existing_project_raises(self, fake_home, monkeypatch):
        _write_v2_profile(fake_home, "demo")
        monkeypatch.setattr(ie, "run_wizard", lambda **kw: None)
        with pytest.raises(SystemExit) as exc_info:
            ie.ensure_profile("demo", clone_from="cartooner")
        assert "already exists" in str(exc_info.value)


class TestEntrySkills:

    def test_install_entry_skills_script_includes_ancestor_skill(self):
        script = _REPO / "core" / "skills" / "clawseat-install" / "scripts" / "install_entry_skills.py"
        assert '"clawseat-ancestor"' in script.read_text(encoding="utf-8")

    def test_ensure_entry_skills_runs_installer(self, fake_home, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="installed\n", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        ie.ensure_entry_skills()
        assert calls == [[sys.executable, str(ie.INSTALL_ENTRY_SKILLS)]]


class TestAncestorEngineer:

    def test_ensure_ancestor_engineer_renders_template(self, fake_home):
        target = ie.ensure_ancestor_engineer(dry_run=False)
        assert target == fake_home / ".agents" / "engineers" / "ancestor" / "engineer.toml"
        rendered = target.read_text(encoding="utf-8")
        assert "{CLAWSEAT_ROOT}" not in rendered
        assert str(ie.CLAWSEAT_ROOT / "core" / "skills" / "clawseat-ancestor" / "SKILL.md") in rendered

    def test_ensure_ancestor_engineer_is_idempotent(self, fake_home):
        target = ie.ensure_ancestor_engineer(dry_run=False)
        first = target.read_text(encoding="utf-8")
        target.write_text(first, encoding="utf-8")
        second_target = ie.ensure_ancestor_engineer(dry_run=False)
        assert second_target == target
        assert second_target.read_text(encoding="utf-8") == first


class TestAncestorLaunchFlow:

    def test_launch_ancestor_sets_brief_env_and_returns_created(self, fake_home, monkeypatch):
        _write_v2_profile(fake_home, "demo")
        profile = ie.load_profile_if_v2("demo")
        brief = fake_home / ".agents" / "tasks" / "demo" / "patrol" / "handoffs" / "ancestor-bootstrap.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("brief", encoding="utf-8")

        monkeypatch.setattr(ie, "tmux_has_session", lambda _: False)
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["env"] = kwargs["env"]
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        session, created = ie.launch_ancestor(
            "demo",
            profile,
            workdir=ie.CLAWSEAT_ROOT,
            brief=brief,
            dry_run=False,
        )
        assert session == "demo-ancestor-claude"
        assert created is True
        assert seen["cmd"][:6] == [
            str(ie.LAUNCHER), "--tool", "claude", "--auth", "oauth_token", "--session",
        ]
        assert seen["env"]["CLAWSEAT_ANCESTOR_BRIEF"] == str(brief)
        assert seen["env"]["CLAWSEAT_PROJECT"] == "demo"

    def test_open_ancestor_window_sends_single_attach_payload(self, fake_home, monkeypatch):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["input"] = kwargs["input"]
            return subprocess.CompletedProcess(cmd, 0, stdout='{"status":"ok","window_id":"w0"}\n', stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        ie.open_ancestor_window("install", "install-ancestor-claude", dry_run=False)
        payload = json.loads(seen["input"])
        assert seen["cmd"] == [sys.executable, str(ie.ITERM_DRIVER)]
        assert payload["title"] == "install · ancestor"
        assert payload["panes"] == [
            {
                "label": "ancestor",
                "command": "tmux attach -t '=install-ancestor-claude'",
            }
        ]

    def test_prime_ancestor_submits_bootstrap_prompt(self, fake_home, monkeypatch):
        calls = []
        brief = fake_home / ".agents" / "tasks" / "install" / "patrol" / "handoffs" / "ancestor-bootstrap.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("brief", encoding="utf-8")

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        ie.prime_ancestor("install-ancestor-claude", brief, dry_run=False)
        assert calls[0][:4] == ["tmux", "send-keys", "-l", "-t"]
        assert calls[0][4] == "install-ancestor-claude"
        assert str(brief) in calls[0][5]
        assert "clawseat-ancestor/SKILL.md" in calls[0][5]
        assert calls[1] == ["tmux", "send-keys", "-t", "install-ancestor-claude", "Enter"]


class TestMainFlow:

    def test_main_renders_ancestor_engineer_before_launch(self, fake_home, monkeypatch):
        _write_v2_profile(fake_home, "install")
        _write_binding(fake_home, "install", "oc_demo")
        profile = ie.load_profile_if_v2("install")
        brief = fake_home / ".agents" / "tasks" / "install" / "patrol" / "handoffs" / "ancestor-bootstrap.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("brief", encoding="utf-8")
        calls = []

        monkeypatch.setattr(ie.shutil, "which", lambda _: "/usr/bin/tmux")
        monkeypatch.setattr(ie, "ensure_profile", lambda project, clone_from=None: profile)
        monkeypatch.setattr(ie, "verify_binding", lambda project: "oc_demo")
        monkeypatch.setattr(ie, "ensure_entry_skills", lambda: calls.append("skills"))
        monkeypatch.setattr(
            ie,
            "ensure_ancestor_engineer",
            lambda *, dry_run: calls.append(("engineer", dry_run)) or (fake_home / ".agents" / "engineers" / "ancestor" / "engineer.toml"),
        )
        monkeypatch.setattr(ie, "preflight_seats", lambda profile: [])
        monkeypatch.setattr(ie, "render_brief", lambda project: brief)
        monkeypatch.setattr(
            ie,
            "launch_ancestor",
            lambda project, profile, **kwargs: calls.append(("launch", kwargs["brief"])) or ("install-ancestor-claude", True),
        )
        monkeypatch.setattr(
            ie,
            "open_ancestor_window",
            lambda project, session, *, dry_run: calls.append(("window", session, dry_run)),
        )
        monkeypatch.setattr(
            ie,
            "prime_ancestor",
            lambda session, brief_path, *, dry_run: calls.append(("prime", session, dry_run)),
        )

        rc = ie.main(["--project", "install"])

        assert rc == 0
        assert calls == [
            "skills",
            ("engineer", False),
            ("launch", brief),
            ("window", "install-ancestor-claude", False),
            ("prime", "install-ancestor-claude", False),
        ]
