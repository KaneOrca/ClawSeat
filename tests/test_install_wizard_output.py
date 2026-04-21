"""Snapshot the install wizard's canonical output against §4 of the v0.4 spec.

If this test fails, either:
  (a) the spec changed — update SAMPLE_PROFILE_V2 in test_tui_validator_seam.py
      AND this snapshot together, or
  (b) the wizard drifted from the spec — fix the wizard.

Either way, the two must stay locked.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from core.tui import install_wizard


def _canonical_install_state() -> install_wizard.WizardState:
    state = install_wizard.WizardState(
        project_name="install",
        repo_root="{CLAWSEAT_ROOT}",
        openclaw_frontstage_agent="yu",
        machine_services=["memory"],
        seats=[
            install_wizard.SeatChoice(
                name=name,
                tool=install_wizard.RECOMMENDED_OVERRIDES[name]["tool"],
                auth_mode=install_wizard.RECOMMENDED_OVERRIDES[name]["auth_mode"],
                provider=install_wizard.RECOMMENDED_OVERRIDES[name]["provider"],
                parallel_instances=1 if name in install_wizard.PARALLEL_OK else 1,
            )
            for name in install_wizard.LEGAL_SEAT_ROLES
        ],
    )
    return state


def test_build_payload_matches_spec_structure():
    """Each key in the canonical §4 example must be present in our payload."""
    state = _canonical_install_state()
    payload = install_wizard.build_payload(state)

    required_top_level = {
        "version", "profile_name", "template_name", "project_name",
        "repo_root", "tasks_root", "project_doc", "tasks_doc", "status_doc",
        "send_script", "agent_admin", "workspace_root", "handoff_dir",
        "machine_services", "openclaw_frontstage_agent",
        "seats", "seat_roles", "seat_overrides",
        "dynamic_roster", "patrol", "observability",
    }
    missing = required_top_level - set(payload.keys())
    assert not missing, f"§4 keys missing from payload: {missing}"


def test_payload_version_is_2():
    state = _canonical_install_state()
    payload = install_wizard.build_payload(state)
    assert payload["version"] == 2, "v2 schema required"


def test_payload_seats_are_six_canonical_roles():
    state = _canonical_install_state()
    payload = install_wizard.build_payload(state)
    assert payload["seats"] == [
        "ancestor", "planner", "builder", "reviewer", "qa", "designer",
    ]


def test_payload_no_forbidden_heartbeat_fields():
    """§4 'EXPLICITLY REMOVED' — these fields must never appear."""
    state = _canonical_install_state()
    payload = install_wizard.build_payload(state)
    forbidden = {
        "heartbeat_owner", "heartbeat_seats", "heartbeat_transport",
        "heartbeat_receipt", "feishu_group_id",
    }
    found = forbidden & set(payload.keys())
    assert not found, f"wizard emitted forbidden v1 fields: {found}"
    # Also forbidden: memory/koder/builder-N in any seat reference.
    seats = payload.get("seats", [])
    for bad in ("memory", "koder", "builder-1", "reviewer-2", "qa-3"):
        assert bad not in seats, f"wizard put forbidden seat name {bad!r} in seats[]"


def test_parallel_instances_only_where_legal():
    """§7 rule 10 — parallel_instances only for builder/reviewer/qa."""
    state = _canonical_install_state()
    payload = install_wizard.build_payload(state)
    for seat, overrides in payload["seat_overrides"].items():
        has_parallel = "parallel_instances" in overrides
        should_have = seat in install_wizard.PARALLEL_OK
        assert has_parallel == should_have, (
            f"{seat}: parallel_instances legality mismatch "
            f"(has={has_parallel}, should={should_have})"
        )


def test_rendered_toml_is_parseable(tmp_path):
    """Render to TOML and re-parse — must round-trip."""
    try:
        import tomllib  # py3.11+
    except ImportError:
        import tomli as tomllib  # type: ignore
    state = _canonical_install_state()
    payload = install_wizard.build_payload(state)
    rendered = install_wizard._render_v2_toml(payload)
    parsed = tomllib.loads(rendered)
    assert parsed["version"] == 2
    assert parsed["project_name"] == "install"
    assert parsed["openclaw_frontstage_agent"] == "yu"
    assert parsed["seats"] == payload["seats"]
    # Spot-check seat_overrides round-tripped
    assert parsed["seat_overrides"]["reviewer"]["tool"] == "codex"
    assert parsed["seat_overrides"]["builder"]["parallel_instances"] == 1


def test_launcher_auth_table_covers_canonical_overrides():
    """Every (tool, auth_mode, provider) in RECOMMENDED_OVERRIDES must be
    reachable through at least one launcher auth value — otherwise the
    'launcher-dialog' option in screen_seats produces a result the
    canonical default disagrees with."""
    canonical = {
        (v["tool"], v["auth_mode"], v["provider"])
        for v in install_wizard.RECOMMENDED_OVERRIDES.values()
    }
    table_outputs = {
        (tool, auth, prov)
        for (tool, _), (auth, prov) in install_wizard.LAUNCHER_AUTH_TO_CLAWSEAT.items()
    }
    missing = canonical - table_outputs
    assert not missing, (
        f"these canonical (tool, auth_mode, provider) tuples have no path "
        f"through LAUNCHER_AUTH_TO_CLAWSEAT: {missing}"
    )


def test_launcher_auth_translation_known_values():
    f = install_wizard.launcher_auth_to_clawseat
    # Claude
    assert f("claude", "oauth_token") == ("oauth_token", "anthropic")
    assert f("claude", "minimax") == ("api", "minimax")
    assert f("claude", "anthropic-console") == ("api", "anthropic-console")
    # Codex
    assert f("codex", "chatgpt") == ("oauth", "chatgpt")
    assert f("codex", "xcode") == ("api", "xcode-best")
    # Gemini
    assert f("gemini", "oauth") == ("oauth", "google")
    assert f("gemini", "primary") == ("api", "google-primary")


def test_launcher_auth_translation_unknown_falls_back():
    """Unknown (tool, auth) returns (auth, auth) so wizard never crashes
    on a future launcher menu addition."""
    out = install_wizard.launcher_auth_to_clawseat("claude", "future-auth-mode")
    assert out == ("future-auth-mode", "future-auth-mode")


def test_launcher_prompt_auth_returns_none_on_failure(monkeypatch):
    """If launcher script missing, returns None and wizard falls through."""
    import subprocess as _sp
    monkeypatch.setattr(install_wizard, "_launcher_path",
                        lambda: Path("/no/such/launcher"))
    assert install_wizard.launcher_prompt_auth("claude") is None


def test_launcher_prompt_auth_returns_none_on_nonzero_rc(monkeypatch):
    """User cancelled (rc=1) → None (wizard falls back to default)."""
    from types import SimpleNamespace
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="cancel")
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(install_wizard, "_launcher_path",
                        lambda: Path("/usr/bin/true"))  # exists, but we mock run anyway
    assert install_wizard.launcher_prompt_auth("claude") is None


def test_launcher_prompt_auth_returns_picked_value(monkeypatch):
    from types import SimpleNamespace
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout="minimax\n", stderr="")
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(install_wizard, "_launcher_path",
                        lambda: Path("/usr/bin/true"))
    assert install_wizard.launcher_prompt_auth("claude") == "minimax"


def test_rendered_toml_matches_spec_fragments():
    """Key exact strings from the §4 example must appear in the wizard output.

    Not a full-file diff (the spec example has marginal whitespace variations)
    — just the lines that would indicate structural drift.
    """
    state = _canonical_install_state()
    payload = install_wizard.build_payload(state)
    rendered = install_wizard._render_v2_toml(payload)
    must_contain = [
        'version = 2',
        'profile_name = "install"',
        'project_name = "install"',
        'machine_services = ["memory"]',
        'openclaw_frontstage_agent = "yu"',
        'seats = ["ancestor", "planner", "builder", "reviewer", "qa", "designer"]',
        '[seat_overrides.reviewer]',
        'tool = "codex"',
        '[seat_overrides.designer]',
        'tool = "gemini"',
        '[dynamic_roster]',
        'bootstrap_seats = ["ancestor"]',
    ]
    for fragment in must_contain:
        assert fragment in rendered, (
            f"rendered TOML missing expected fragment: {fragment!r}"
        )
