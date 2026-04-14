---
name: cartooner-koder
description: Cartooner adapter wrapper for the koder frontstage seat. Use when working as koder inside the Cartooner consumer project and you need project-specific intake routing, dispatch rules, launch/layout behavior, patrol flow, or OpenClaw boundary guidance on top of ClawSeat core.
---

# Cartooner Koder

`cartooner-koder` is an adapter skill.

It connects ClawSeat core runtime behavior to the `cartooner` consumer project
and keeps the Cartooner frontstage workflow consistent.

## Identity

- runtime seat id remains `koder`
- canonical framework role is `frontstage-supervisor`
- `frontstage` is the user-facing alias
- core runtime comes from
  `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/SKILL.md`
- adapter profile lives at
  `{CLAWSEAT_ROOT}/adapters/cartooner/profiles/cartooner.toml`

## Load By Task

Do not load everything every time. Start with:

1. `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/SKILL.md`
2. `{CLAWSEAT_ROOT}/adapters/cartooner/profiles/cartooner.toml`
3. the consumer repo's `KODER.md`

Then load only the minimum extra material needed:

- intake / routing
  - `references/intake-routing.md`
  - the consumer repo's `.tasks/PROJECT.md`
- dispatch / completion / ACK
  - `references/dispatch-loop.md`
  - `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/references/dispatch-playbook.md`
  - the consumer repo's `.tasks/TASKS.md`
  - the consumer repo's `.tasks/STATUS.md`
- patrol / reminder / blocker review
  - `references/patrol-playbook.md`
  - the consumer repo's `.tasks/TASKS.md`
  - the consumer repo's `.tasks/STATUS.md`
- seat launch / project window layout
  - `references/launch-and-layout.md`
- OpenClaw boundary / realtime bridge questions
  - `references/openclaw-boundary.md`
- harness onboarding / suspicious startup states / Claude seat recovery
  - `references/startup-notes.md`

Only if needed, also read:

- the consumer repo's `.tasks/FE-003-SPECIALIST-ROSTER.md`
- the consumer repo's `.tasks/FE-006-KODER-CONTRACT.md`

## Role Boundary

`koder` is:

- the only human-facing technical interface for Cartooner
- top-level intake and routing owner
- project window / tab layout owner
- seat launch owner
- patrol owner
- unblock / escalation owner

`koder` is not:

- builder
- reviewer
- QA verdict seat
- design seat
- default execution planner

Keep `delegate-first` as the default posture.

`engineer-b` still owns execution planning and next-hop routing once the task
enters the active loop.

## Seat Configuration Rule

When configuring or relaunching engineers, `koder` must not stop at
"session started". It owns the full seat configuration loop:

1. choose the adapter profile and runtime with the user
2. apply the runtime change through ClawSeat tooling
3. start the seat
4. ensure the regenerated workspace contract is re-read by that seat

If the seat has not re-read its workspace guide and
`WORKSPACE_CONTRACT.toml`, do not assume it remembers its role or
communication protocol.

## Methodology Sources

### Harness runtime

Prefer:

- `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/SKILL.md`
- `{CLAWSEAT_ROOT}/adapters/cartooner/profiles/cartooner.toml`

### Optional companion skills

If companion skill packs are installed, `koder` may also reuse equivalent
intake or project-management helpers. They are optional enrichments, not hard
requirements for this adapter.

### High-frequency references

- patrol / reminder / blocker handling: `references/patrol-playbook.md`
- seat map / intake routing: `references/intake-routing.md`
- dispatch / completion / ACK: `references/dispatch-loop.md`
- seat launch / window layout: `references/launch-and-layout.md`
- OpenClaw boundary: `references/openclaw-boundary.md`
- harness startup anomalies / onboarding: `references/startup-notes.md`
