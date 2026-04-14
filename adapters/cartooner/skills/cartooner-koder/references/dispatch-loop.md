# Dispatch Loop

Top-level dispatch follows this order:

1. update the target seat's `TODO.md`
2. update `TASKS.md`
3. update `STATUS.md`
4. send a transport reminder so the target seat reads the durable docs

Preferred transport paths:

- `{CLAWSEAT_ROOT}/.scripts/send-and-verify.sh`
- `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/scripts/notify_seat.py`

Rules:

- durable docs are the source of truth
- tmux is only a reminder layer
- do not replace docs with chat text
- `send-and-verify.sh` is the default transport path
- in multi-project environments, do not use a bare seat name such as
  `engineer-b`
- prefer the canonical session name, for example `cartooner-engineer-b-claude`
- otherwise pass `--project cartooner`
- for frontstage unblock / reminder messages, `notify_seat.py` is preferred
- raw `tmux send-keys` is protocol drift
- fallback is only allowed if the main transport is unavailable
- fallback must still honor the transport contract: send text, wait one
  second, send `Enter`, verify the message did not remain queued

Completion back to `engineer-b` is also document-first:

1. specialist updates `DELIVERY.md`
2. specialist notifies `engineer-b` with
   `{CLAWSEAT_ROOT}/.scripts/send-and-verify.sh`
3. `engineer-b` writes a durable `Consumed:` ACK in the consumer repo's
   `.tasks/engineer-b/TODO.md`

Do not treat pane noise as proof that a completion handoff was consumed.

Protocol helpers:

- `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/scripts/dispatch_task.py`
- `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/scripts/complete_handoff.py`
- `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/scripts/verify_handoff.py`
- `{CLAWSEAT_ROOT}/.agents/skills/gstack-harness/references/dispatch-playbook.md`

Low-freedom defaults:

- `koder -> engineer-b` uses `dispatch_task.py`
- `engineer-b -> specialist` uses `dispatch_task.py`
- `specialist -> engineer-b` uses `complete_handoff.py`
- `engineer-b -> koder` uses `complete_handoff.py`
