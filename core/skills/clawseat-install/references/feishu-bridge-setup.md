# Feishu Bridge Setup & Smoke Test

## Prerequisites

- `lark-cli` installed and in PATH (`brew install larksuite/cli/lark-cli` or check `which lark-cli`)
- OpenClaw gateway running
- A Feishu group that the project bot has been added to

## Step 1: Verify lark-cli auth

```bash
lark-cli auth status
```

If `tokenStatus` is `needs_refresh` or `expired`:

```bash
lark-cli auth login
```

Follow the browser prompt to complete OAuth. This is a **user action** — the agent cannot complete it automatically.

## Step 2: Collect Feishu group ID

Ask the user for the Feishu group ID. It can be found:

- In the Feishu admin panel under group settings
- By scanning OpenClaw sessions: `python3 $CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/find_feishu_group_ids.py`
- From `sessions.json` keys with `group:` prefix

Format: `oc_` followed by a hex string (e.g. `oc_0e1305956760980a9728cb427375c3b3`)

## Step 3: Confirm project-group binding

Before binding, koder must confirm with the user:

1. Is this group for the **current project**?
2. Or should it **switch to an existing project**?
3. Or should it **create a new project** for this group?

One project = one group. One group = one project.

## Step 4: Bind the project to the group

Planner (or koder via adapter) calls:

```python
bind_project_to_group(
    project="install",
    group_id="oc_xxx",
    account_id="<koder_app_id>",
    session_key="<openclaw_session_key>",
    bound_by="<user>",
    authorized=True,
)
```

This writes `~/.agents/projects/install/BRIDGE.toml`.

## Step 5: Configure requireMention

- Main agent (koder-facing OpenClaw): `requireMention: true` (default)
- Project koder account in group: `requireMention: false`

See `references/feishu-group-no-mention.md` for configuration details.

## Step 6: Smoke test

Planner sends a test delegation report to the bound group:

```bash
python3 $CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py \
  --project install \
  --lane planning \
  --task-id BRIDGE-SMOKE-001 \
  --report-status done \
  --decision-hint proceed \
  --user-gate none \
  --next-action consume_closeout \
  --summary 'Feishu bridge smoke test — if you see this message, the bridge is working' \
  --chat-id oc_xxx
```

Tell the user: `收到测试消息即可回复希望完成什么任务`

If the message arrives in the Feishu group, the bridge is working.

## Step 7: Verify koder can parse the report

Koder should receive the `OC_DELEGATION_REPORT_V1` envelope in the group and verify:

- `project=install` matches
- `task_id=BRIDGE-SMOKE-001` matches
- `report_status=done` + `next_action=consume_closeout` → auto-advance

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `lark_cli_missing` in send result | `brew install larksuite/cli/lark-cli` |
| `lark_cli_send_failed` | Check `lark-cli auth status`, run `lark-cli auth login` if expired |
| `no_group_id_found` | Pass `--chat-id` explicitly or set `CLAWSEAT_FEISHU_GROUP_ID` |
| Message sent but koder doesn't see it | Check `requireMention` config and restart gateway |
| Permission denied on im:message | Re-run `lark-cli auth login` with `im:message` scope |
