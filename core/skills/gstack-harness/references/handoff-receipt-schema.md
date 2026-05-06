# Handoff Receipt Schema

This reference documents the durable receipt shapes used by `dispatch_task.py`,
`complete_handoff.py`, `notify_seat.py`, and the planner strict fan-in checks.
The `.json.consumed` sentinel is a presence check, not a rich schema; the JSON
receipt is the canonical structured payload.

## 1. Dispatch receipt

Path pattern:

```text
<handoff_dir>/<task_id>__<source>__<target>.json
```

Required fields:

- `kind`: `"dispatch"`
- `task_id`
- `source`
- `target`
- `title`
- `test_policy`
- `todo_path`
- `reply_to`
- `assigned_at`

Optional fields:

- `correlation_id`
- `docs_consulted`
- `docs_skip_reason`
- `notified_at`
- `notify_message`
- `feishu_group_broadcast`

## 2. Completion receipt

Path pattern:

```text
<handoff_dir>/<task_id>__<source>__<target>.json
```

Required fields:

- `kind`: `"completion"`
- `task_id`
- `source`
- `target`
- `branch_base`: git merge-base <feature_branch> <main>
- `branch_tip`: git rev-parse <feature_branch>
- `pr_number`: PR number used for closeout
- `ci_conclusion`: success | failure | strict-diff | strict_diff_zero
- `status`
- `title`
- `summary`
- `correlation_id`

Common optional fields:

- `test_policy`
- `delivery_path`
- `delivered_at`
- `source_todo_path`
- `used_fallback_delivery`
- `verdict`
- `frontstage_disposition`
- `user_summary`
- `next_action`
- `todo_path`
- `assigned_at`
- `notify_skipped`
- `notified_at`
- `notify_message`
- `feishu_delegation_report`
- `feishu_group_broadcast`

Optional fields:

- `expected_base_sha`: git rev-parse of `clawseat/main` or `origin/main` captured by `dispatch_task.py` at dispatch time

## 3. Consumed ACK

The durable ACK trail has two pieces:

- TODO line format: `Consumed: <task_id> from <source> at <iso8601>`
- Fan-in sentinel: `*.json.consumed`

The sentinel only records presence. For field-level contract checks, use the
JSON receipt fields above.


## DF completion receipt additions
- `base_drift_acknowledged` - optional boolean completion receipt field for intentional current-main drift.
- `drift_reason` - optional JSON string capturing `drift_from`, `drift_to`, and `orthogonal_files_verified`.
