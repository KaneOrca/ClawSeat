# Generic Project Group Proposal Pack

This is the default shape for a ClawSeat v3 multi-team project group. Memory
must adapt names and ownership paths after scanning the actual repo.

## Recommendation Card

```text
topology_strategy: module-layered-autonomous-quality
project_archetype: derived-from-repo
phase_1_teams:
  - product-surface
  - runtime-platform
  - domain-capability
  - orchestration-ops
  - quality-docs
phase_2_optional:
  - reviewer/security
  - release/deploy
  - media/provider-specialist
```

Merge a team when the repo has no matching surface. Split a team when one layer
contains clearly independent modules with different owners, tests, and failure
modes.

## Proposed YAML Examples

### product-surface__proposed.yaml

```yaml
project: <project>
team: product-surface
proposal_status: proposed
seats:
  - role: planner
    tool: claude
    provider: anthropic
    auth_mode: oauth_token
    rationale: "plans user-visible product/UI work and owns this team's workflow."
  - role: builder
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: "implements UI/product changes and targeted tests."
estimated_monthly_cost_usd: { low: 0, high: 30 }
```

### runtime-platform__proposed.yaml

```yaml
project: <project>
team: runtime-platform
proposal_status: proposed
seats:
  - role: planner
    tool: claude
    provider: anthropic
    auth_mode: oauth_token
    rationale: "plans runtime, SDK/provider, env, auth, IPC, and local-path work."
  - role: builder
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: "implements runtime/integration changes and regression tests."
estimated_monthly_cost_usd: { low: 0, high: 30 }
```

### domain-capability__proposed.yaml

```yaml
project: <project>
team: domain-capability
proposal_status: proposed
seats:
  - role: planner
    tool: claude
    provider: anthropic
    auth_mode: oauth_token
    rationale: "plans domain-specific skills, pipelines, content, or business logic."
  - role: builder
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: "implements domain capability changes and fixtures."
estimated_monthly_cost_usd: { low: 0, high: 30 }
```

### orchestration-ops__proposed.yaml

```yaml
project: <project>
team: orchestration-ops
proposal_status: proposed
seats:
  - role: planner
    tool: claude
    provider: anthropic
    auth_mode: oauth_token
    rationale: "plans project-group lifecycle, install, restart, recovery, and queue protocol work."
  - role: builder
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: "implements automation/ops scripts and protocol tests."
estimated_monthly_cost_usd: { low: 0, high: 30 }
```

### quality-docs__proposed.yaml

```yaml
project: <project>
team: quality-docs
proposal_status: proposed
autonomous: true
loop: continuous
stop_rule: campaign_clean_streak_3
seats:
  - role: planner
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: "designs campaigns, assigns patrols, maintains QA docs, and routes findings."
  - role: patrol
    instance: fast
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: "runs high-frequency deterministic checks: typecheck, unit, targeted tests, queue smoke."
  - role: patrol
    instance: human
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: "simulates real user workflows and captures screenshots/logs."
  - role: patrol
    instance: chaos
    tool: claude
    provider: minimax
    auth_mode: api
    rationale: "tests failure injection, recovery, missing credentials, port/session conflicts, and long-running state."
estimated_monthly_cost_usd: { low: 0, high: 20 }
```

## Quality-Docs Artifacts

`quality-docs-planner` maintains:

```text
docs/qa/TEST_STRATEGY.md
docs/qa/TEST_MATRIX.md
docs/qa/RISK_REGISTER.md
docs/qa/STATUS.md
~/.agents/tasks/<project>/quality-docs/campaigns/
~/.agents/tasks/<project>/quality-docs/missions/
~/.agents/tasks/<project>/quality-docs/runs/
~/.agents/tasks/<project>/quality-docs/findings/
~/.agents/tasks/<project>/quality-docs/evidence/
```

Every closed finding becomes a regression scenario in `TEST_MATRIX.md`.
