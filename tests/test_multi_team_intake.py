from __future__ import annotations

import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "core" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "core" / "scripts"))


def _approved_quality_docs_yaml(project: str = "p") -> str:
    return f"""---
project: {project}
team: quality-docs
proposal_status: approved
operator_approved_ts: 2026-05-14T00:00:00+00:00
autonomous: true
loop: continuous
stop_rule: campaign_clean_streak_3
seats:
  - role: planner
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: writes QA campaigns and docs
  - role: patrol
    instance: fast
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: runs deterministic smoke and targeted tests
  - role: patrol
    instance: human
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: simulates human product workflows
  - role: patrol
    instance: chaos
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: tests failure injection and recovery
estimated_monthly_cost_usd: {{ low: 0, high: 20 }}
---
"""


def _approved_subteam_yaml(project: str = "p") -> str:
    return f"""---
project: {project}
team: cartooner-front
proposal_status: approved
operator_approved_ts: 2026-05-14T00:00:00+00:00
team_type: subteam
ownership_paths:
  - apps/web/src/components/**
  - apps/web/src/store/**
scaling_policy:
  max_builders: 3
  reviewer_required_when_builders_gte: 2
  overflow_action: propose_new_subteam
  reviewer_fallback: planner
seats:
  - role: planner
    tool: claude
    provider: anthropic
    auth_mode: oauth_token
    rationale: plans front work
  - role: builder
    instance: core
    tool: codex
    provider: openai
    auth_mode: oauth
    purpose: front product surface generalist
    capabilities: [react, zustand, vibe-canvas]
    rationale: implements front work
estimated_monthly_cost_usd: {{ low: 0, high: 30 }}
---
"""


def test_render_supports_named_same_role_instances(tmp_path: Path) -> None:
    from render_project_toml_v3 import render_project_toml_v3

    proposals = tmp_path / "_config-proposals"
    proposals.mkdir()
    (proposals / "quality-docs__approved.yaml").write_text(
        _approved_quality_docs_yaml(),
        encoding="utf-8",
    )

    data = tomllib.loads(render_project_toml_v3(project="p", proposals_dir=proposals))

    assert data["teams"]["quality-docs"]["autonomous"] is True
    assert data["teams"]["quality-docs"]["loop"] == "continuous"
    assert data["teams"]["quality-docs"]["stop_rule"] == "campaign_clean_streak_3"
    assert data["teams"]["quality-docs"]["seats"] == [
        "quality-docs-planner",
        "quality-docs-patrol-fast",
        "quality-docs-patrol-human",
        "quality-docs-patrol-chaos",
    ]
    assert data["seat_roles"]["quality-docs-patrol-fast"] == "patrol"
    assert data["seat_roles"]["quality-docs-patrol-human"] == "patrol"
    assert data["seat_overrides"]["quality-docs-patrol-chaos"]["instance"] == "chaos"


def test_render_preserves_subteam_scaling_and_ownership(tmp_path: Path) -> None:
    from render_project_toml_v3 import render_project_toml_v3

    proposals = tmp_path / "_config-proposals"
    proposals.mkdir()
    (proposals / "cartooner-front__approved.yaml").write_text(
        _approved_subteam_yaml(),
        encoding="utf-8",
    )

    data = tomllib.loads(render_project_toml_v3(project="p", proposals_dir=proposals))

    team = data["teams"]["cartooner-front"]
    assert team["team_type"] == "subteam"
    assert team["ownership_paths"] == [
        "apps/web/src/components/**",
        "apps/web/src/store/**",
    ]
    assert team["scaling_policy"] == {
        "max_builders": 3,
        "reviewer_required_when_builders_gte": 2,
        "overflow_action": "propose_new_subteam",
        "reviewer_fallback": "planner",
    }
    assert data["seat_overrides"]["cartooner-front-builder-core"]["instance"] == "core"
    assert data["seat_overrides"]["cartooner-front-builder-core"]["capabilities"] == [
        "react",
        "zustand",
        "vibe-canvas",
    ]


def test_validator_rejects_duplicate_same_role_without_instance(tmp_path: Path) -> None:
    from proposal_validator import validate_proposal_file

    proposal = tmp_path / "quality-docs__approved.yaml"
    proposal.write_text(
        """---
project: p
team: quality-docs
proposal_status: approved
operator_approved_ts: 2026-05-14T00:00:00+00:00
seats:
  - role: patrol
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: one
  - role: patrol
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: two
estimated_monthly_cost_usd: { low: 0, high: 20 }
---
""",
        encoding="utf-8",
    )

    report = validate_proposal_file(proposal)
    assert not report.ok
    assert any("duplicate role/instance identity" in v for v in report.violations)


def test_validator_rejects_bad_instance_name(tmp_path: Path) -> None:
    from proposal_validator import validate_proposal_file

    proposal = tmp_path / "quality-docs__approved.yaml"
    proposal.write_text(
        """---
project: p
team: quality-docs
proposal_status: approved
operator_approved_ts: 2026-05-14T00:00:00+00:00
seats:
  - role: patrol
    instance: "Fast Lane"
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: invalid
estimated_monthly_cost_usd: { low: 0, high: 20 }
---
""",
        encoding="utf-8",
    )

    report = validate_proposal_file(proposal)
    assert not report.ok
    assert any("instance='Fast Lane'" in v for v in report.violations)


def test_validator_requires_reviewer_for_multi_builder_subteam(tmp_path: Path) -> None:
    from proposal_validator import validate_proposal_file

    proposal = tmp_path / "front__approved.yaml"
    proposal.write_text(
        """---
project: p
team: front
proposal_status: approved
operator_approved_ts: 2026-05-14T00:00:00+00:00
team_type: subteam
ownership_paths: [apps/web/src/**]
scaling_policy:
  max_builders: 3
  reviewer_required_when_builders_gte: 2
  overflow_action: propose_new_subteam
  reviewer_fallback: planner
seats:
  - role: planner
    tool: claude
    provider: anthropic
    auth_mode: oauth_token
    rationale: plans
  - role: builder
    instance: app-shell
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: one
  - role: builder
    instance: canvas
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: two
estimated_monthly_cost_usd: { low: 0, high: 30 }
---
""",
        encoding="utf-8",
    )

    report = validate_proposal_file(proposal)
    assert not report.ok
    assert any("must declare a reviewer" in v for v in report.violations)


def test_validator_rejects_four_builder_subteam(tmp_path: Path) -> None:
    from proposal_validator import validate_proposal_file

    proposal = tmp_path / "front__approved.yaml"
    proposal.write_text(
        """---
project: p
team: front
proposal_status: approved
operator_approved_ts: 2026-05-14T00:00:00+00:00
team_type: subteam
ownership_paths: [apps/web/src/**]
scaling_policy:
  max_builders: 3
  reviewer_required_when_builders_gte: 2
  overflow_action: propose_new_subteam
  reviewer_fallback: planner
seats:
  - role: planner
    tool: claude
    provider: anthropic
    auth_mode: oauth_token
    rationale: plans
  - role: builder
    instance: one
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: one
  - role: builder
    instance: two
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: two
  - role: builder
    instance: three
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: three
  - role: builder
    instance: four
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: four
  - role: reviewer
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: reviews
estimated_monthly_cost_usd: { low: 0, high: 30 }
---
""",
        encoding="utf-8",
    )

    report = validate_proposal_file(proposal)
    assert not report.ok
    assert any("max is 3" in v for v in report.violations)


def test_multi_team_intake_skill_documents_generic_quality_group() -> None:
    skill = REPO_ROOT / "core" / "skills" / "multi-team-intake" / "SKILL.md"
    reference = (
        REPO_ROOT
        / "core"
        / "skills"
        / "multi-team-intake"
        / "references"
        / "generic-project-group.md"
    )

    text = skill.read_text(encoding="utf-8")
    ref_text = reference.read_text(encoding="utf-8")

    assert "module/layer-based team topology" in text
    assert "reviewer_required_when_builders_gte" in text
    assert "propose_new_subteam" in text
    assert "quality-docs" in text
    assert "campaign_clean_streak_3" in text
    assert "patrol-fast" in text and "patrol-human" in text and "patrol-chaos" in text
    assert "cartooner-front" in ref_text
    assert "cartooner-runtime-platform" in ref_text
    assert "cartooner-skills" in ref_text
    assert "product-surface" in ref_text
    assert "runtime-platform" in ref_text
    assert "orchestration-ops" in ref_text
