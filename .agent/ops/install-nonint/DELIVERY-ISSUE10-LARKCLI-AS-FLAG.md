# DELIVERY-ISSUE10-LARKCLI-AS-FLAG

Date: 2026-04-24
Repo: `/Users/ywf/ClawSeat`
Branch: `experimental`
Commit: not created
Task: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/TASK-ISSUE10-LARKCLI-AS-FLAG.md`

## Scope Completed

Fixed the `lark-cli` 1.0.18 `--as` flag position breakage for the actual
runtime call sites under `core/` and `scripts/` that still used the old
subcommand-local form.

## Files Changed

### 1. Runtime fixes

- `core/skills/gstack-harness/scripts/send_delegation_report.py:93`
- `core/skills/gstack-harness/scripts/send_delegation_report.py:238`
- `core/skills/gstack-harness/scripts/_feishu.py:516`
- `core/skills/gstack-harness/scripts/_feishu.py:719`
- `core/lib/project_binding.py:380`
- `core/scripts/heartbeat_beacon.sh:39`

Before:

```python
cmd = [lark_cli, "auth", "status"]
if identity != "auto":
    cmd.extend(["--as", identity])
```

After:

```python
cmd = [lark_cli]
if identity != "auto":
    cmd.extend(["--as", identity])
cmd.extend(["auth", "status"])
```

Before:

```python
cmd = [lark_cli, "im", "+messages-send"]
if identity != "auto":
    cmd.extend(["--as", identity])
```

After:

```python
cmd = [lark_cli]
if identity != "auto":
    cmd.extend(["--as", identity])
cmd.extend(["im", "+messages-send"])
```

Resulting argv examples:

- `lark-cli auth status --as bot` -> `lark-cli --as bot auth status`
- `lark-cli im +messages-send --as user ...` -> `lark-cli --as user im +messages-send ...`

Additional fixed call sites:

- `core/skills/gstack-harness/scripts/_feishu.py`
  - auth check: `[lark_cli, "auth", "status", "--as", normalized]`
    -> `[lark_cli, "--as", normalized, "auth", "status"]`
  - send path: `[lark_cli, "im", "+messages-send", "--as", normalized, ...]`
    -> `[lark_cli, "--as", normalized, "im", "+messages-send", ...]`

- `core/lib/project_binding.py`
  - metadata lookup: `[lark_cli, "im", "chats", "list", "--as", "user", ...]`
    -> `[lark_cli, "--as", "user", "im", "chats", "list", ...]`

- `core/scripts/heartbeat_beacon.sh`
  - shell invocation: `"$lark_cli" im +messages-send --as user ...`
    -> `"$lark_cli" --as user im +messages-send ...`

### 2. Test coverage

- `tests/test_send_delegation_report_identity.py:99`
- `tests/test_send_delegation_report_identity.py:107`
- `tests/test_send_delegation_report_identity.py:123`
- `tests/test_send_delegation_report_identity.py:137`
- `core/skills/gstack-harness/scripts/selftest.py:471`

Updated assertions now require:

- `--as user auth status`
- `--as bot auth status`
- `--as <identity> im +messages-send ...`

Also added a focused regression asserting no command starts with the obsolete:

- `auth status --as`
- `im +messages-send --as`

Adjusted existing selftest expectation:

- `core/skills/gstack-harness/scripts/selftest.py`
  - before: log contains `im +messages-send --as user`
  - after: log contains `--as user im +messages-send`

## Scan Result

Task scan command:

```bash
grep -rn 'lark-cli.*--as' /Users/ywf/ClawSeat/core /Users/ywf/ClawSeat/scripts --include='*.py' --include='*.sh'
```

Runtime hits requiring code change:

- `core/skills/gstack-harness/scripts/send_delegation_report.py`
- `core/skills/gstack-harness/scripts/_feishu.py`
- `core/lib/project_binding.py`
- `core/scripts/heartbeat_beacon.sh`
- `core/skills/gstack-harness/scripts/selftest.py` (test expectation / smoke assertion)

Non-runtime/commentary-only hits left unchanged:

- `core/scripts/agent_admin_workspace.py`
- comments/docstrings describing `lark-cli --as ...`

Verified `scripts/hooks/planner-stop-hook.sh` does not use `--as`, so no change
was needed there.

## Test Results

- `pytest /Users/ywf/ClawSeat/tests/test_send_delegation_report_identity.py -q`
  - `5 passed`
- `pytest /Users/ywf/ClawSeat/tests/test_send_delegation_report_identity.py /Users/ywf/ClawSeat/tests/test_project_binding.py /Users/ywf/ClawSeat/tests/test_heartbeat.py /Users/ywf/ClawSeat/tests/test_complete_handoff_user_summary.py /Users/ywf/ClawSeat/tests/test_smoke_coverage.py -q`
  - `105 passed`

Validation scan after patch:

- `grep -rn 'lark-cli.*--as' /Users/ywf/ClawSeat/core /Users/ywf/ClawSeat/scripts --include='*.py' --include='*.sh'`
  - no remaining runtime call-site using the obsolete post-subcommand form

## Residual Feishu Issues (Not In Scope)

- `#9` token cleared / auth state issue
  - This task only fixes argv ordering for `--as`.
  - If auth still fails after this patch, operator should diagnose token state
    separately.

- `#11` bot not in group
  - This task does not change group membership or sender permissions.
  - If `--as bot` now reaches auth but send still fails, missing group
    membership / bot scope remains a separate issue.

## Notes

- No runtime interaction pattern was expanded beyond the `--as` position fix.
- No commit was created.
