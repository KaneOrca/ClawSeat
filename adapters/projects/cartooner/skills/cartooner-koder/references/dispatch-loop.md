# Dispatch Loop

Top-level dispatch follows this order:

1. update the target seat's `TODO.md`
2. update `TASKS.md`
3. update `STATUS.md`
4. send a transport reminder so the target seat reads the durable docs

Preferred transport paths:

- `{CLAWSEAT_ROOT}/core/shell-scripts/send-and-verify.sh`
- `{CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/notify_seat.py`

Rules:

- durable docs are the source of truth
- tmux is only a reminder layer
- do not replace docs with chat text
- `send-and-verify.sh` is the default transport path
- in multi-project environments, do not use a bare seat name such as
  `planner`
- prefer the canonical session name, for example `cartooner-planner-claude`
- otherwise pass `--project cartooner`
- for frontstage unblock / reminder messages, `notify_seat.py` is preferred
- raw `tmux send-keys` is protocol drift
- fallback is only allowed if the main transport is unavailable
- fallback must still honor the transport contract: send text, wait one
  second, send `Enter`, verify the message did not remain queued

Completion back to `planner` is also document-first:

1. specialist updates `DELIVERY.md`
2. specialist notifies `planner` with
   `{CLAWSEAT_ROOT}/core/shell-scripts/send-and-verify.sh`
3. `planner` writes a durable `Consumed:` ACK in the consumer repo's
   `.tasks/planner/TODO.md`

Do not treat pane noise as proof that a completion handoff was consumed.

Protocol helpers:

- `{CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/dispatch_task.py`
- `{CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/complete_handoff.py`
- `{CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/verify_handoff.py`
- `{CLAWSEAT_ROOT}/core/skills/gstack-harness/references/dispatch-playbook.md`

Low-freedom defaults:

- `koder -> planner` uses `dispatch_task.py`
- `planner -> specialist` uses `dispatch_task.py`
- `specialist -> planner` uses `complete_handoff.py`
- `planner -> koder` uses `complete_handoff.py`
