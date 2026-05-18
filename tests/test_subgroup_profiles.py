"""Tests for ClawSeat subgroup profiles (cf030).

Covers:
- dev-minimal: planner + builder, planner_owned review, no reviewer required
- dev-standard: planner + 2 builders + reviewer, reviewer gate required
- test: planner + patrol, quality-docs type
- hot-plug: adding a subgroup does not delete existing task data
- template phrase coverage: local review/latest, no push/PR, OpenClaw optional
- subgroup-profiles.toml: machine-readable profile definitions
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run_seed(tmp_path: Path, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
    proposals = tmp_path / "proposals"
    proposals.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            str(REPO / "core" / "scripts" / "seed_multi_team_minimal.py"),
            "--project", "testproj",
            "--output-dir", str(proposals),
        ] + extra_args,
        capture_output=True,
        text=True,
        check=False,
    )


# ── dev-minimal ──────────────────────────────────────────────────────────────


def test_seed_dev_minimal_default_produces_planner_and_builder(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text()
    assert "role: planner" in yaml_text
    assert "role: builder" in yaml_text
    assert "role: reviewer" not in yaml_text


def test_seed_dev_minimal_explicit_sets_planner_owned_review(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-minimal"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text()
    assert "review_model: planner_owned" in yaml_text
    assert "dedicated_reviewer: false" in yaml_text


def test_seed_dev_minimal_names_profile_in_yaml(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-minimal"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text()
    assert "dev-minimal" in yaml_text


def test_seed_dev_minimal_does_not_include_openclaw_feishu_koder(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-minimal"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text().lower()
    assert "openclaw" not in yaml_text
    assert "feishu" not in yaml_text
    assert "koder" not in yaml_text
    assert "lark" not in yaml_text


# ── dev-standard ─────────────────────────────────────────────────────────────


def test_seed_dev_standard_produces_2_builders_and_reviewer(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-standard"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text()
    assert yaml_text.count("role: builder") == 2
    assert "role: reviewer" in yaml_text


def test_seed_dev_standard_has_reviewer_required_gte(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-standard"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text()
    assert "reviewer_required_when_builders_gte: 2" in yaml_text


def test_seed_dev_standard_names_profile(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-standard"])
    assert result.returncode == 0, result.stderr
    assert "dev-standard" in (tmp_path / "proposals" / "myteam__approved.yaml").read_text()


def test_seed_dev_standard_builders_have_disjoint_instances(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-standard"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text()
    assert "instance: primary" in yaml_text
    assert "instance: secondary" in yaml_text


# ── test group ────────────────────────────────────────────────────────────────


def test_seed_test_group_produces_planner_and_patrol(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "qa-team", "--profile", "test"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "qa-team__approved.yaml").read_text()
    assert "role: planner" in yaml_text
    assert "role: patrol" in yaml_text
    assert "role: builder" not in yaml_text
    assert "role: reviewer" not in yaml_text


def test_seed_test_group_is_quality_docs_type(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "qa-team", "--profile", "test"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "qa-team__approved.yaml").read_text()
    assert "team_type: quality-docs" in yaml_text


def test_seed_test_group_names_profile(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "qa-team", "--profile", "test"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "qa-team__approved.yaml").read_text()
    assert "subgroup_profile: test" in yaml_text


def test_seed_test_group_has_quality_campaign_mode(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "qa-team", "--profile", "test"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "qa-team__approved.yaml").read_text()
    assert "planner_mode: quality_campaign" in yaml_text
    assert "notify_policy: never_notify_memory" in yaml_text


# ── invalid profile ───────────────────────────────────────────────────────────


def test_seed_invalid_profile_raises_error(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "unknown-profile"])
    assert result.returncode != 0


# ── hot-plug ──────────────────────────────────────────────────────────────────


def test_hotplug_adding_subgroup_preserves_existing_queue_file(tmp_path: Path) -> None:
    # Simulate an existing queue file from a different team
    queue_file = tmp_path / "existing_queue.jsonl"
    queue_file.write_text('{"task_id": "t1"}\n', encoding="utf-8")
    result = _run_seed(tmp_path, ["--teams", "new-team", "--profile", "dev-minimal"])
    assert result.returncode == 0, result.stderr
    assert queue_file.read_text(encoding="utf-8") == '{"task_id": "t1"}\n', (
        "hot-plug must not delete or modify existing task queue data"
    )


def test_hotplug_does_not_overwrite_existing_approved_yaml_without_force(tmp_path: Path) -> None:
    existing = tmp_path / "proposals" / "myteam__approved.yaml"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("# original content\n", encoding="utf-8")
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-standard"])
    assert result.returncode == 0, result.stderr
    assert existing.read_text(encoding="utf-8") == "# original content\n", (
        "without --force, existing approved proposals must be preserved (hot-plug safety)"
    )


def test_hotplug_with_force_overwrites_existing(tmp_path: Path) -> None:
    existing = tmp_path / "proposals" / "myteam__approved.yaml"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("# original\n", encoding="utf-8")
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-standard", "--force"])
    assert result.returncode == 0, result.stderr
    assert existing.read_text(encoding="utf-8") != "# original\n", "--force should overwrite"


def test_hotplug_adding_new_team_does_not_touch_other_team_yaml(tmp_path: Path) -> None:
    existing_team = tmp_path / "proposals" / "existing-team__approved.yaml"
    existing_team.parent.mkdir(parents=True, exist_ok=True)
    existing_team.write_text("# existing team data\n", encoding="utf-8")
    result = _run_seed(tmp_path, ["--teams", "new-team", "--profile", "dev-minimal"])
    assert result.returncode == 0, result.stderr
    assert existing_team.read_text(encoding="utf-8") == "# existing team data\n", (
        "hot-plug add of new team must not modify other team proposals"
    )


# ── docs / config existence and content ───────────────────────────────────────


def test_subgroup_profiles_doc_exists() -> None:
    doc = REPO / "docs" / "guides" / "subgroup-profiles.md"
    assert doc.exists(), f"subgroup-profiles.md must exist at {doc}"


def test_subgroup_profiles_doc_contains_all_three_profile_names() -> None:
    doc = (REPO / "docs" / "guides" / "subgroup-profiles.md").read_text(encoding="utf-8")
    assert "dev-minimal" in doc
    assert "dev-standard" in doc
    assert "test group" in doc


def test_subgroup_profiles_doc_contains_hotplug_term() -> None:
    doc = (REPO / "docs" / "guides" / "subgroup-profiles.md").read_text(encoding="utf-8")
    assert "hot-plug" in doc or "hot plug" in doc


def test_subgroup_profiles_doc_contains_review_latest() -> None:
    doc = (REPO / "docs" / "guides" / "subgroup-profiles.md").read_text(encoding="utf-8")
    assert "local review/latest" in doc


def test_subgroup_profiles_doc_contains_no_push_no_pr() -> None:
    doc = (REPO / "docs" / "guides" / "subgroup-profiles.md").read_text(encoding="utf-8")
    assert "no push" in doc.lower() or "No push" in doc
    assert "no PR" in doc or "no pr" in doc.lower()


def test_subgroup_profiles_doc_composition_terms() -> None:
    doc = (REPO / "docs" / "guides" / "subgroup-profiles.md").read_text(encoding="utf-8")
    assert "planner + builder" in doc
    assert "2 builders" in doc
    assert "planner + patrol" in doc


# ── subgroup-profiles.toml ────────────────────────────────────────────────────


def test_subgroup_profiles_toml_exists() -> None:
    toml = REPO / "core" / "templates" / "subgroup-profiles.toml"
    assert toml.exists(), f"subgroup-profiles.toml must exist at {toml}"


def test_subgroup_profiles_toml_has_all_three_profiles() -> None:
    data = tomllib.loads(
        (REPO / "core" / "templates" / "subgroup-profiles.toml").read_text(encoding="utf-8")
    )
    assert "dev-minimal" in data.get("profiles", {}), "dev-minimal profile must exist"
    assert "dev-standard" in data.get("profiles", {}), "dev-standard profile must exist"
    assert "test" in data.get("profiles", {}), "test profile must exist"


def test_subgroup_profiles_toml_dev_minimal_is_default() -> None:
    data = tomllib.loads(
        (REPO / "core" / "templates" / "subgroup-profiles.toml").read_text(encoding="utf-8")
    )
    assert data.get("invariants", {}).get("default_profile") == "dev-minimal"


def test_subgroup_profiles_toml_invariants_validation_branch() -> None:
    data = tomllib.loads(
        (REPO / "core" / "templates" / "subgroup-profiles.toml").read_text(encoding="utf-8")
    )
    invariants = data.get("invariants", {})
    assert "local review/latest" in invariants.get("validation_branch", "")


# ── template phrase coverage ──────────────────────────────────────────────────


def test_builder_template_contains_review_latest() -> None:
    tmpl = (REPO / "core" / "templates" / "workspace-builder.template.md.codex").read_text(encoding="utf-8")
    assert "local review/latest" in tmpl


def test_builder_template_contains_no_push_no_pr() -> None:
    tmpl = (REPO / "core" / "templates" / "workspace-builder.template.md.codex").read_text(encoding="utf-8")
    assert "no push" in tmpl.lower() or "No push" in tmpl
    assert "no PR" in tmpl or "no pr" in tmpl.lower()


def test_builder_template_contains_ci_opt_in() -> None:
    tmpl = (REPO / "core" / "templates" / "workspace-builder.template.md.codex").read_text(encoding="utf-8")
    assert "CI opt-in" in tmpl or "ci opt-in" in tmpl.lower()


def test_planner_template_contains_review_latest() -> None:
    tmpl = (REPO / "core" / "templates" / "workspace-planner.template.md.gemini").read_text(encoding="utf-8")
    assert "local review/latest" in tmpl


def test_planner_template_contains_profile_names() -> None:
    tmpl = (REPO / "core" / "templates" / "workspace-planner.template.md.gemini").read_text(encoding="utf-8")
    assert "dev-minimal" in tmpl
    assert "dev-standard" in tmpl
    assert "planner + patrol" in tmpl


def test_patrol_template_contains_review_latest() -> None:
    tmpl = (REPO / "core" / "templates" / "workspace-patrol.template.md.claude.minimax").read_text(encoding="utf-8")
    assert "local review/latest" in tmpl


def test_reviewer_template_contains_review_latest() -> None:
    tmpl = (REPO / "core" / "templates" / "workspace-reviewer.template.md").read_text(encoding="utf-8")
    assert "local review/latest" in tmpl


def test_reviewer_template_contains_dev_standard_mention() -> None:
    tmpl = (REPO / "core" / "templates" / "workspace-reviewer.template.md").read_text(encoding="utf-8")
    assert "dev-standard" in tmpl


# ── OpenClaw decoupling ───────────────────────────────────────────────────────


def test_dev_minimal_yaml_does_not_require_openclaw(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-minimal"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text(encoding="utf-8").lower()
    assert "openclaw" not in yaml_text
    assert "feishu" not in yaml_text
    assert "lark" not in yaml_text


def test_dev_standard_yaml_does_not_require_openclaw(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "myteam", "--profile", "dev-standard"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "myteam__approved.yaml").read_text(encoding="utf-8").lower()
    assert "openclaw" not in yaml_text
    assert "feishu" not in yaml_text


def test_test_group_yaml_does_not_require_openclaw(tmp_path: Path) -> None:
    result = _run_seed(tmp_path, ["--teams", "qa-team", "--profile", "test"])
    assert result.returncode == 0, result.stderr
    yaml_text = (tmp_path / "proposals" / "qa-team__approved.yaml").read_text(encoding="utf-8").lower()
    assert "openclaw" not in yaml_text
    assert "feishu" not in yaml_text
