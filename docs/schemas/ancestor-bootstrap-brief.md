# Ancestor Bootstrap Brief — Schema v0.1

> **Status**: Legacy reference for `core/tui/ancestor_brief.py`, not the v0.7
> install SSOT.
> **Consumer**: ancestor seat (via `clawseat-ancestor` skill)
> **Producer**: historical `core/tui/ancestor_brief.py` renderer. The current
> v0.7 install path renders `core/templates/ancestor-brief.template.md` from
> `scripts/install.sh`.
> **Format**: Markdown with a leading fenced YAML metadata block so both
> humans and the ancestor skill can parse deterministically.
> **Location**: `~/.agents/tasks/<project>/patrol/handoffs/ancestor-bootstrap.md`

When this file conflicts with [`docs/INSTALL.md`](../INSTALL.md),
[`core/skills/clawseat-ancestor/SKILL.md`](../../core/skills/clawseat-ancestor/SKILL.md),
or [`core/templates/ancestor-brief.template.md`](../../core/templates/ancestor-brief.template.md),
the v0.7 install playbook and current template win. Some examples below retain
pre-v0.7 assumptions for legacy renderer coverage and historical context.

## Why a brief

The ancestor boots into an empty state. It needs a deterministic, file-based
handoff that tells it:

- which project it belongs to
- where the profile + machine config live
- which seats it should launch
- who the OpenClaw tenant is
- which Feishu targets are in play
- what phase the project is in

File-based (not `tmux send-keys`) because:

1. Idempotent. Ancestor can re-read on crash-recovery without replaying
   keystrokes that may have been truncated or applied mid-prompt.
2. Reviewable. Operators can inspect what the ancestor saw.
3. Diffable. Bootstrap runs across time compared via `git diff`.

## Envelope

A v0.1 brief is a single Markdown file starting with a YAML front-matter
block delimited by `---` lines, followed by human-readable sections.

```
---
brief_schema: ancestor-bootstrap
brief_schema_version: 0.1
brief_generated_at: 2026-04-21T22:45:00+08:00
brief_generator: core/tui/ancestor_brief.py

project: install
profile_path: ~/.agents/profiles/install-profile-dynamic.toml
profile_version: 2
machine_config_path: ~/ClawSeat/machine.toml    # null if missing
openclaw_tenant: yu
openclaw_tenant_workspace: ~/.openclaw/workspace-yu
feishu_group_binding: null    # PROJECT_BINDING.toml not yet written

seats_declared:
  - role: ancestor
    sessions: [install-ancestor-claude]
    tool: claude
    auth_mode: oauth_token
    provider: anthropic
    state: alive         # ancestor is already up (that's us)
  - role: planner
    sessions: [install-planner-claude]
    tool: claude
    auth_mode: oauth_token
    provider: anthropic
    state: pending
  - role: builder
    sessions: [install-builder-1-claude]   # parallel_instances=1 expanded
    tool: claude
    auth_mode: oauth_token
    provider: anthropic
    parallel_instances: 1
    state: pending
  - role: reviewer
    sessions: [install-reviewer-1-codex, install-reviewer-2-codex]  # parallel_instances=2 expanded
    tool: codex
    auth_mode: api
    provider: xcode-best
    parallel_instances: 2
    state: pending
  # ... one entry per profile.seats[]

machine_services_required:
  - memory

checklist_phase_a:
  - B1-read-brief
  - B2-verify-or-launch-memory
  - B3-verify-openclaw-binding
  - B4-launch-pending-seats
  - B5-verify-feishu-group-binding
  - B6-smoke-dispatch
  - B7-write-status-ready

checklist_phase_b_cadence_minutes: 30

observability:
  feishu_events_whitelist:
    - task.completed
    - chain.closeout
    - seat.blocked_on_modal
    - seat.context_near_limit
  feishu_sender_seat: ancestor
  feishu_lark_cli_identity: planner    # shared OAuth per 2026-04-21 Q2=a

clawseat_root: /Users/ywf/ClawSeat
---

# Ancestor bootstrap brief — <project>

... human-readable narrative follows ...
```

## Field reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `brief_schema` | string | yes | always `"ancestor-bootstrap"` |
| `brief_schema_version` | string | yes | semver; breaking changes bump major |
| `brief_generated_at` | ISO-8601 timestamp w/ offset | yes | UTC+08 in practice |
| `brief_generator` | string | yes | human-readable producer id |
| `project` | string | yes | matches `profile.project_name` |
| `profile_path` | path string (may start `~`) | yes | absolute or tilde-prefixed |
| `profile_version` | int | yes | must equal 2 for v0.4 |
| `machine_config_path` | path string or null | yes | null → ancestor must alert and DO NOT auto-create |
| `openclaw_tenant` | string | yes | matches `profile.openclaw_frontstage_agent` |
| `openclaw_tenant_workspace` | path string | yes | tenant's WORKSPACE_CONTRACT.toml parent |
| `feishu_group_binding` | string or null | yes | PROJECT_BINDING.toml path; null → Phase A B5 must run |
| `seats_declared` | list of seat objects | yes | includes ancestor (with state=alive); other roles state=pending or alive if already spawned |
| `seats_declared[].role` | enum | yes | one of v0.4 LEGAL_SEAT_ROLES |
| `seats_declared[].sessions` | list of strings | yes | tmux session names (exact, for `tmux has-session -t '='`). One entry for singleton roles; `parallel_instances` entries for fan-out roles (builder/reviewer/qa). Suffix convention: `<project>-<role>-<N>-<tool>`. |
| `seats_declared[].tool` | enum | yes | from profile.seat_overrides |
| `seats_declared[].auth_mode` | enum | yes | same |
| `seats_declared[].provider` | string | yes | same |
| `seats_declared[].parallel_instances` | int or absent | no | present only for builder/reviewer/qa |
| `seats_declared[].state` | enum | yes | `alive` \| `pending` \| `dead` |
| `machine_services_required` | list of strings | yes | must appear in machine.toml.services |
| `checklist_phase_a` | list of strings | yes | stable ordered tokens; ancestor crosses them off |
| `checklist_phase_b_cadence_minutes` | int | yes | patrol interval |
| `observability.feishu_events_whitelist` | list of enum strings | yes | mirrors profile.observability.announce_event_types |
| `observability.feishu_sender_seat` | string | yes | always `"ancestor"` |
| `observability.feishu_lark_cli_identity` | enum | yes | `"planner"` per current decision; future values may widen |
| `clawseat_root` | absolute path | yes | `{CLAWSEAT_ROOT}` expanded |

## Phase-A checklist token semantics

The `checklist_phase_a` list is the ancestor skill's ordered step plan.
Each token has a fixed contract.

| Token | Meaning | Success signal | Failure handling |
|-------|---------|----------------|------------------|
| `B1-read-brief` | Parse this file | YAML block parses cleanly | Abort with operator alert |
| `B2-verify-or-launch-memory` | `tmux has-session -t 'machine-memory-claude'`; if you need exact-target syntax use `tmux has-session -t '=machine-memory-claude'` (quoted). If absent, call `agent-launcher.sh --headless --session machine-memory-claude` using `machine.toml.services.memory` overrides; re-verify | rc=0 after (up to) one launch attempt | Feishu alert, continue (see 6.3 in responsibilities); do **not** halt Phase-A |
| `B3-verify-openclaw-binding` | Read tenant WORKSPACE_CONTRACT.toml, assert `.project == <project>` | match | Feishu alert, halt Phase A |
| `B4-launch-pending-seats` | For each seat with `state=pending`, iterate `sessions[]` and call `agent-launcher.sh --headless --session <session>` per instance | every session transitions to alive within 30s | Retry once per session; then mark that instance `state=dead`, include in status |
| `B5-verify-feishu-group-binding` | Read `~/.agents/tasks/<project>/PROJECT_BINDING.toml.feishu_group_id`; confirm non-empty | file exists + group id present | Halt Phase-A; stderr + Feishu (if any earlier binding) alert: "launcher must have written PROJECT_BINDING.toml.feishu_group_id before spawning ancestor; rerun installer" |
| `B6-smoke-dispatch` | Send `OC_DELEGATION_REPORT_V1` report type=`smoke` to group | message delivered | Retry 3×, then mark B6 failed in STATUS.md; proceed (not hard-fail) |
| `B7-write-status-ready` | Write `~/.agents/tasks/<project>/STATUS.md` with `phase=ready`, then enter Phase-B (no operator ack gate) | file present | hard failure (disk issue) |

**Note**: B8 (await-operator-ack) was removed in v0.1. Rationale: the install
playbook already surfaces runtime selection and binding inputs before ancestor
is launched; a second "ack before patrol" gate provides no additional
information. Phase-B patrol is benign (read-only observation +
restart-dead-seats) so unconditionally entering it after B7 is safe.

## Phase-B patrol semantics

Phase B is triggered by **external `launchd` plist** (template at
`core/templates/ancestor-patrol.plist.in`, installed by the launcher).
Every `checklist_phase_b_cadence_minutes` minutes, the plist runs
`tmux send-keys -t '=<project>-ancestor-claude' "/patrol-tick" Enter` —
ancestor skill recognizes the `/patrol-tick` marker and executes
P1..P7 from the responsibility matrix §3.2 in that one turn. Phase B
runs until the project is archived (ancestor never retires on its own).

Ancestor does NOT run an in-process `sleep`-loop; patrol cadence is
owned by the OS scheduler.

## Idempotency requirements

Ancestor may re-read the brief on crash-recovery. Before executing any
B-step, it checks whether the step was already done:

- `B2`: re-verify memory each time (it's cheap)
- `B3`: re-verify binding each time
- `B4`: skip sessions whose `tmux has-session` reports alive; iterate per-instance for fan-out roles
- `B5`: re-verify (cheap read)
- `B6`: skip if `STATUS.md` shows any previous `smoke=ok` entry
- `B7`: re-write is safe (overwrite semantics)

Never mutate this brief file. Progress is tracked in STATUS.md + the
ancestor seat's own workspace journal, NOT by rewriting the brief.

## Versioning policy

- `0.x` = TUI-engineer-provisional, subject to architect veto
- `1.0` = architect sign-off, stable through all v0.4.x ClawSeat releases
- `2.0` = only bumped when a seat-role change invalidates existing briefs;
  ancestor skill must then support both schemas for one release cycle

## Architect decisions (2026-04-21, closed)

- Brief format: YAML front-matter + Markdown body — **APPROVED**.
- `seats_declared[].state` enum: `alive | pending | dead` (no `dying`) — **APPROVED**.
- B0-preflight: **not added**; B1 implicitly parses the YAML block.
- Feishu identity: uses planner's lark-cli OAuth + `sender_seat: ancestor` header; no separate audit log in v0.1.
- B8 (await-operator-ack): **removed**; see note in Phase-A checklist above.
- `seats_declared[].session` → `sessions: list[str]`: fan-out roles expand to one entry per instance (§N-2).
- B2 semantics: verify-**or**-launch memory; ancestor owns machine-service launch (§B2 revision).
- B5 semantics: verify PROJECT_BINDING.toml.feishu_group_id already written by the launcher (§B5 revision); ancestor does NOT prompt operator (would violate N1 in responsibilities.md).
- Phase-B trigger: external `launchd` plist injects `/patrol-tick` via `tmux send-keys` (SKILL.md §8 Q3 closed).

## Residual open questions (deferred to v0.2)

1. Is `feishu_lark_cli_identity: planner` the right shared identity, or
   should we open a distinct `ancestor` OAuth before v1.0?
2. Should `seats_declared[].state` track `dying` as well as `dead` for
   mid-shutdown observability? (currently closed; re-open if ops needs it)
