# Koder Hygiene — Consume ACK Rules

Autonomous chain mode: planner drives each Phase-2 track end-to-end. Koder acts as routing + final mission-level summary only.

## Rule 1 — AUTO_ADVANCE

When a planner closeout arrives with `frontstage_disposition: AUTO_ADVANCE`:

- **Immediately run** the consume ACK to prune your own TODO entry.
- No user notification required.
- No Feishu broadcast.

```bash
python3 <HARNESS_SCRIPTS>/complete_handoff.py \
  --profile <PROFILE> \
  --source planner \
  --target koder \
  --task-id <TASK_ID> \
  --ack-only
```

## Rule 2 — USER_DECISION_NEEDED

When a planner closeout arrives with `frontstage_disposition: USER_DECISION_NEEDED`:

- **Do NOT** auto-ack. Retain the TODO entry.
- Relay the `user_summary` to the user in plain language.
- Wait for explicit user instruction before proceeding.

## Rule 3 — CHANGES_REQUESTED (unexpected)

This disposition should not appear in the planner→koder path (planner handles fix1 chains internally). If it does appear:

- Treat identically to USER_DECISION_NEEDED.
- Relay the `user_summary` and wait.

## Rationale

Autonomous chain mode means planner no longer sends a per-track status message to koder for every builder/reviewer/qa handoff. Koder only acts when the full chain is resolved and planner pushes a final closeout. AUTO_ADVANCE closeouts require no human judgment — just prune and move on.
