---
name: koder-frontstage
description: Wrapper skill for the user-facing koder seat in a ClawSeat project. Use when the seat is the only user-visible frontstage, must read PLANNER_BRIEF, react to frontstage_disposition, consume action schema, switch project context safely, and route all execution work through planner plus transport helpers.
---

# Koder Frontstage

`koder-frontstage` defines the protocol behavior for the frontstage seat. It does
not replace project knowledge. It translates ClawSeat frontstage state into
repeatable user-facing actions.

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

1. the generated workspace guide (`CLAUDE.md`; legacy `AGENTS.md` only when still present)
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
- set `warden` / koder on `requireMention = false` for that group so it can
  receive the planner-ready broadcast without explicit mentions
- verify existing group ids from `~/.openclaw/agents/*/sessions/sessions.json`
  by scanning keys prefixed with `group:`
- check `~/.openclaw/openclaw.json` for the group-specific settings under
  `messaging.feishu.accounts.<account>.groups.<group_id>`
- confirm `warden` is actually a member of that group before relying on group
  delivery
- once the `group ID` arrives, immediately delegate the bridge smoke test to
  `planner`, tell the user `收到测试消息即可回复希望完成什么任务`, and start
  `reviewer-1` in parallel when that seat exists
- after planner initialization completes, send the broadcast with:

```bash
bash /Users/ywf/.openclaw/skills/claude-desktop/script/feishu-send.sh \
  --target group:<GROUP_ID> \
  "<project> 项目 planner 初始化完成"
```

If the main agent is also in that group, it should remain mention-gated. Do not
weaken the main account to `requireMention = false`.

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
6. refresh project-local knowledge files such as `CLAUDE.md`
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

## Non-Negotiables

- Do not bypass planner for normal execution routing.
- Do not read specialist artifacts directly when the brief can answer the same
  question.
- Do not use raw `tmux send-keys` when transport helpers exist.
- Do not drop the project tag or `project_name` from multi-project operations.
