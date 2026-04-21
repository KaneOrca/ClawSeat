"""P1 tests: core/scripts/migrate_profile_to_v2.py.

Exercises §6 migration rules + subcommands (plan / apply / apply-all /
rollback). Builder-1's profile_validator is optional: tests run either
with or without it.
"""
from __future__ import annotations

import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "core" / "scripts"))

import migrate_profile_to_v2 as mig  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

V1_INSTALL = """\
version = 1
profile_name = "install-with-memory"
project_name = "install"
template_name = "gstack-harness"
repo_root = "{CLAWSEAT_ROOT}"
tasks_root = "~/.agents/tasks/install"
workspace_root = "~/.agents/workspaces/install"
handoff_dir = "~/.agents/tasks/install/patrol/handoffs"
heartbeat_owner = "koder"
heartbeat_transport = "tmux"
active_loop_owner = "planner"
default_notify_target = "planner"
heartbeat_receipt = "~/.agents/workspaces/install/koder/HEARTBEAT_RECEIPT.toml"
seats = ["memory", "koder", "planner", "builder-1", "builder-2", "reviewer-1"]
heartbeat_seats = ["koder"]

[seat_roles]
memory = "memory-oracle"
koder = "frontstage-supervisor"
planner = "planner-dispatcher"
builder-1 = "builder"
builder-2 = "builder"
reviewer-1 = "reviewer"

[dynamic_roster]
enabled = true
session_root = "~/.agents/sessions"
materialized_seats = ["memory", "koder", "planner", "builder-1", "builder-2", "reviewer-1"]
runtime_seats = ["memory", "koder", "planner", "builder-1", "builder-2", "reviewer-1"]
bootstrap_seats = ["koder"]
default_start_seats = ["memory", "planner"]
compat_legacy_seats = false

[seat_overrides.memory]
tool = "claude"
auth_mode = "api"
provider = "minimax"
model = "MiniMax-M2.7-highspeed"

[seat_overrides.builder-1]
tool = "claude"
auth_mode = "oauth"
provider = "anthropic"
"""


def _write_v1(path: Path, body: str = V1_INSTALL) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _make_tenant_workspace(root: Path, tenant: str, project: str) -> Path:
    ws = root / f"workspace-{tenant}"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "WORKSPACE_CONTRACT.toml").write_text(
        f'project = "{project}"\n', encoding="utf-8",
    )
    return ws


@pytest.fixture()
def tmp_profile(tmp_path) -> Path:
    return _write_v1(tmp_path / "profiles" / "install-profile-dynamic.toml")


@pytest.fixture()
def tmp_workspaces(tmp_path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    _make_tenant_workspace(root, "yu", "install")
    return root


# ---------------------------------------------------------------------------
# migrate_profile (pure function)
# ---------------------------------------------------------------------------

def test_migrate_collapses_builder_1_and_2_to_parallel_2(tmp_workspaces):
    v1 = _parse(V1_INSTALL)
    v2, warnings, errors = mig.migrate_profile(v1, workspaces_root=tmp_workspaces)
    assert errors == []
    assert v2["version"] == 2
    assert "builder" in v2["seats"]
    assert "builder-1" not in v2["seats"] and "builder-2" not in v2["seats"]
    assert v2["seat_overrides"]["builder"]["parallel_instances"] == 2


def test_migrate_strips_heartbeat_and_deprecated_fields(tmp_workspaces):
    v1 = _parse(V1_INSTALL)
    v2, _, _ = mig.migrate_profile(v1, workspaces_root=tmp_workspaces)
    for forbidden in ("heartbeat_owner", "heartbeat_transport", "heartbeat_seats",
                      "heartbeat_receipt", "active_loop_owner",
                      "default_notify_target"):
        assert forbidden not in v2


def test_migrate_inserts_ancestor_and_designer(tmp_workspaces):
    v1 = _parse(V1_INSTALL)
    v2, warnings, _ = mig.migrate_profile(v1, workspaces_root=tmp_workspaces)
    assert "ancestor" in v2["seats"]
    assert "designer" in v2["seats"]
    assert any("designer" in w for w in warnings)


def test_migrate_seats_are_in_canonical_order(tmp_workspaces):
    v1 = _parse(V1_INSTALL)
    v2, _, _ = mig.migrate_profile(v1, workspaces_root=tmp_workspaces)
    assert v2["seats"] == [
        "ancestor", "planner", "builder", "reviewer", "qa", "designer",
    ] or v2["seats"] == [
        # qa is not in v1 install, so omitted unless inserted.
        "ancestor", "planner", "builder", "reviewer", "designer",
    ]
    # Exactly one of the two canonical orderings.


def test_migrate_detects_koder_tenant_from_workspace(tmp_workspaces):
    v1 = _parse(V1_INSTALL)
    v2, _, errors = mig.migrate_profile(v1, workspaces_root=tmp_workspaces)
    assert errors == []
    assert v2["openclaw_frontstage_agent"] == "yu"


def test_migrate_aborts_when_no_tenant_matches(tmp_path):
    v1 = _parse(V1_INSTALL)
    empty_ws = tmp_path / "empty-openclaw"
    empty_ws.mkdir()
    _v2, _w, errors = mig.migrate_profile(v1, workspaces_root=empty_ws)
    assert any("koder" in e and "project='install'" in e for e in errors)
    assert any("agent-admin project koder-bind" in e for e in errors)


def test_migrate_sets_machine_services_memory(tmp_workspaces):
    v1 = _parse(V1_INSTALL)
    v2, _, _ = mig.migrate_profile(v1, workspaces_root=tmp_workspaces)
    assert v2["machine_services"] == ["memory"]


def test_migrate_idempotent_on_v2(tmp_workspaces):
    v2_in = {"version": 2, "seats": ["ancestor", "planner"]}
    v2_out, w, e = mig.migrate_profile(v2_in, workspaces_root=tmp_workspaces)
    assert v2_out == v2_in
    assert w == [] and e == []


def test_migrate_carries_parallel_instances_only_for_allowed_roles(tmp_workspaces):
    v1 = _parse(V1_INSTALL)
    v2, _, _ = mig.migrate_profile(v1, workspaces_root=tmp_workspaces)
    # planner/ancestor/designer must not have parallel_instances.
    for role in ("ancestor", "planner", "designer"):
        assert "parallel_instances" not in v2["seat_overrides"].get(role, {})


def test_migrate_unknown_seat_reports_error(tmp_workspaces):
    body = V1_INSTALL.replace(
        '"memory", "koder", "planner", "builder-1", "builder-2", "reviewer-1"',
        '"memory", "koder", "planner", "mystery-seat"',
    )
    v1 = _parse(body)
    _, _, errors = mig.migrate_profile(v1, workspaces_root=tmp_workspaces)
    assert any("mystery-seat" in e for e in errors)


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

def test_backup_profile_filename_matches_schema(tmp_profile):
    fixed = datetime(2026, 4, 21, 12, 34, 56)
    bk = mig.backup_profile(tmp_profile, now=fixed)
    assert bk.name.endswith(".bak.v1.20260421-123456")
    assert bk.is_file()
    assert bk.read_text() == tmp_profile.read_text()


def test_latest_backup_returns_most_recent(tmp_profile):
    mig.backup_profile(tmp_profile, now=datetime(2026, 1, 1, 0, 0, 0))
    time.sleep(0.01)
    mig.backup_profile(tmp_profile, now=datetime(2026, 4, 21, 12, 0, 0))
    bk = mig.latest_backup(tmp_profile)
    assert bk is not None
    assert "20260421-120000" in bk.name


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------

def test_plan_is_dry_run(tmp_profile, tmp_workspaces, capsys):
    rc = mig.main([
        "plan",
        "--profile", str(tmp_profile),
        "--workspaces-root", str(tmp_workspaces),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "plan migrate v1 -> v2" in captured.out
    assert "openclaw_frontstage_agent" in captured.out
    assert "parallel_instances" in captured.out
    # File unchanged.
    raw = tmp_profile.read_text()
    assert 'version = 1' in raw


def test_plan_returns_1_when_tenant_missing(tmp_profile, tmp_path, capsys):
    empty = tmp_path / "empty-openclaw"
    empty.mkdir()
    rc = mig.main([
        "plan",
        "--profile", str(tmp_profile),
        "--workspaces-root", str(empty),
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "koder" in err


def test_apply_creates_backup_and_writes_v2(tmp_profile, tmp_workspaces, capsys):
    rc = mig.main([
        "apply",
        "--profile", str(tmp_profile),
        "--workspaces-root", str(tmp_workspaces),
        "--skip-validate",  # isolate from builder-1's validator in tests
    ])
    assert rc == 0
    # Backup present.
    bks = list(tmp_profile.parent.glob(tmp_profile.name + ".bak.v1.*"))
    assert len(bks) == 1
    # New file is v2.
    after = tmp_profile.read_text()
    assert "version = 2" in after
    assert 'heartbeat_owner' not in after
    assert 'openclaw_frontstage_agent = "yu"' in after


def test_apply_on_v2_is_noop(tmp_path, capsys):
    p = tmp_path / "already-v2.toml"
    p.write_text(
        'version = 2\n'
        'project_name = "x"\n'
        'seats = ["ancestor", "planner"]\n',
        encoding="utf-8",
    )
    before = p.read_text()
    rc = mig.main(["apply", "--profile", str(p), "--skip-validate"])
    assert rc == 0
    assert "already v2" in capsys.readouterr().out
    # Untouched.
    assert p.read_text() == before
    assert list(p.parent.glob(p.name + ".bak.v1.*")) == []


def test_apply_aborts_without_tenant(tmp_profile, tmp_path, capsys):
    empty = tmp_path / "empty-openclaw"
    empty.mkdir()
    rc = mig.main([
        "apply",
        "--profile", str(tmp_profile),
        "--workspaces-root", str(empty),
        "--skip-validate",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "koder" in err
    # File unchanged.
    assert 'version = 1' in tmp_profile.read_text()


def test_rollback_restores_last_backup(tmp_profile, tmp_workspaces):
    # Apply, then edit, then rollback.
    rc = mig.main([
        "apply",
        "--profile", str(tmp_profile),
        "--workspaces-root", str(tmp_workspaces),
        "--skip-validate",
    ])
    assert rc == 0
    v2_body = tmp_profile.read_text()
    assert "version = 2" in v2_body

    rc = mig.main(["rollback", "--profile", str(tmp_profile)])
    assert rc == 0
    restored = tmp_profile.read_text()
    assert "version = 1" in restored
    # (Backup file for the v1 we just clobbered should still exist.)


def test_rollback_reports_error_when_no_backup(tmp_profile, capsys):
    rc = mig.main(["rollback", "--profile", str(tmp_profile)])
    assert rc == 1
    assert "no backup" in capsys.readouterr().err


def test_apply_all_iterates_profiles_dir(tmp_path, tmp_workspaces, capsys):
    pdir = tmp_path / "profiles"
    pdir.mkdir()
    _write_v1(pdir / "a.toml", V1_INSTALL)
    # second profile with different project name that has no tenant match
    body2 = V1_INSTALL.replace('project_name = "install"',
                               'project_name = "orphan"')
    _write_v1(pdir / "b.toml", body2)

    rc = mig.main([
        "apply-all",
        "--profiles-dir", str(pdir),
        "--workspaces-root", str(tmp_workspaces),
        "--skip-validate",
    ])
    # rc is the worst of each profile; the orphan migration fails with rc=1.
    assert rc == 1
    out = capsys.readouterr().out
    assert "a.toml" in out and "b.toml" in out
    # a.toml migrated.
    assert 'version = 2' in (pdir / "a.toml").read_text()
    # b.toml untouched.
    assert 'version = 1' in (pdir / "b.toml").read_text()


# ---------------------------------------------------------------------------
# TOML writer
# ---------------------------------------------------------------------------

def test_dump_toml_round_trips_v2_shape():
    import tomllib
    src = {
        "version": 2,
        "project_name": "install",
        "seats": ["ancestor", "planner", "builder"],
        "dynamic_roster": {"enabled": True, "bootstrap_seats": ["ancestor"]},
        "seat_overrides": {
            "builder": {"tool": "claude", "parallel_instances": 2},
        },
    }
    raw = mig.dump_toml(src)
    reparsed = tomllib.loads(raw)
    assert reparsed["version"] == 2
    assert reparsed["seats"] == src["seats"]
    assert reparsed["seat_overrides"]["builder"]["parallel_instances"] == 2
    assert reparsed["dynamic_roster"]["enabled"] is True


def test_dump_toml_handles_escaped_strings():
    raw = mig.dump_toml({"repo_root": "{CLAWSEAT_ROOT}/x"})
    assert r'"{CLAWSEAT_ROOT}/x"' in raw


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse(body: str) -> dict:
    import tomllib
    return tomllib.loads(body)
