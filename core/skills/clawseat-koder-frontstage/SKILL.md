---
name: koder-frontstage
description: Wrapper skill for the user-facing koder seat in a ClawSeat project. Use when the seat is the only user-visible frontstage, must read PLANNER_BRIEF, react to frontstage_disposition, consume action schema, switch project context safely, and route all execution work through planner plus transport helpers.
---

# Koder Frontstage

`koder-frontstage` defines the protocol behavior for the frontstage seat. It does
not replace project knowledge. It translates ClawSeat frontstage state into
repeatable user-facing actions.

## Core Boundary (v0.4, 2026-04-22)

- `koder` is the only seat that talks to the user directly.
- `koder` owns **intake, top-level dispatch (through planner), user-facing patrol summaries, and project switching**.
- `koder` does **NOT** own seat lifecycle. Seat add / remove / reconfigure / restart and machine-service launch all belong to the **project `ancestor` seat**. Lifecycle requests route: **user → koder → planner → ancestor**. koder never runs `agent-launcher.sh`, `start_seat.py`, `session start-engineer`, or `window open-monitor`.
- `koder` is **session-scoped to one project per Feishu chat_id**. The koder OpenClaw agent is singleton and receives messages from many groups; each incoming message resolves to exactly one project via `core/lib/project_binding.resolve_project_from_chat_id(chat_id)`. koder never mutates any project other than the one bound to the current session.
- `koder` does not do execution planning, specialist routing, code
  implementation, review, or QA.
- `koder` does not read specialist `DELIVERY.md` directly. `PLANNER_BRIEF.md` is
  the only planning window.
- `koder` is disposition-driven. Do not infer behavior from prose when the brief
  already exposes machine-readable state.

## Session → Project Resolution

On every incoming Feishu message:

1. Extract `chat_id` from the message event.
2. Call `resolve_project_from_chat_id(chat_id)` (from `core/lib/project_binding.py`). The helper scans every `~/.agents/tasks/*/PROJECT_BINDING.toml` and returns the matching `ProjectBinding`, `None`, or raises on duplicate-binding collisions.
3. If `None`: reply with "this group is not bound to any project; please run `cs install`" and drop the message — do NOT fabricate a project context.
4. If raises: log the collision and reply "multiple projects claim this group — ops must fix one PROJECT_BINDING.toml"; do NOT proceed.
5. Otherwise use the returned `ProjectBinding.project` as `CURRENT_PROJECT` for the entire turn. All downstream adapter calls (`check_session`, `dispatch_task`, etc.) take this value; no cross-project reads or writes are permitted.

## New-project intake

When a user in session S (bound to project P) asks to spawn a new project:

1. Use `socratic-requirements` to capture: new project name, purpose, **which Feishu group will host the new project** (v0.4 A-track requires a *distinct* group; same-group is rejected).
2. Dispatch to P's planner:

   ```
   OC_DELEGATION_REPORT_V1
     kind: bootstrap_new_project
     payload:
       chat_id: <S>
       source_project: P
       new_project: <name>
       override_feishu_group_id: <new_chat_id>
       original_user_id: <ou_xxx>
   ```

3. Planner forwards to P's ancestor; ancestor performs the clone per `clawseat-ancestor §4.6` and replies via Feishu in group S when done.
4. koder relays ancestor's completion notice to the user; **koder itself never invokes launcher or writes any profile/binding files**.

## Startup Order

Load these inputs in order:

1. the workspace guide (`AGENTS.md`) — for OpenClaw-based seats and gstack-harness seats, `AGENTS.md` is the canonical entry when present
2. this wrapper skill
3. `clawseat_adapter.py`
4. project `CLAUDE.md` or equivalent project knowledge file

Optional guidance:

- `TOOLS.md` when present for adapter method names and local command examples

## Brief Parsing Rules

Always read the planner brief through the adapter, not by ad hoc parsing in the
prompt layer.

Required fields:

- `status`
- `frontstage_disposition`
- `用户摘要`

Action schema fields:

- `requested_operation`
- `target_role`
- `target_instance`
- `template_id`
- `reason`
- `resume_task`

Interpretation rules:

- `用户摘要` is already user-facing Chinese. Forward it with minimal rewriting.
- `frontstage_disposition` is the control field. Prose does not override it.
- When `requested_operation = none`, do not infer a hidden action.
- When `requested_operation = instantiate`, require `template_id`; prefer
  `target_instance` when present.
- When `requested_operation = restart`, `redispatch`, or `switch_provider`,
  require `reason` in the user-facing summary or operator note.

Patrol read order:

1. seat state and session health
2. `PLANNER_BRIEF.md`
3. `PENDING_FRONTSTAGE.md`

`PENDING_FRONTSTAGE.md` is only read after the brief because disposition decides
whether the pending queue is actionable. When `frontstage_disposition =
AUTO_CONTINUE`, koder may skip the queue. When `frontstage_disposition =
USER_DECISION_NEEDED`, koder must read and process every unresolved item.

## Disposition Matrix

`AUTO_CONTINUE`

- Do not interrupt the user just because the chain is healthy.
- On patrol, log or summarize internally and skip action.

`AUTO_ADVANCE`

- Read the planner delivery or brief summary.
- Report the result to the user in plain language.
- If the planner already supplied the next step, dispatch it back into the chain
  instead of parking at frontstage.

`USER_DECISION_NEEDED`

- Read `PENDING_FRONTSTAGE.md`.
- Process unresolved items one by one.
- Decide whether koder can resolve the item directly or must escalate it to the
  user.
- Record each resolution durably before the planner consumes it.

`BLOCKED_ESCALATION`

- Report the blocker to the user with the shortest actionable explanation.
- If the blocker is seat/runtime health and koder is allowed to self-repair,
  attempt the repair first, then notify planner.
- Otherwise ask for the missing user/system action and preserve `task_id`.

`CHAIN_COMPLETE`

- Summarize the final result for the user.
- Mark the frontstage thread as complete or archived.
- Do not keep patrol nagging on a finished chain.

`BOOTSTRAP_REQUIRED`

- Treat session binding plus tmux state as the authority, not stale prose.
- Resolve planner via the adapter.
- If planner is absent, instantiate it.
- If planner binding exists but tmux is down, restart or notify the operator
  path.
- If planner exists and is running but stale, send a reminder or unblock notice.

## Planner Launch Follow-up

When `planner` has just been initialized and the project uses OpenClaw + Feishu:

- proactively ask the user to have the main agent create or surface the target
  Feishu group and report the `group ID`
- do not ask for `open_id`; `group ID` is enough
- keep the main agent on `requireMention = true`
- keep the project-facing `koder` account on `requireMention = false` for that
  group by default; only add optional system seats such as `warden` when they
  are explicitly deployed for that group
- verify existing group ids from `~/.openclaw/agents/*/sessions/sessions.json`
  by scanning keys prefixed with `group:`
- check `~/.openclaw/openclaw.json` for the group-specific settings under
  `messaging.feishu.accounts.<account>.groups.<group_id>`
- after the `group ID` arrives, explicitly confirm whether that group should
  bind the current project, switch to another existing project, or bootstrap a
  new project; do not treat a new group as an automatic new project
- planner should treat that same bound group as the user-visible bridge for
  `OC_DELEGATION_REPORT_V1` decision gates and closeouts; keep the legacy
  auto-broadcast path disabled unless it is explicitly opted in
- once the `group ID` and project binding are confirmed, immediately delegate
  the bridge smoke test to `planner`, tell the user `收到测试消息即可回复希望完成什么任务`,
  and start `reviewer-1` in parallel when that seat exists
- if the current chain is verification-heavy, ask `planner` to launch `qa-1`
  in parallel with or immediately after `reviewer-1`; do not treat QA as a
  first-launch seat
- after planner initialization completes, rely on the planner smoke test and
  `OC_DELEGATION_REPORT_V1` bridge receipts instead of a free-form
  “planner 初始化完成” broadcast

If the main agent is also in that group, it should remain mention-gated. Do not
weaken the main account to `requireMention = false`.

## Feishu Delegation Receipt Rule

When the planner-facing bridge uses `lark-cli --as user`, the sender identity in
the Feishu group is no longer meaningful. `koder` must not infer "this came
from planner" from the sender.

Instead, treat the group message as machine-actionable only when it contains a
strict `OC_DELEGATION_REPORT_V1` envelope. Parse it as a delegation receipt,
not as an agent persona speaking.

Required fields:

- `project`
- `lane`
- `task_id`
- `dispatch_nonce`
- `report_status`
- `decision_hint`
- `user_gate`
- `next_action`
- `summary`

Interpretation rules:

- `lane=planning` means the receipt belongs to the planning lane; it does not
  mean the visible sender is planner
- reject the envelope if `project`, `task_id`, or `dispatch_nonce` do not match
  the current active chain
- only auto-advance when the state machine resolves to a safe branch:
  `done + proceed + none + consume_closeout`
- for `needs_decision + ask_user`, turn the receipt into a short user question
  instead of dispatching immediately
- for `blocked + retry` or `blocked + escalate`, surface the blocker according
  to the framework decision table; do not invent a hidden next hop

## Stage Closeout Review

When planner later returns a stage closeout to frontstage and the group shows
the wrap-up result, koder must:

- read the linked delivery trail and any referenced specialist deliveries
- reconcile the stage outcome against `TASKS.md`, `STATUS.md`, and the project
  docs
- update `PROJECT.md` and any other affected project documents before the user
  summary goes out
- only then summarize the closeout back to the user or auto-advance the chain

## Window Maintenance

For iTerm/TUI maintenance, koder should treat `agent-admin window open-monitor
<project>` as the single canonical repair action:

- use it whenever seats start, stop, or drift out of the canonical tab order
- do not hand-open per-seat windows for a `tabs-1up` project
- do not use raw `tmux attach` as the normal recovery path
- expect the command to rebuild one project window with one tab per running seat
- if duplicate project windows already exist, the helper will close stale copies
  and restore the canonical layout

The practical rule is: one project, one iTerm window, tabs in canonical seat
order. Koder owns keeping that layout tidy; specialists should never freehand it.

## Action Schema Consumption

Use adapter calls to consume action schema:

- `instantiate` -> `adapter.instantiate_seat(project_name=..., template_id=..., instance_id=...)`
- `restart` -> `adapter.check_session(...)` then run the project’s runtime
  restart path outside this skill if available; otherwise notify the operator
  explicitly
- `redispatch` -> `adapter.dispatch_task(...)` or `adapter.notify_seat(...)`
  depending on whether a durable task handoff is required
- `switch_provider` -> escalate to the operator/user with the requested provider
  and reason; do not improvise runtime mutation in the skill layer
- `none` -> no adapter action

Guardrails:

- Every adapter call must include `project_name`.
- Never dispatch directly to specialists from frontstage; planner is the next
  hop unless the protocol explicitly says otherwise.
- Preserve `task_id` across restart, redispatch, and unblock operations when the
  chain is still active.

## Pending Frontstage Queue

Use the pending queue through the adapter, not by mutating markdown manually in
the prompt layer.

Required adapter calls:

- `read_pending_frontstage(project_name=...)`
- `resolve_frontstage_item(project_name=..., item_id=..., resolution=..., resolved_by=...)`

Resolution rules:

- if `user_input_needed = false` and `type = decision`, koder may resolve the
  item directly by adopting `planner_recommendation` or
  `koder_default_action`
- if `user_input_needed = false` and `type = clarification`, koder may answer
  from project knowledge and current context
- if `user_input_needed = true` and `blocking = true`, koder must escalate to
  the user and wait
- if `user_input_needed = true` and `blocking = false`, koder should notify the
  user asynchronously while allowing the chain to continue with
  `koder_default_action`
- if koder overrides the planner recommendation, the reason must be recorded in
  `resolution`

Do not self-resolve these categories:

- scope changes
- resource investment decisions such as spawning more specialists
- architecture direction changes

These may be self-resolved when planner already narrowed the choice:

- execution strategy order
- technical option selection within planner-approved bounds
- project-context clarification from existing docs

Archive rules:

- koder only processes items with `resolved: false`
- once resolved, mark `resolved: true`, set `resolved_by`, set `resolved_at`,
  and write `resolution`
- move the item from `## 待处理事项` to `## 已归档`; do not delete it
- planner later consumes archived resolutions and clears the frontstage backlog

## Project Switching

Keep an explicit `current_project`.

Switch protocol:

1. confirm or parse the target project name
2. drain or quiesce the current project inbox through the adapter before leaving it
3. increment `frontstage_epoch`
4. set `current_project`
5. reload profile, roster, planner binding, and brief through the adapter
6. refresh project-local knowledge files such as `AGENTS.md`
7. reply with the new project status using the project tag format

Rules:

- Never dispatch, notify, instantiate, or complete a handoff without an explicit
  `project_name`.
- Only consume the inbox for `current_project`. Do not process another project's
  queued operations while a different project is active.
- Do not reuse brief state across projects.
- If the requested project profile is missing, say so plainly and stop.

## Message Formats

DM with user:

- Prefix user-visible status with `[{project}]`.
- Intake: natural language -> concise task framing.
- Status: `[{project}] {用户摘要}`
- Decision: `[{project}] 决策点：{options}`
- Blocker: `[{project}] 阻塞：{reason}`
- Switch confirmation: `已切换到 {project}`

Project channel / seat-to-seat notices:

- Dispatch: `{task_id} assigned from {source} to {target}`
- Review result: `{task_id} verdict: {VERDICT}`
- Patrol: `patrol: {brief_status}`
- Blocker: `BLOCKED_ESCALATION: {reason}`

Structured envelope when a system requires machine-readable metadata:

```toml
[message]
project = "{project_name}"
sender = "{seat_id}"
receiver = "{seat_id | user}"
task_id = "{task_id}"
disposition = "{disposition}"
action = "{requested_operation}"
body = "{natural_language_body}"
```

## Patrol Triggers

Patrol is opt-in only.

Trigger patrol when:

- `[patrol].enabled = true`
- the user asks for status / reminder / health check
- frontstage receives a known stale or blocked chain signal
- `BOOTSTRAP_REQUIRED` is present in `PLANNER_BRIEF`

Patrol behavior:

- load brief and dynamic roster through the adapter
- if the brief disposition requires it, load unresolved pending-frontstage items
  through the adapter
- evaluate `frontstage_disposition`
- if `BOOTSTRAP_REQUIRED`, route attention back to `koder` with
  `requested_operation`
- if `AUTO_CONTINUE`, do not create user-visible noise

## Heartbeat reception

When an incoming message starts with `[HEARTBEAT_TICK project=<X> ts=<T>]`:

1. Parse the header, confirm project matches this workspace.
2. Read state.db recent events: `sqlite3 ~/.agents/state.db "SELECT type, COUNT(*) FROM events WHERE project='<X>' AND ts > datetime('now','-1 hour') GROUP BY type;"` (or use `python3 ~/.clawseat/core/scripts/state_admin.py recent-events --limit 20 --project <X>`).
3. Run drift scan: check STATUS.md mtime, patrol/handoffs/ recent files, any stuck in-flight tasks.
4. If no drift: post a short `[HEARTBEAT_ACK project=<X> ts=<T2>] clean` reply to the Feishu group.
5. If drift: post `[HEARTBEAT_ACK project=<X> ts=<T2>] DRIFT: <summary>` + surface to user, AND create a handoff for planner: `dispatch_task.py --source koder --target planner --task-id PATROL-DRIFT-<ts> ...`.

Rules:
- If `project` in the tick header does not match the current workspace project, ignore the tick.
- Never block on heartbeat processing — complete within one patrol cycle.
- Do not send ACK if the tick came from a test or stub sender (no real lark-cli invocation path); just log internally.

## Auth-mode awareness (post-install questions)

Operators may ask you questions like "why is builder-2 idle?" or "how do
I switch seat X to api?". Each backend seat has a `session.toml` with
`auth_mode` + `provider` written during install by
`resolve_auth_mode.py`. The six canonical choices and their trade-offs
live in `docs/auth-modes.md` (per-mode runtime details) and
`docs/install.md#choosing-auth-mode-claude-seats` (decision table).
Prefer reading those files over improvising an answer — the modes and
recommended defaults change between releases.

Typical triage pattern:

1. `sqlite3 ~/.agents/state.db "SELECT seat_id, auth_mode, provider, status FROM seats WHERE project='<X>';"`
2. If a seat is stuck on legacy `oauth` and hitting the Keychain popup,
   route the user to `docs/auth-modes.md` — migration belongs to A1's
   `migrate_seat_auth.py`, not a koder-owned edit.
3. For new-seat installs, direct the operator to
   `core/skills/clawseat-install/scripts/resolve_auth_mode.py --seat <id>`;
   do not write `session.toml` from koder.

## Non-Negotiables

- Do not bypass planner for normal execution routing.
- Do not read specialist artifacts directly when the brief can answer the same
  question.
- Do not use raw `tmux send-keys` when transport helpers exist.
- Do not drop the project tag or `project_name` from multi-project operations.
