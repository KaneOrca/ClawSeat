# Chain Protocol

Default chain shape:

- `user -> frontstage -> planner -> specialist -> planner -> ... -> frontstage -> user`

One common project mapping is:

- `user -> koder -> engineer-b -> specialist -> engineer-b -> ... -> koder -> user`

## Dispatch protocol

1. write target `TODO`
   - target `TODO.md` must include:
     - `task_id`
     - `source`
     - `reply_to`
   - use `scripts/dispatch_task.py` as the default dispatch path instead of
     hand-writing `TODO.md`, `TASKS.md`, or `STATUS.md`
2. update project task/state docs
3. notify via `send-and-verify`
   - the notification text should explicitly include:
     - who dispatched the task
     - who the target seat is
     - who the target seat should reply to when complete
   - in a multi-project setup, never resolve a bare seat id with
     `agentctl.sh session-name engineer-b`
   - use either the canonical tmux session name directly, or pass
     `--project <project>` to the transport helper
   - prefer `scripts/notify_seat.py`
     for ad hoc reminders or unblock notices that are not full dispatches
   - this is the default transport; do not use raw `tmux send-keys` unless the
     transport script is unavailable
   - if a fallback is unavoidable, replicate the transport contract:
     - send the text
     - wait 1 second
     - send `Enter`
     - verify the message is not stranded in the input buffer
4. write a handoff receipt

Default policy:

- frontstage -> planner dispatch should normally go through
  `scripts/dispatch_task.py`
- planner -> specialist dispatch should normally go through
  `scripts/dispatch_task.py`
- if the helper is unavailable and a fallback is unavoidable, the operator
  must still leave all four artifacts:
  - `TODO.md` with `source` and `reply_to`
  - `TASKS.md` update
  - `STATUS.md` update
  - machine-readable dispatch receipt

## Seat launch protocol

Before frontstage starts any non-frontstage seat, it must first summarize to
the user:

- which harness/profile will be used
- which seat/role is being launched
- which tool/runtime will be used
- which auth mode and provider/model family will be used

Only after the user confirms may frontstage actually launch the seat.

## Completion protocol

1. specialist writes `DELIVERY`
   - `DELIVERY.md` must include:
     - `task_id`
     - `owner`
     - `target`
2. specialist notifies planner
   - the notification text should explicitly include:
     - who completed the task
     - who should consume it
   - in a multi-project setup, the transport must resolve the target seat with
     an explicit project or canonical session name
   - use the same `send-and-verify` transport rule as dispatch
3. planner writes durable `Consumed:` ACK
4. planner decides the next hop

## Planner -> frontstage closeout

When the active loop owner returns a chain result to frontstage:

1. planner uses `scripts/complete_handoff.py` as the default closeout path
   - do not hand-roll a planner closeout with ad hoc file edits unless the
     helper is unavailable
2. planner writes `DELIVERY`
   - `DELIVERY.md` must include:
     - `task_id`
     - `owner`
     - `target`
     - `FrontstageDisposition: AUTO_ADVANCE | USER_DECISION_NEEDED`
     - `UserSummary: ...` in short plain language
   - if `FrontstageDisposition: USER_DECISION_NEEDED`, also include:
     - `NextAction: ...`
3. planner notifies frontstage using the same `send-and-verify` transport rule
4. planner writes a machine-readable handoff receipt
5. planner refreshes the frontstage inbox
   - write the current frontstage `TODO.md` so koder/frontstage has a durable
     current-task anchor even if the live TUI compacts or restarts
   - the frontstage inbox item should carry:
     - `task_id`
     - `source`
     - `reply_to`
     - `FrontstageDisposition`
     - `UserSummary`
6. frontstage reads the planner receipt and:
   - gives the user a short, easy-to-understand summary
   - auto-advances by default when the disposition is `AUTO_ADVANCE`
   - asks the user to decide only when the disposition is `USER_DECISION_NEEDED`

Default policy:

- planner auto-advances most of the time
- planning memos and execution plans should also default to `AUTO_ADVANCE`
  once the current scope is already accepted; do not wait for a second
  frontstage approval unless the task spec or the user explicitly created a
  plan gate
- escalate to the user only for genuine product, scope, risk, seat, or model/auth choices

## Handoff state machine

- `assigned`
- `notified`
- `consumed`

Only `assigned + notified + consumed` counts as healthy.

## Generic reminders / unblock notices

- frontstage or planner should use `scripts/notify_seat.py`
  for one-off notices instead of raw tmux
- if the notice is tied to a task, include `--task-id` so the transport leaves
  a receipt

## Review canonical verdicts

- `APPROVED`
- `APPROVED_WITH_NITS`
- `CHANGES_REQUESTED`
- `BLOCKED`
- `DECISION_NEEDED`

Review outputs must carry a canonical `Verdict:` field so the planner does not
have to infer routing from prose.
