#!/usr/bin/env python3
"""Seed approved v3 proposals for the MULTI_TEAM_MINIMAL template.

This is the compatibility bridge for the old ``clawseat-solo`` entry point:
solo is no longer a standalone single-mode runtime. It is the minimal dev
subteam archetype inside a v3 multi-team project group.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_list(items: list[str], *, indent: str = "  ") -> str:
    return "\n".join(f"{indent}- {_quote(item)}" for item in items)


def _header(project: str, team: str, ts: str) -> list[str]:
    return [
        "---",
        f"project: {project}",
        f"team: {team}",
        "proposal_status: approved",
        f"operator_approved_ts: {ts}",
    ]


def _subteam_yaml(project: str, team: str, ts: str, ownership_paths: list[str]) -> str:
    lines = _header(project, team, ts)
    lines.extend(
        [
            "team_type: subteam",
            "planner_mode: delivery",
            "notify_policy: queue_drained_only",
            "review_model: planner_owned",
            "dedicated_reviewer: false",
            "ownership_paths:",
            _yaml_list(ownership_paths),
            "scaling_policy:",
            "  max_builders: 3",
            "  reviewer_required_when_builders_gte: 2",
            "  overflow_action: propose_new_subteam",
            "  reviewer_fallback: planner",
            "seats:",
            "  - role: planner",
            "    tool: claude",
            "    provider: anthropic",
            "    auth_mode: oauth_token",
            f"    rationale: {_quote('claims this team queue, writes workflow.md, dispatches the minimal solo unit')}",
            "  - role: builder",
            "    instance: core",
            "    tool: codex",
            "    provider: openai",
            "    auth_mode: oauth",
            f"    purpose: {_quote('minimal implementation builder for this module/layer')}",
            "    capabilities: [implementation, tests, docs]",
            f"    rationale: {_quote('implements planner-assigned changes and returns DELIVERY.md evidence')}",
            "estimated_monthly_cost_usd: { low: 0, high: 30 }",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def _quality_docs_yaml(project: str, ts: str) -> str:
    lines = _header(project, "quality-docs", ts)
    lines.extend(
        [
            "team_type: quality-docs",
            "planner_mode: quality_campaign",
            "notify_policy: never_notify_memory",
            "quality_gate_doc: quality-docs/QUALITY.md",
            "autonomous: true",
            "loop: continuous",
            "stop_rule: campaign_clean_streak_3",
            "seats:",
            "  - role: planner",
            "    tool: claude",
            "    provider: minimax",
            "    auth_mode: api",
            f"    rationale: {_quote('designs campaigns, assigns patrols, maintains QUALITY.md, and researches findings')}",
            "  - role: patrol",
            "    instance: fast",
            "    tool: claude",
            "    provider: minimax",
            "    auth_mode: api",
            f"    rationale: {_quote('runs high-frequency deterministic checks and targeted regressions')}",
            "  - role: patrol",
            "    instance: human",
            "    tool: claude",
            "    provider: minimax",
            "    auth_mode: api",
            f"    rationale: {_quote('simulates human product workflows and records evidence')}",
            "  - role: patrol",
            "    instance: chaos",
            "    tool: claude",
            "    provider: minimax",
            "    auth_mode: api",
            f"    rationale: {_quote('tests failure injection, recovery, conflicts, and edge risks')}",
            "estimated_monthly_cost_usd: { low: 0, high: 20 }",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


_CARTOONER_PATHS = {
    "cartooner-front": [
        "apps/web/src/**",
        "apps/web/electron/**",
    ],
    "cartooner-runtime-platform": [
        "apps/web/electron/**",
        "apps/web/src/services/**",
        "core/launchers/**",
        "scripts/**",
    ],
    "cartooner-skills": [
        "core/skills/cartooner-harness/**",
        "~/.agents/skills/cartooner*/**",
    ],
}


def _default_teams(project: str, repo_root: str, archetype: str) -> list[str]:
    resolved = archetype
    if resolved == "auto":
        haystack = f"{project} {repo_root}".lower()
        resolved = "cartooner" if "cartooner" in haystack else "generic"
    if resolved == "cartooner":
        return ["cartooner-front", "quality-docs"]
    return ["core", "quality-docs"]


def _paths_for(team: str, archetype: str) -> list[str]:
    if archetype in {"auto", "cartooner"} and team in _CARTOONER_PATHS:
        return list(_CARTOONER_PATHS[team])
    if team in {"core", "product-surface"}:
        return ["**/*"]
    return [f"{team}/**", "src/**", "tests/**"]


def seed(
    *,
    project: str,
    output_dir: Path,
    repo_root: str,
    teams: list[str],
    archetype: str,
    force: bool,
) -> list[Path]:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    selected = list(teams or _default_teams(project, repo_root, archetype))
    if "quality-docs" not in selected:
        selected.append("quality-docs")
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for team in selected:
        path = output_dir / f"{team}__approved.yaml"
        if path.exists() and not force:
            continue
        if team == "quality-docs":
            text = _quality_docs_yaml(project, ts)
        else:
            text = _subteam_yaml(project, team, ts, _paths_for(team, archetype))
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed MULTI_TEAM_MINIMAL approved proposal YAML files."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--teams", default="")
    parser.add_argument("--archetype", choices=["auto", "generic", "cartooner"], default="auto")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    teams = [item.strip() for item in args.teams.split(",") if item.strip()]
    written = seed(
        project=args.project,
        output_dir=Path(args.output_dir),
        repo_root=args.repo_root,
        teams=teams,
        archetype=args.archetype,
        force=args.force,
    )
    for path in written:
        print(f"seeded {path}")
    if not written:
        print("seeded 0 files; existing approved proposals preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
