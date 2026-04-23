# TASK: Fix #10 — lark-cli `--as` flag position broken in 1.0.18

**Assigned to**: codex-xcode TUI (idle, has context on lark-cli from prior rounds)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Priority**: unblocks Phase-A B5.5 smoke dispatch (operator currently waiting)

---

## Background

lark-cli upgraded from 1.0.14 → 1.0.18 moved the `--as <user|bot>` flag from **subcommand-local** to **global**:

- Old (1.0.14): `lark-cli auth status --as bot` ← flag AFTER subcommand
- New (1.0.18): `lark-cli --as bot auth status` ← flag BEFORE subcommand

Current `core/skills/gstack-harness/scripts/send_delegation_report.py` (and possibly other callers) still uses the old position. Observed failure in ancestor pane at B5.5:
> "B5.5 smoke dispatch 因 lark-cli --as flag 格式问题无法完成，消息体构造正确但 auth 校验失败"

Memory reference: `feedback_feishu_chat_id_resolution.md`, `reference_lark_cli_troubleshooting.md`.

---

## Fan-out instruction (MANDATORY)

Work is small but has 2 parallel sub-lanes. Use your Agent tool to fan-out.

See `core/skills/gstack-harness/references/sub-agent-fan-out.md` (round-4 delivered) for the pattern.

## Lane A — Scan + patch all `lark-cli .* --as` call sites

```bash
grep -rn 'lark-cli.*--as' /Users/ywf/ClawSeat/core /Users/ywf/ClawSeat/scripts --include="*.py" --include="*.sh"
```

For each hit, move `--as <value>` from subcommand position to **before** the subcommand.

Known candidate file (per memory + prior context):
- `core/skills/gstack-harness/scripts/send_delegation_report.py` — confirmed hit
- `core/shell-scripts/send-and-verify.sh` — had `auth status --as` references earlier; verify

Edit pattern:
- `lark-cli auth status --as bot` → `lark-cli --as bot auth status`
- `lark-cli im v1 chats --as user` → `lark-cli --as user im v1 chats`
- Generic: any `lark-cli <subcommand> ... --as <X>` → `lark-cli --as <X> <subcommand> ...`

**Do NOT change lark-cli invocations that don't use `--as`** (those are unaffected).

## Lane B — Test coverage

1. Find or write a test that exercises `send_delegation_report.py` with a mock/stub lark-cli: `tests/test_send_delegation_report*.py`
2. Assert the constructed argv order has `--as <X>` BEFORE the subcommand
3. If no such test exists, add `tests/test_lark_cli_as_flag_position.py` — regex parse callsites via same grep, assert all are correct

---

## Deliverable

1. Patches applied on experimental branch
2. New/updated tests pass
3. Write `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ISSUE10-LARKCLI-AS-FLAG.md`:
   - Files Changed (exact path:line for each fix)
   - Before/after snippet per call site
   - Test results
   - Known residual Feishu issues (document for operator): #9 token cleared, #11 bot not in group — these are NOT in scope for this task, just note them

## Signal completion

`echo ISSUE10_DONE`

---

## Constraints

- Small mechanical fix — don't expand scope; don't rewrite lark-cli interaction patterns
- Parallel-safe with all 4 currently-running workers (reviewer, builder, codex-chatgpt Matrix, gemini role-skills) — none touch `send_delegation_report.py` or lark-cli wrapper code
- No commit — planner commits after reviewer verdict bundle
- If you find lark-cli 1.0.18 made OTHER breaking changes (not just --as), note them in DELIVERY "Residual" section — do NOT fix them here

## After delivery

Operator will retry B5.5 smoke dispatch in ancestor pane. Expect `--as` auth to pass; the remaining failures will isolate #9 (token) and #11 (bot in group) cleanly.
