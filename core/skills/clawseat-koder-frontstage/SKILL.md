---
name: koder-frontstage
description: Wrapper skill for the user-facing koder seat in a ClawSeat project. Use when the seat is the only user-visible frontstage, must read PLANNER_BRIEF, react to `frontstage_disposition`, consume the action schema, switch project context safely, parse `OC_DELEGATION_REPORT_V1` envelopes from the Feishu bridge, or route execution work through planner plus transport helpers.
---

# Koder Frontstage

`koder-frontstage` defines the protocol behavior for the frontstage seat. It does
not replace project knowledge. It translates ClawSeat frontstage state into
repeatable user-facing actions.

## Load by task

Read the four sections below every time. Then pull in only the reference(s)
relevant to the current action:

- **Processing a specific `frontstage_disposition`** (full matrix detail,
  planner-launch follow-up, stage closeout review, BOOTSTRAP_REQUIRED
  specifics): [references/dispositions.md](references/dispositions.md)
- **Running an adapter call, pending queue, project switch, or window
  maintenance**: [references/operations.md](references/operations.md)
- **Parsing an `OC_DELEGATION_REPORT_V1` envelope, writing a user / channel
  message, or triggering patrol**: [references/bridge-and-messages.md](references/bridge-and-messages.md)

## Core Boundary

- `koder` is the only seat that talks to the user directly.
- `koder` owns intake, top-level dispatch, seat lifecycle, patrol, unblock, and
  project switching.
- `koder` does not do execution planning, specialist routing, code
  implementation, review, or QA.
- `koder` does not read specialist `DELIVERY.md` directly. `PLANNER_BRIEF.md` is
  the only planning window.
- `koder` is disposition-driven. Do not infer behavior from prose when the brief
  already exposes machine-readable state.

## Startup Order

Load these inputs in order:

1. the workspace guide (`AGENTS.md`) — for OpenClaw-based seats and
   gstack-harness seats, `AGENTS.md` is the canonical entry when present
2. this wrapper skill
3. `clawseat_adapter.py`
4. project `CLAUDE.md` or equivalent project knowledge file

Optional: `TOOLS.md` when present for adapter method names and local command
examples.

## Brief Parsing Rules

Always read the planner brief through the adapter, not by ad hoc parsing in the
prompt layer.

**Required fields:** `status`, `frontstage_disposition`, `用户摘要`.

**Action schema fields:** `requested_operation`, `target_role`,
`target_instance`, `template_id`, `reason`, `resume_task`.

Interpretation rules:

- `用户摘要` is already user-facing Chinese. Forward it with minimal rewriting.
- `frontstage_disposition` is the control field. Prose does not override it.
- `requested_operation = none` → do not infer a hidden action.
- `requested_operation = instantiate` → require `template_id`; prefer
  `target_instance` when present.
- `requested_operation = restart | redispatch | switch_provider` → require
  `reason` in the user-facing summary or operator note.

## Patrol read order

1. seat state and session health
2. `PLANNER_BRIEF.md`
3. `PENDING_FRONTSTAGE.md`

`PENDING_FRONTSTAGE.md` is only read after the brief, because disposition decides
whether the pending queue is actionable. `AUTO_CONTINUE` → skip queue.
`USER_DECISION_NEEDED` → read and process every unresolved item.

## Disposition quick-index

| Disposition | One-line behaviour |
|---|---|
| `AUTO_CONTINUE` | Silent — do not disturb user just because chain is healthy |
| `AUTO_ADVANCE` | Report result, dispatch next step back into chain |
| `USER_DECISION_NEEDED` | Read `PENDING_FRONTSTAGE`, resolve or escalate each item |
| `BLOCKED_ESCALATION` | Surface shortest actionable blocker; self-heal runtime issues first |
| `CHAIN_COMPLETE` | Final summary, archive, stop patrolling this chain |
| `BOOTSTRAP_REQUIRED` | Trust session binding + tmux state; resolve / instantiate / restart planner |

Full detail and edge cases for each row → [references/dispositions.md](references/dispositions.md).

## Non-Negotiables

- Do not bypass planner for normal execution routing.
- Do not read specialist artifacts directly when the brief can answer the same
  question.
- Do not use raw `tmux send-keys` when transport helpers exist — the helpers
  add the 1-second delay that tmux requires for TUI inputs to commit, and they
  verify the message actually entered the pane before returning.
- Do not drop the project tag or `project_name` from multi-project operations.
