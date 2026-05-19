"""CF050: Focused tests for the planner-only engineering subgroup profile.

Verifies that:
- seed_multi_team_minimal.py --profile planner-only generates valid YAML with
  planner seat(s), no builder, no reviewer, and planner-owned review model.
- subgroup-profiles.toml includes [profiles.planner-only] without changing
  existing dev-minimal, dev-standard, or test definitions.
- install_multi.sh --help lists the planner-only profile.
- Existing profiles are unchanged.
"""
from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_SCRIPT = REPO_ROOT / "core" / "scripts" / "seed_multi_team_minimal.py"
INSTALL_MULTI = REPO_ROOT / "scripts" / "install_multi.sh"
PROFILES_TOML = REPO_ROOT / "core" / "templates" / "subgroup-profiles.toml"
SUBGROUP_GUIDE = REPO_ROOT / "docs" / "guides" / "subgroup-profiles.md"

sys.path.insert(0, str(REPO_ROOT / "core" / "scripts"))


# ---------------------------------------------------------------------------
# subgroup-profiles.toml
# ---------------------------------------------------------------------------

def test_profiles_toml_includes_planner_only():
    """[profiles.planner-only] must exist in subgroup-profiles.toml."""
    data = tomllib.loads(PROFILES_TOML.read_text(encoding="utf-8"))
    profiles = data.get("profiles", {})
    assert "planner-only" in profiles, (
        "subgroup-profiles.toml must include [profiles.planner-only]"
    )


def test_profiles_toml_planner_only_has_no_builder():
    """planner-only profile must declare dedicated_builder: false and no reviewer."""
    data = tomllib.loads(PROFILES_TOML.read_text(encoding="utf-8"))
    po = data["profiles"]["planner-only"]
    assert po.get("dedicated_builder") is False, "planner-only must have dedicated_builder=false"
    assert po.get("reviewer_required") is False, "planner-only must have reviewer_required=false"
    assert po.get("review_model") == "planner_owned", "planner-only must use planner_owned review"


def test_profiles_toml_planner_only_has_planner_seat():
    """planner-only seats must include 'planner' and must not include 'builder' or 'reviewer'."""
    data = tomllib.loads(PROFILES_TOML.read_text(encoding="utf-8"))
    seats = data["profiles"]["planner-only"].get("seats", [])
    assert "planner" in seats, "planner-only must declare planner seat"
    assert "builder" not in seats, "planner-only must not declare builder seat"
    assert "reviewer" not in seats, "planner-only must not declare reviewer seat"


def test_profiles_toml_existing_profiles_unchanged():
    """dev-minimal, dev-standard, and test profiles must not change."""
    data = tomllib.loads(PROFILES_TOML.read_text(encoding="utf-8"))
    profiles = data["profiles"]
    # dev-minimal: planner + builder
    dm = profiles["dev-minimal"]
    assert "planner" in dm["seats"] and "builder" in dm["seats"]
    assert dm.get("reviewer_required") is False
    # dev-standard: has reviewer
    ds = profiles["dev-standard"]
    assert ds.get("reviewer_required") is True
    # test: quality-docs
    test = profiles["test"]
    assert test.get("team_type") == "quality-docs"


# ---------------------------------------------------------------------------
# seed_multi_team_minimal.py
# ---------------------------------------------------------------------------

def _run_seed(tmp_path: Path, profile: str, teams: str = "engineering") -> dict[str, Path]:
    result = subprocess.run(
        [
            sys.executable,
            str(SEED_SCRIPT),
            "--project", "test-proj",
            "--output-dir", str(tmp_path),
            "--repo-root", "/tmp/test-proj",
            "--teams", teams,
            "--archetype", "generic",
            "--profile", profile,
            "--force",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"seed failed:\n{result.stderr}"
    return {p.stem.replace("__approved", ""): p for p in tmp_path.glob("*__approved.yaml")}


def test_seed_planner_only_generates_yaml(tmp_path: Path):
    files = _run_seed(tmp_path, "planner-only")
    assert "engineering" in files, "seed must generate engineering__approved.yaml"


def test_seed_planner_only_yaml_has_planner_seat(tmp_path: Path):
    files = _run_seed(tmp_path, "planner-only")
    text = files["engineering"].read_text(encoding="utf-8")
    assert "role: planner" in text, "planner-only YAML must declare a planner seat"


def test_seed_planner_only_yaml_has_no_builder_seat(tmp_path: Path):
    files = _run_seed(tmp_path, "planner-only")
    text = files["engineering"].read_text(encoding="utf-8")
    assert "role: builder" not in text, "planner-only YAML must not declare a builder seat"


def test_seed_planner_only_yaml_has_no_reviewer_seat(tmp_path: Path):
    files = _run_seed(tmp_path, "planner-only")
    text = files["engineering"].read_text(encoding="utf-8")
    assert "role: reviewer" not in text, "planner-only YAML must not declare a reviewer seat"


def test_seed_planner_only_yaml_has_planner_owned_review(tmp_path: Path):
    files = _run_seed(tmp_path, "planner-only")
    text = files["engineering"].read_text(encoding="utf-8")
    assert "review_model: planner_owned" in text, "planner-only must use planner_owned review_model"


def test_seed_planner_only_yaml_has_subgroup_profile_tag(tmp_path: Path):
    files = _run_seed(tmp_path, "planner-only")
    text = files["engineering"].read_text(encoding="utf-8")
    assert "subgroup_profile: planner-only" in text


def test_seed_planner_only_yaml_has_planner_test_lock_required(tmp_path: Path):
    files = _run_seed(tmp_path, "planner-only")
    text = files["engineering"].read_text(encoding="utf-8")
    assert "planner_test_lock_required: true" in text


def test_seed_planner_only_does_not_append_quality_docs(tmp_path: Path):
    """planner-only does not auto-append quality-docs (unlike dev-minimal/dev-standard)."""
    files = _run_seed(tmp_path, "planner-only", teams="engineering")
    assert "quality-docs" not in files, (
        "planner-only must not auto-append quality-docs team"
    )


def test_seed_existing_profiles_not_broken(tmp_path: Path):
    """dev-minimal, dev-standard, and test seeding still works."""
    for profile in ("dev-minimal", "dev-standard", "test"):
        out = tmp_path / profile
        out.mkdir()
        result = subprocess.run(
            [
                sys.executable, str(SEED_SCRIPT),
                "--project", "p",
                "--output-dir", str(out),
                "--teams", "core",
                "--archetype", "generic",
                "--profile", profile,
                "--force",
            ],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, f"{profile} seed failed: {result.stderr}"
        yamls = list(out.glob("*__approved.yaml"))
        assert yamls, f"{profile} must generate at least one approved YAML"


# ---------------------------------------------------------------------------
# install_multi.sh --help
# ---------------------------------------------------------------------------

def test_install_multi_help_lists_planner_only():
    """install_multi.sh --help must mention planner-only profile."""
    result = subprocess.run(
        ["bash", str(INSTALL_MULTI), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert "planner-only" in output, (
        "install_multi.sh --help must list the planner-only profile"
    )


# ---------------------------------------------------------------------------
# docs/guides/subgroup-profiles.md
# ---------------------------------------------------------------------------

def test_subgroup_guide_documents_planner_only():
    text = SUBGROUP_GUIDE.read_text(encoding="utf-8")
    assert "planner-only" in text, "subgroup-profiles.md must document planner-only profile"


def test_subgroup_guide_covers_four_profiles():
    text = SUBGROUP_GUIDE.read_text(encoding="utf-8")
    assert "four" in text.lower() or "4" in text, (
        "subgroup-profiles.md must note there are now four profiles"
    )


# ---------------------------------------------------------------------------
# CF050 rework1: --planner-count tests
# ---------------------------------------------------------------------------

def test_seed_planner_only_default_one_planner(tmp_path: Path):
    """Default planner-only generates exactly one planner seat."""
    files = _run_seed(tmp_path, "planner-only")
    text = files["engineering"].read_text(encoding="utf-8")
    planner_count = text.count("role: planner")
    assert planner_count == 1, f"default planner-only must have 1 planner seat, got {planner_count}"


def test_seed_planner_only_two_planners(tmp_path: Path):
    """--planner-count 2 generates two planner seats with distinct instances."""
    result = subprocess.run(
        [
            sys.executable,
            str(SEED_SCRIPT),
            "--project", "test-proj",
            "--output-dir", str(tmp_path),
            "--repo-root", "/tmp/test-proj",
            "--teams", "engineering",
            "--archetype", "generic",
            "--profile", "planner-only",
            "--planner-count", "2",
            "--force",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"seed with --planner-count 2 failed:\n{result.stderr}"
    files = {p.stem.replace("__approved", ""): p for p in tmp_path.glob("*__approved.yaml")}
    text = files["engineering"].read_text(encoding="utf-8")
    planner_count = text.count("role: planner")
    assert planner_count == 2, f"--planner-count 2 must generate 2 planner seats, got {planner_count}"
    # Must have distinct instance labels
    assert "instance: primary" in text, "first planner must have instance: primary"
    assert "instance: secondary" in text, "second planner must have instance: secondary"
    # No builder/reviewer still
    assert "role: builder" not in text
    assert "role: reviewer" not in text


def test_seed_planner_only_three_planners(tmp_path: Path):
    """--planner-count 3 generates three planner seats."""
    result = subprocess.run(
        [
            sys.executable,
            str(SEED_SCRIPT),
            "--project", "test-proj",
            "--output-dir", str(tmp_path),
            "--repo-root", "/tmp/test-proj",
            "--teams", "engineering",
            "--archetype", "generic",
            "--profile", "planner-only",
            "--planner-count", "3",
            "--force",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    files = {p.stem.replace("__approved", ""): p for p in tmp_path.glob("*__approved.yaml")}
    text = files["engineering"].read_text(encoding="utf-8")
    assert text.count("role: planner") == 3


def test_profiles_toml_header_says_four_profiles():
    """subgroup-profiles.toml header comment must say 'Four hot-pluggable subgroup profiles'."""
    text = PROFILES_TOML.read_text(encoding="utf-8")
    assert "Four hot-pluggable" in text or "four" in text.lower(), (
        "subgroup-profiles.toml header must reflect that there are now four profiles"
    )


def test_profiles_toml_usage_includes_planner_only():
    """Usage comment in subgroup-profiles.toml must include planner-only."""
    text = PROFILES_TOML.read_text(encoding="utf-8")
    assert "planner-only" in text, (
        "subgroup-profiles.toml usage/comment must include planner-only"
    )


def test_subgroup_guide_documents_planner_count():
    """docs/guides/subgroup-profiles.md must document --planner-count."""
    text = SUBGROUP_GUIDE.read_text(encoding="utf-8")
    assert "--planner-count" in text, (
        "subgroup-profiles.md must document --planner-count flag"
    )


def test_subgroup_guide_shared_invariants_says_four_not_three():
    """Regression: Shared Invariants section must not say 'All three profiles' after CF050."""
    text = SUBGROUP_GUIDE.read_text(encoding="utf-8")
    assert "All three profiles" not in text, (
        "subgroup-profiles.md must not say 'All three profiles' — planner-only is the fourth"
    )
    assert "All four profiles" in text, (
        "subgroup-profiles.md Shared Invariants must say 'All four profiles'"
    )
