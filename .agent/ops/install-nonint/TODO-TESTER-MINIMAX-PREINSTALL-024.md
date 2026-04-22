# TODO — PREINSTALL-024 (pre-analyze live install blockers)

```
task_id: PREINSTALL-024
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental worktree)
priority: P0
subagent-mode: REQUIRED — spawn 3 parallel subagents (A/B/C below)
do-not-modify: read-only audit only, no file changes
```

## Context

SWEEP-023 (codex) is deleting legacy dead code right now.
When it finishes, we immediately start live install smoke on ~/ClawSeat.
Your job: find every landmine BEFORE we step on it.

From prior live-run attempts, 3 known failure categories exist.
Investigate all 3 in parallel subagents.

---

## Subagent A — env_scan auth detection gap

Read `/Users/ywf/ClawSeat/scripts/env_scan.py` in full.

Known issue: it only checks `~/.claude/.credentials.json` for Claude auth,
but real Claude Code OAuth lives in macOS Keychain
(entry name: "Claude Code-credentials"). So it reports `auth_methods: []`
even when the user is logged in.

Investigate:
1. Confirm the exact check in env_scan.py (line numbers + logic)
2. Check if there's a way to detect Keychain auth without macOS API
   (e.g. does `claude --version` or `claude config list` indicate auth state?)
3. Check `scripts/launch_ancestor.sh` — does it depend on env_scan output
   for auth gating, or does it check independently?
4. Propose the minimal fix (1-3 lines) to either detect Keychain auth
   or bypass the false-negative for launch purposes

---

## Subagent B — project registration prerequisite

Known issue: `agent_admin session switch-harness` requires the project
to be pre-registered. On a fresh install this step is missing from
docs/INSTALL.md, causing "project not found" errors.

Investigate:
1. Read `docs/INSTALL.md` end-to-end. Does it include a
   `agent-admin project create` or equivalent step? (line numbers)
2. Read `core/scripts/agent_admin.py` — what does `project create`
   or `project-open` actually do? What files does it create?
   (grep: `def.*project`, `project create`, `project_open`)
3. Read `scripts/launch_ancestor.sh` — where does it call
   `switch-harness` or `start-engineer`? (line numbers)
4. What is the minimal sequence of commands to register a project
   and bring up ancestor + memory from scratch?

---

## Subagent C — 4 pre-existing test_scan_project_smoke.py failures

4 tests in `tests/test_scan_project_smoke.py` have been failing since
codex's commit 5d26fee. These are NOT caused by our deletions.

Investigate:
1. Run: `python3 -m pytest tests/test_scan_project_smoke.py -v --tb=short 2>&1`
2. Read the 4 failing test bodies in `tests/test_scan_project_smoke.py`
3. Identify root cause — what exactly do they check and why do they fail?
4. Are these safe to skip (xfail/skip markers) or do they reveal a real
   regression in 5d26fee that blocks the install flow?

---

## Deliverable

Write `DELIVERY-PREINSTALL-024.md` in
`/Users/ywf/ClawSeat/.agent/ops/install-nonint/`:

```
task_id: PREINSTALL-024
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <one line>

## Subagent A — env_scan auth gap
<findings + proposed fix>

## Subagent B — project registration gap
<findings + minimal startup command sequence>

## Subagent C — smoke test failures
<root cause + skip-safe verdict>

## Overall: install readiness verdict
READY | BLOCKED_BY <list>
```

Notify planner: "DELIVERY-PREINSTALL-024 ready".
