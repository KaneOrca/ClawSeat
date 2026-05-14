# MULTI_TEAM_MINIMAL Design Notes

Status: draft-agreed context snapshot
Last updated: 2026-05-14

This note records the decisions agreed with the operator before implementing the
minimal multi-team template and the future memory-driven team-design skill.

## Goal

`MULTI_TEAM_MINIMAL` is not a traditional standalone `templates/*.toml`
runtime roster. It is a minimal multi-team proposal pack and intake workflow for
v3:

1. A first project-level memory seat analyzes the target repo.
2. Memory recommends a team topology and explains why.
3. Memory writes reviewable config proposals under
   `~/.agents/tasks/<project>/_config-proposals/`.
4. The operator approves proposals.
5. `scripts/install.sh --mode multi --project <p> --teams <csv>` renders the
   v3 profile and team workspaces.

The first project-level memory seat is a project-group architect. It is not a
team-local memory.

## Non-Goals

- Do not depend on `core/seat-templates/` for the first minimal version. The v3
  seat template catalog is still under development.
- Do not add `MULTI_TEAM_MINIMAL` to the standalone `--template` whitelist.
- Do not require iTerm. Cartooner-integrated multi-team testing uses tmux and
  embedded terminals / `--no-window`.
- Do not start with reviewer, patrol, image, or creative lane complexity.
- Do not assume the old Cartooner Python/OpenClaw backend architecture.

## Cartooner Facts Used For The Design

Current Cartooner mainline is SDK-only:

- Desktop host: Electron.
- UI: React / Vite / TypeScript.
- Agent channel: Claude Code SDK.
- Main product surfaces: chat sidebar, Vibe Canvas, Tactical HUD, asset sidebars,
  inspiration browser, project management.
- Workflow visualization: task / phase / decision / deliverable nodes.
- Event model: SDK raw events, `cartooner-command`, provider calls, asset
  events, and user decisions are normalized into Core Events.
- Current docs explicitly warn not to add new external AI orchestration backend,
  Python runtime service, Socket.IO server, old file browser, old workbench, or
  old project DB.

Therefore the minimal Cartooner multi-team split should follow product and
runtime boundaries, not legacy backend/frontend boundaries.

## Proposed Cartooner Minimal Topology

For Cartooner, the first useful minimal topology is:

```text
project-level memory
  Owns user intent, repo analysis, team topology proposal, acceptance strategy,
  and final memory retention.

team: product-ui
  Owns React UI surfaces, Vibe Canvas, chat, Tactical HUD, interaction state,
  visual regressions, and frontend tests.

team: desktop-runtime
  Owns Electron, Claude SDK control plane, provider bridge, asset/runtime paths,
  local project bridge, terminal/tmux bridge, and desktop acceptance.
```

Each team starts with only:

```text
planner + builder
```

This keeps the first template focused on proving the v3 protocol instead of
proving production-grade review coverage. Reviewer and patrol can be added in a
second-tier `MULTI_TEAM_ENGINEERING` template.

## Minimal Proposal Shape

The proposal pack should generate one `*__approved.yaml` per team after user
approval. A minimal team proposal looks like:

```yaml
---
project: <project>
team: product-ui
proposal_status: approved
operator_approved_ts: <iso8601>
seats:
  - role: planner
    tool: claude
    provider: anthropic
    auth_mode: oauth_token
    rationale: "claims this team's queue, writes workflow.md, dispatches team work"
  - role: builder
    tool: codex
    provider: openai
    auth_mode: oauth
    rationale: "implements planner-assigned changes and writes DELIVERY.md"
estimated_monthly_cost_usd:
  low: 0
  high: 20
---
```

The exact tool/provider defaults remain policy, not hard-coded truth. The skill
should explain the choice and let the operator approve or change it.

## Memory-Driven Team Designer Skill

The final implementation should become a skill, tentatively:

```text
core/skills/multi-team-intake/SKILL.md
```

Skill responsibilities:

1. Scan the target repo's current docs, package manifests, tests, and major
   directories.
2. Identify project archetype and module boundaries.
3. Recommend a team topology with phase-1 minimal teams and optional phase-2
   teams.
4. Explain why each team exists, which paths it owns, and which acceptance
   routes it needs.
5. Write proposed YAML files first, not approved YAML.
6. Ask the operator to approve or edit.
7. Convert proposals to `__approved.yaml` only after explicit approval.
8. Tell the operator the exact `install.sh --mode multi` dry-run command.

Important boundary: memory designs the project groups and writes briefs /
acceptance criteria. Planner claims team queues and authors workflow. Memory
does not write `workflow.md` and does not dispatch directly to builders.

## Memory To Planner Execution Trigger

For v3 multi-team, the agreed default is pull-first:

1. Memory writes a brief:

   ```bash
   python3 core/scripts/agent_admin.py brief queue \
     --project <p> --team <t> \
     --task-id <task_id> \
     --objective "<one-line objective>" \
     --seats-required builder
   ```

2. This writes:

   ```text
   ~/.agents/tasks/<project>/<team>/brief/<task_id>.md
   ~/.agents/tasks/<project>/<team>/tasks.queue.jsonl
   ```

3. Planner claims:

   ```bash
   python3 core/scripts/agent_admin.py brief claim \
     --project <p> --team <t> \
     --task-id <task_id> \
     --actor planner@claude
   ```

4. Planner writes:

   ```text
   ~/.agents/tasks/<project>/<team>/workflow/<task_id>.md
   ```

For the minimal template phase, do not default to a background 60-second claim
loop. A launchd poller that claims without waking the planner TUI can create a
confusing "claimed but not executing" state. Start with SessionStart/manual
claim, or add a wrapper that claims and wakes the correct planner pane.

## Cross-Team Dependency Rule

Use `depends_on` across teams only through durable queue state. A downstream
team task must remain `task_waiting_for` until the upstream task is `task_done`
in any sibling team queue.

Every task identity in discussion or compact summaries must include:

```text
project + team + task_id
```

Never refer to a bare task id in multi-team mode.

## Planner Compact Trigger

Planner must not emit `[CLEAR-REQUESTED]`. Planner keeps cross-step routing
state and must preserve that context through compact.

Planner asks memory to compact by appending this marker to its relay:

```text
[memory: compact-me]
```

Memory then:

1. Checks that planner durable state is written.
2. Preserves a compact summary with:
   - project
   - team
   - task_id
   - workflow path
   - queue state
   - owner map
   - blockers
   - handoff receipt paths
   - pending acceptance routes
3. Applies an idle gate: planner is not thinking/working and no active write is
   in progress.
4. Sends `/compact` through the standard transport:

   ```bash
   core/shell-scripts/send-and-verify.sh --project <project> <planner-seat> "/compact"
   ```

The compact summary must include `team`; otherwise planner recovery can mix
similarly named tasks across teams.

## Open Design Questions

1. Should the first generic minimal topology be fixed to two teams, or should
   memory always derive team count from repo analysis?
2. Should minimal builder default to `codex/oauth/openai` or to
   `claude/oauth_token/anthropic` for consistency with planner?
3. Should a safe claim-and-wakeup wrapper be added before enabling the
   60-second background planner poller by default?

