task_id: INST-RESEARCH-022
Consumed: planner
Consumed-At: 2026-04-22
From: tester-minimax
Via: DELIVERY-INST-RESEARCH-022.md (477 lines)
Verdict: ACCEPTED
Status: verdicts accepted; cleanup TODO dispatched to codex (SWEEP-023)

## Open questions resolved by planner

1. openclaw_plugin/ is a live symlink to openclaw-plugin/ — KEEP, NOT in delete list.
2. docs/install/ + docs/review/ don't exist — nothing to do, treat as already cleaned.
3. workflow-architect/ stays KEEP_BUT_DORMANT — leave registry intact, no action this sweep.
4. test_heartbeat.py text-assertion tests — REMOVE them (fragile doc-shape testing anti-pattern).

## Action taken

Dispatched SWEEP-023 to codex-chatgpt. Target: delete 9 dead paths with coordinated test/ref cleanup.
