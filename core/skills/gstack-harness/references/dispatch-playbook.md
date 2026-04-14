# Dispatch Playbook

Use this when you want the lowest-freedom, most repeatable command path.

Prefer these helpers over hand-written `TODO.md`, `TASKS.md`, or `STATUS.md`
edits.

When you must use `<repo-root>/core/shell-scripts/send-and-verify.sh` directly in a
multi-project environment:

- prefer the canonical session name, for example `<project>-engineer-b-<tool>`
- otherwise pass `--project <project>`
- do not use a bare seat id like `engineer-b` without project context

## Frontstage -> planner

```bash
python3 <repo-root>/core/skills/gstack-harness/scripts/dispatch_task.py \
  --profile <project-profile.toml> \
  --source koder \
  --target engineer-b \
  --task-id <TASK_ID> \
  --title '<TITLE>' \
  --objective '<OBJECTIVE>' \
  --reply-to koder
```

## Planner -> specialist

```bash
python3 <repo-root>/core/skills/gstack-harness/scripts/dispatch_task.py \
  --profile <project-profile.toml> \
  --source engineer-b \
  --target engineer-a \
  --task-id <TASK_ID> \
  --title '<TITLE>' \
  --objective '<OBJECTIVE>' \
  --reply-to engineer-b
```

Swap `--target` for `engineer-c`, `engineer-d`, or `engineer-e` as needed.

## Specialist -> planner completion

```bash
python3 <repo-root>/core/skills/gstack-harness/scripts/complete_handoff.py \
  --profile <project-profile.toml> \
  --source engineer-a \
  --target engineer-b \
  --task-id <TASK_ID> \
  --title '<TITLE>' \
  --summary '<DELIVERY_SUMMARY>'
```

Reviewer completion must add `--verdict APPROVED` (or another canonical
verdict).

## Planner consumes specialist completion

After reading the specialist delivery, stamp the durable ACK before routing the
next hop:

```bash
python3 <repo-root>/core/skills/gstack-harness/scripts/complete_handoff.py \
  --profile <project-profile.toml> \
  --source engineer-a \
  --target engineer-b \
  --task-id <TASK_ID> \
  --ack-only
```

## Planner -> frontstage closeout

```bash
python3 <repo-root>/core/skills/gstack-harness/scripts/complete_handoff.py \
  --profile <project-profile.toml> \
  --source engineer-b \
  --target koder \
  --task-id <TASK_ID> \
  --title '<TITLE>' \
  --summary '<CHAIN_SUMMARY>' \
  --frontstage-disposition AUTO_ADVANCE \
  --user-summary '<SHORT_USER_SUMMARY>'
```

If the user really must decide, use:

- `--frontstage-disposition USER_DECISION_NEEDED`
- `--next-action '<DECISION_QUESTION>'`

## Recovery playbook

If someone hand-wrote task state and a handoff drifted:

1. ensure the target `TODO.md` includes `task_id`, `source`, and `reply_to`
2. ensure there is a root seat `DELIVERY.md`, not only a task-local scratch file
3. ensure the target seat was notified through the standard transport
4. backfill the machine-readable receipt with the matching helper
