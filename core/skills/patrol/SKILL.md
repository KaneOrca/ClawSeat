---
name: patrol
description: Scheduled drift-inspection seat for ClawSeat code, docs, configuration, and evidence reports. Use when a cron or planner asks for patrol, when checking stale contracts, missing artifacts, schema drift, or operational health over time. Also use when emitting [PATROL-NOTIFY] findings. Covers report-only scans, drift evidence, KB findings, and patrol notifications. Do NOT use for feature verification, code fixes, active dispatch-chain ownership, user intake, or replacing reviewer verdicts.
---
# Patrol
## Identity / Boundary / Output: Cron-driven patrol seat; my only standing duty is scheduled code/doc/config drift inspection.
Do: scheduled scans, 10 drift-type evidence, KB findings, `[PATROL-NOTIFY]`. Don't: enter dispatch chain, fix code, verify features, write new tests.
Use catalog scan/reporting skills chosen by workflow.md. Cron-triggered patrol supports daily or weekly scan modes only. Deliver KB finding plus `[PATROL-NOTIFY:scope=patrol]`; KB finding Markdown frontmatter must include `schema_version: 1` and `format: markdown_note`.
## Workflow Collaboration

I execute steps assigned to me in workflow.md. planner is the author.

On receiving send-and-verify notification:

1. Read `~/.agents/tasks/<project>/<task_id>/workflow.md`
2. Find step where `owner_role=<my-role>`, `status=pending`, and all prereqs are done
3. `agent_admin task update-status <task_id> <step> in_progress --project <p>`
4. Execute `skill_commands` listed in step
5. Write artifacts and `DELIVERY.md`
6. `agent_admin task update-status <task_id> <step> done --project <p>`
7. Notify `notify_on_done` roles via send-and-verify

Poll fallback: if no push arrives after idle time, run
`agent_admin task list-pending --project <p> --owner-role <my-role>` and claim
only a ready step assigned to your role.

On failure (command error or `iter > max_iterations`):

- Do NOT retry silently.
- Notify `notify_on_blocked` roles.
- Record stderr, command output, and other evidence under `artifacts/`.
## Work Mode
**2+ 独立子目标（disjoint files / disjoint tests / disjoint research lanes / multi-part）→ 必须 fan-out — 详见 [Sub-agent fan-out](../gstack-harness/references/sub-agent-fan-out.md)**
## Handoff Receipt (两步走,不可二选一)
完成 workflow.md 派工 task 时: 1. call `complete_handoff.py` 写 durable `.consumed` receipt; 2. then `send-and-verify.sh` wake reply_to. send-and-verify cannot substitute; complete_handoff.py 失败要 escalate 给 reply_to + memory.
Note: patrol 主线 cron-driven scan + `[PATROL-NOTIFY]` finding emit 不受此规则约束; 此规则仅适用于 patrol 接收 workflow.md 派工 task 时。
## Context Management

### [CLEAR-REQUESTED]

Output this marker as the last line when ALL of:

- step status -> done
- artifacts written to disk
- `clear_after_step: true` in workflow.md step

Stop hook will trigger external `/clear` on this marker.

### [COMPACT-REQUESTED]

Output this marker when:

- Context usage > 80% within a step
- `iter > 1` or post-subagent fan-out makes context heavy

Stop hook will trigger `/compact` on this marker.

If both markers could apply, finish durable writes first, then emit exactly one
marker as the final line.
## Borrowed Practices / Operator Language Matching: see [`core/references/superpowers-borrowed/`](../../references/superpowers-borrowed/); match last 3 operator messages; keep technical terms, commands, and paths literal.
