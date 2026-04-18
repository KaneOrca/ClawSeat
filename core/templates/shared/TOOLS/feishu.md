# Feishu / OpenClaw Protocol

## OC_DELEGATION_REPORT_V1

When a Feishu group is bound, use `send_delegation_report.py` to emit a structured
closeout receipt — do NOT hand-write a free-form status message.

```bash
python3 <HARNESS_SCRIPTS>/send_delegation_report.py \
  --profile <PROFILE> \
  --task-id <TASK_ID> \
  --report-status done \
  --decision-hint proceed \
  --user-gate none \
  --next-action consume_closeout \
  --human-summary '<SHORT_PLAIN_LANGUAGE_SUMMARY>'
```

For interactive skill decision gates (`needs_decision` from plan-eng-review etc.):
```bash
python3 <HARNESS_SCRIPTS>/send_delegation_report.py \
  --profile <PROFILE> \
  --task-id <TASK_ID> \
  --report-status needs_decision \
  --report-kind OC_DELEGATION_REPORT_V1 \
  --decision-hint ask_user \
  --user-gate required \
  --human-summary '<THE_SKILL_QUESTION_IN_PLAIN_CHINESE>'
```

## Auth Check

Before first Feishu send in a session, verify auth:
```bash
python3 <HARNESS_SCRIPTS>/send_delegation_report.py --check-auth
```

If status is not `ok`, tell the user: "请在有浏览器的终端运行 `lark-cli auth login`".

## Group Broadcast (Legacy, Disabled by Default)

The legacy group broadcast path is **disabled by default**. It only fires when
`CLAWSEAT_ENABLE_LEGACY_FEISHU_BROADCAST=1` is explicitly set.

The default planner closeout path is `OC_DELEGATION_REPORT_V1` via `lark-cli --as user`.

## User Identity Broadcast

When the bound group uses lark-cli user identity, do NOT trust sender identity for
machine-readable packets. Only consume `OC_DELEGATION_REPORT_V1` as a delegation receipt.

When a closeout becomes visible in the bound group, read the linked delivery trail,
reconcile the wrap-up, and update project docs before summarizing to the user.
