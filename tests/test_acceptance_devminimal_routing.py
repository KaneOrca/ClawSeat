"""CF042: Focused tests for acceptance reviewer routing in dev-minimal teams.

Verifies that _resolve_reviewer_seat_from_profile and route_reviewer:
- Route to planner fallback for dev-minimal (no dedicated reviewer seat) teams.
- Route to the declared reviewer seat for dedicated-reviewer teams.
- Fall back to {team}-reviewer when the profile is unavailable.
- Do not silently skip reviewer acceptance; PENDING is correct when items exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "core" / "lib"))

from acceptance_executor import (  # noqa: E402
    _resolve_reviewer_seat_from_profile,
    route_reviewer,
    run_acceptance,
)


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def _write_devminimal_profile(home: Path, project: str, team: str) -> Path:
    """Write a dev-minimal profile (planner + builder only, no reviewer seat).

    Includes the mandatory 'memory' seat required by load_profile_v3 validation.
    """
    profiles = home / ".agents" / "profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    planner_seat = f"{team}-planner"
    builder_seat = f"{team}-builder-core"
    profile = profiles / f"{project}-profile-dynamic.toml"
    profile.write_text(
        f'profile_name = "{project}-profile-dynamic"\n'
        f'project_name = "{project}"\n'
        f'seats = ["memory", "{planner_seat}", "{builder_seat}"]\n'
        f"\n[mode]\nteam_structure = \"multi\"\n"
        f"\n[teams]\n"
        f'{team} = {{ seats = ["{planner_seat}", "{builder_seat}"] }}\n'
        f"\n[seat_roles]\n"
        f'"memory" = "memory"\n'
        f'"{planner_seat}" = "planner"\n'
        f'"{builder_seat}" = "builder"\n',
        encoding="utf-8",
    )
    return profile


def _write_dedicated_reviewer_profile(home: Path, project: str, team: str) -> Path:
    """Write a profile with a dedicated reviewer seat declared.

    Includes the mandatory 'memory' seat required by load_profile_v3 validation.
    """
    profiles = home / ".agents" / "profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    planner_seat = f"{team}-planner"
    builder_seat = f"{team}-builder-core"
    reviewer_seat = f"{team}-reviewer"
    profile = profiles / f"{project}-profile-dynamic.toml"
    profile.write_text(
        f'profile_name = "{project}-profile-dynamic"\n'
        f'project_name = "{project}"\n'
        f'seats = ["memory", "{planner_seat}", "{builder_seat}", "{reviewer_seat}"]\n'
        f"\n[mode]\nteam_structure = \"multi\"\n"
        f"\n[teams]\n"
        f'{team} = {{ seats = ["{planner_seat}", "{builder_seat}", "{reviewer_seat}"] }}\n'
        f"\n[seat_roles]\n"
        f'"memory" = "memory"\n'
        f'"{planner_seat}" = "planner"\n'
        f'"{builder_seat}" = "builder"\n'
        f'"{reviewer_seat}" = "reviewer"\n',
        encoding="utf-8",
    )
    return profile


def _write_brief(agents_root: Path, project: str, team: str, task_id: str, brief_yaml: str) -> Path:
    brief_dir = agents_root / "tasks" / project / team / "brief"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief = brief_dir / f"{task_id}.md"
    brief.write_text(f"---\n{brief_yaml}\n---\n\n# body\n", encoding="utf-8")
    return brief


# ---------------------------------------------------------------------------
# _resolve_reviewer_seat_from_profile: dev-minimal → planner fallback
# ---------------------------------------------------------------------------

def test_devminimal_routes_to_planner_not_reviewer(tmp_path: Path) -> None:
    """Dev-minimal team with no reviewer seat must route to planner, not {team}-reviewer."""
    profile = _write_devminimal_profile(tmp_path, "proj", "core")
    agents_root = tmp_path / ".agents"
    seat = _resolve_reviewer_seat_from_profile("core", "proj", agents_root=agents_root, profile_path=profile)
    assert seat == "core-planner", f"expected core-planner, got {seat!r}"
    assert "reviewer" not in seat


def test_devminimal_routes_to_planner_for_clawseat_core(tmp_path: Path) -> None:
    """Simulates the clawseat-core team (CF041/CF042 use case)."""
    profile = _write_devminimal_profile(tmp_path, "cartooner-front", "clawseat-core")
    agents_root = tmp_path / ".agents"
    seat = _resolve_reviewer_seat_from_profile(
        "clawseat-core", "cartooner-front", agents_root=agents_root, profile_path=profile
    )
    assert seat == "clawseat-core-planner", f"expected clawseat-core-planner, got {seat!r}"
    assert "reviewer" not in seat


def test_devminimal_never_produces_undeclared_reviewer(tmp_path: Path) -> None:
    """_resolve_reviewer_seat_from_profile must not return {team}-reviewer for dev-minimal."""
    profile = _write_devminimal_profile(tmp_path, "proj", "my-team")
    agents_root = tmp_path / ".agents"
    seat = _resolve_reviewer_seat_from_profile("my-team", "proj", agents_root=agents_root, profile_path=profile)
    assert not seat.endswith("-reviewer"), (
        f"dev-minimal routing must not produce a -reviewer seat; got {seat!r}"
    )


# ---------------------------------------------------------------------------
# _resolve_reviewer_seat_from_profile: dedicated reviewer → reviewer seat
# ---------------------------------------------------------------------------

def test_dedicated_reviewer_team_routes_to_reviewer(tmp_path: Path) -> None:
    """Dedicated-reviewer profile must still route to the reviewer seat."""
    profile = _write_dedicated_reviewer_profile(tmp_path, "proj", "product")
    agents_root = tmp_path / ".agents"
    seat = _resolve_reviewer_seat_from_profile("product", "proj", agents_root=agents_root, profile_path=profile)
    assert seat == "product-reviewer", f"expected product-reviewer, got {seat!r}"


def test_dedicated_reviewer_not_planner(tmp_path: Path) -> None:
    profile = _write_dedicated_reviewer_profile(tmp_path, "proj", "alpha")
    agents_root = tmp_path / ".agents"
    seat = _resolve_reviewer_seat_from_profile("alpha", "proj", agents_root=agents_root, profile_path=profile)
    assert "reviewer" in seat, f"dedicated-reviewer team must route to reviewer, got {seat!r}"
    assert "planner" not in seat


# ---------------------------------------------------------------------------
# _resolve_reviewer_seat_from_profile: missing profile → safe fallback
# ---------------------------------------------------------------------------

def test_missing_profile_falls_back_to_team_reviewer(tmp_path: Path) -> None:
    """When the profile file does not exist, returns {team}-reviewer as safe fallback."""
    agents_root = tmp_path / ".agents"
    agents_root.mkdir(parents=True)
    seat = _resolve_reviewer_seat_from_profile("core", "no-such-project", agents_root=agents_root)
    assert seat == "core-reviewer", f"expected core-reviewer fallback, got {seat!r}"


def test_explicit_missing_profile_path_falls_back(tmp_path: Path) -> None:
    agents_root = tmp_path / ".agents"
    agents_root.mkdir(parents=True)
    missing = tmp_path / "nonexistent-profile.toml"
    seat = _resolve_reviewer_seat_from_profile("t", "p", agents_root=agents_root, profile_path=missing)
    assert seat == "t-reviewer"


# ---------------------------------------------------------------------------
# route_reviewer: dev-minimal profile → dispatch to planner, not -reviewer
# ---------------------------------------------------------------------------

def test_route_reviewer_uses_planner_for_devminimal_team(tmp_path: Path) -> None:
    """route_reviewer must dispatch to planner seat for dev-minimal teams."""
    profile = _write_devminimal_profile(tmp_path, "proj", "core")
    agents_root = tmp_path / ".agents"
    acceptance_dir = tmp_path / "acceptance"

    captured = []

    def fake_dispatch(packet):
        captured.append(packet)
        return "dispatched"

    brief = {
        "task_id": "T-DEVMIN",
        "project": "proj",
        "team": "core",
        "objective": "test",
        "seats_required": ["builder"],
        "acceptance_criteria": {
            "mechanical": ["true"],
            "reviewer": ["planner confirms the fix is correct"],
        },
    }
    result = route_reviewer(
        brief, "proj", "core", "T-DEVMIN", acceptance_dir,
        dispatch_fn=fake_dispatch,
        profile_path=profile,
    )
    assert result.verdict == "PENDING"
    assert len(captured) == 1
    assert captured[0]["reviewer_seat"] == "core-planner", (
        f"dev-minimal reviewer must route to core-planner, got {captured[0]['reviewer_seat']!r}"
    )
    assert "reviewer" not in captured[0]["reviewer_seat"]


def test_route_reviewer_uses_real_reviewer_for_dedicated_team(tmp_path: Path) -> None:
    """route_reviewer must still dispatch to reviewer seat for dedicated-reviewer teams."""
    profile = _write_dedicated_reviewer_profile(tmp_path, "proj", "product")
    acceptance_dir = tmp_path / "acceptance"

    captured = []

    def fake_dispatch(packet):
        captured.append(packet)
        return "dispatched"

    brief = {
        "task_id": "T-DED",
        "project": "proj",
        "team": "product",
        "objective": "test",
        "seats_required": ["builder", "reviewer"],
        "acceptance_criteria": {
            "mechanical": ["true"],
            "reviewer": ["reviewer confirms UX correctness"],
        },
    }
    result = route_reviewer(
        brief, "proj", "product", "T-DED", acceptance_dir,
        dispatch_fn=fake_dispatch,
        profile_path=profile,
    )
    assert result.verdict == "PENDING"
    assert len(captured) == 1
    assert captured[0]["reviewer_seat"] == "product-reviewer", (
        f"dedicated-reviewer team must route to product-reviewer, got {captured[0]['reviewer_seat']!r}"
    )


def test_route_reviewer_does_not_skip_reviewer_acceptance(tmp_path: Path) -> None:
    """Reviewer acceptance must remain PENDING when items exist — not silently PASS."""
    profile = _write_devminimal_profile(tmp_path, "proj", "core")
    acceptance_dir = tmp_path / "acceptance"

    brief = {
        "task_id": "T-NOSKIP",
        "project": "proj",
        "team": "core",
        "objective": "test",
        "seats_required": ["builder"],
        "acceptance_criteria": {
            "mechanical": ["true"],
            "reviewer": ["planner confirms stale detection is non-noisy"],
        },
    }
    result = route_reviewer(
        brief, "proj", "core", "T-NOSKIP", acceptance_dir,
        profile_path=profile,
        dispatch_fn=lambda p: "dispatched",
    )
    assert result.verdict == "PENDING", "reviewer items must produce PENDING, not silent PASS"
    assert len(result.items) == 1


@pytest.mark.parametrize("team", ["core", "clawseat-core", "frontend", "backend"])
def test_devminimal_routing_parametrized(tmp_path: Path, team: str) -> None:
    """Parametrized: various dev-minimal teams all route to planner, not -reviewer."""
    profile = _write_devminimal_profile(tmp_path / team, "proj", team)
    agents_root = (tmp_path / team) / ".agents"
    seat = _resolve_reviewer_seat_from_profile(team, "proj", agents_root=agents_root, profile_path=profile)
    assert not seat.endswith("-reviewer"), (
        f"dev-minimal {team!r} routing produced -reviewer seat {seat!r}"
    )
    assert "planner" in seat
