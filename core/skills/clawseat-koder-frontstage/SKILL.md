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

## Risk-based autonomous routing

Koder no longer blind-trusts `frontstage_disposition`. On every planner
closeout, koder performs an independent risk assessment and holds final
routing authority. The planner's disposition is a strong signal and audit
input — not an unconditional execute order.

### Ultra-high risk whitelist (koder must escalate regardless of disposition)

Any closeout whose `summary`, `diff`, or `next_action` matches an entry
below is classified ultra-high risk. Koder escalates to the operator and
does **not** auto-advance, even if `frontstage_disposition: AUTO_ADVANCE`.

**Code / repository**

- `git push --force` / `git push -f` / any force push to `main`, `master`,
  `release/*`
- `git reset --hard`
- `git branch -D` on an unmerged branch
- PR creation, merge, or close via API
- Merging into `main` / `master` / `production` / `release` branches
- `rm -rf` on non-scratch directories
- Commit containing `.env`, credentials, or private keys

**Infrastructure / seat lifecycle**

- Any invocation of `start_seat.py` / `launch_ancestor.sh` /
  `agent-launcher.sh` / `install.sh` without `--dry-run`
- Modification of `PROJECT_BINDING.toml` / `machine.toml` / `profile.toml`
- Deletion of a workspace or project record
- `tmux kill-session` or `tmux rename-session` on a live seat

**External services / accounts**

- Write operations to external services (Slack, email, webhook, third-party
  API sends)
- Credential addition, rotation, or export of OAuth tokens / API keys
- Feishu group membership addition, removal, or permission change
- Package publishing (`npm publish`, `pip upload`, container image push)

**Data / financial**

- Database migration `apply` (generation phase is not covered)
- Any decision involving monetary amounts, account identifiers, or private
  personal data fields

**Semantic (koder self-judges)**

- User-taste / preference A/B options that are functionally equivalent from
  an engineering standpoint
- Repeat of a class of issue the operator has explicitly reversed or
  flagged in recent history

### Bidirectional override flow

```
planner closeout received
  │
  ├─ read summary + diff + next_action
  │
  ├─ WHITELIST MATCH or koder judges ultra-high?
  │     YES → escalate to operator (regardless of disposition)
  │           write state.db: planner_disposition=<X>, koder_risk_level=ultra,
  │                           koder_decision=escalate, notified_at=<ts>
  │           stop; do not auto-advance
  │
  ├─ No whitelist match; koder judges medium risk?
  │     YES → self-decide + send Feishu message:
  │           「我替你决了：<action in one sentence>。
  │             原因：<one line>。
  │             原 planner disposition: <frontstage_disposition>」
  │           write state.db: planner_disposition=<X>, koder_risk_level=medium,
  │                           koder_decision=<action>, notified_at=<ts>
  │           proceed with decided action
  │
  └─ koder judges low risk?
        YES → silent prune (consume ACK only)
              write state.db: planner_disposition=<X>, koder_risk_level=low,
                              koder_decision=auto_advance, notified_at=null
```

### Key invariants

1. **Planner still emits `frontstage_disposition`** — it remains the primary
   signal and provides the audit trail for every closeout.
2. **Koder has final routing authority** — koder's risk judgment overrides
   planner's disposition in both directions (escalate up or self-decide down).
3. **All overrides are traceable** — `state.db` records both
   `planner_disposition` and `koder_decision` on every non-trivial routing
   event.
4. **Whitelist is exhaustive by category, not by substring** — koder applies
   semantic judgment within each category; the list is illustrative, not
   regex-matched.
