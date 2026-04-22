---
name: koder-frontstage
description: Optional Feishu reverse-channel adapter for the user-facing koder seat. Use only when the project explicitly enables the Feishu overlay; otherwise koder stays off the critical path and follows the CLI/state.db route.
---

# Koder Frontstage

`koder-frontstage` defines the optional user-facing adapter for a ClawSeat
project. It does not own the project critical path.

## Core Boundary (v0.7, 2026-04-22)

- `koder` is optional. If the Feishu overlay is disabled, it is not the control
  plane.
- Project identity comes from `CURRENT_PROJECT`, active CLI context, and
  adapter resolution, not from `chat_id`. Treat `chat_id` as transport
  metadata only.
- `koder` reads `PLANNER_BRIEF.md` through the adapter. The primary inputs are
  `status`, `frontstage_disposition`, and `用户摘要`.
- `koder` does not own seat lifecycle, project bootstrap, or workspace
  mutation. The lifecycle critical path is `operator -> ancestor` via CLI.
- New projects are created with `agent_admin project bootstrap` /
  `agent_admin project use`, not from Feishu intake.
- `koder` does not dispatch specialists directly unless the active adapter path
  exposes an internal next hop for the current chain.

## Overlay Mode

Only when the project explicitly enables the Feishu overlay:

- Parse `OC_DELEGATION_REPORT_V1` as a machine receipt, not as sender persona.
- Validate `project`, `task_id`, and `dispatch_nonce` against the active
  chain.
- Use `report_status`, `decision_hint`, `user_gate`, and `summary` for user
  synthesis.
- Treat `next_action` as an optional internal koder path only. Do not assume it
  is a universal external routing directive.
- For safe closeout receipts, koder may surface the summary and follow the next
  hop internally if it stays inside the active project and chain.
- For `needs_decision`, ask the user the short question from the receipt
  instead of auto-advancing.

If the overlay is off:

- ignore Feishu control packets as routing authority
- use `state.db` / CLI receipts as the durable source of truth
- do not infer planner intent from sender identity

## Lifecycle Route

Lifecycle requests always go through the operator and ancestor CLI path:

1. operator decides a lifecycle or install/reconfigure action is needed
2. operator invokes ancestor via CLI
3. ancestor performs the mutation
4. if koder overlay is active, it only mirrors the status/result back outward

Do not call launcher or window-creation commands from this skill layer.

## Patrol and Heartbeat

- Use `PLANNER_BRIEF.md` for patrol decisions.
- Respect `frontstage_disposition` exactly.
- `AUTO_CONTINUE` means no user interruption.
- `AUTO_ADVANCE` means surface the result and only continue if the current
  chain has a safe next hop.
- `USER_DECISION_NEEDED` means ask the user only for the decision that the
  brief or receipt requires.
- `BLOCKED_ESCALATION` means surface the blocker briefly and preserve
  `task_id`.
- `CHAIN_COMPLETE` means summarize and stop.

Heartbeat handling depends on overlay mode:

- overlay on: post `HEARTBEAT_ACK` to Feishu only after confirming state is
  clean
- overlay off: write the ack through `state.db` / CLI receipt path instead of
  Feishu
- drift always stays visible to the operator path; do not block the patrol loop
