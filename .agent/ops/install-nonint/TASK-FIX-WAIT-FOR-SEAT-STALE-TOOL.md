# TASK: Fix wait-for-seat.sh stale-tool fallback risk + start-engineer variant cleanup

**Assigned to**: codex-chatgpt TUI (agent-launcher-codex-chatgpt-20260423-230652)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Source**: planner

---

## Background

Analysis just confirmed `wait-for-seat.sh` fallback behavior has a subtle risk:

- fallback scans `<project>-<seat>-{claude|codex|gemini}` when `agentctl session-name` resolution fails (after budget retries, around line 74)
- it **does NOT cross to a different `<seat>`** — that guardrail is tested (see `tests/test_install_lazy_panes.py:589`)
- BUT it **can attach to a stale SAME-seat DIFFERENT-tool session** (e.g., canonical is `install-planner-claude`, pane ends up attached to leftover `install-planner-codex`)
- observed failure mode in install test: after `switch-harness` flipped a seat's tool, old tmux session wasn't cleaned up, grid pane's wait-for-seat attached to the old variant → new canonical session had no grid pane attached

## Fix scope (2 lanes)

### Lane A — `wait-for-seat.sh` becomes tool-aware

Currently the fallback scans all 3 tool suffixes blindly. Make it **read the engineer profile's canonical tool** and only accept a session with the canonical suffix.

1. Read `~/.agents/engineers/<seat>/engineer.toml` at fallback time, parse `default_tool` (e.g., `claude`, `codex`, `gemini`)
2. Fallback **only** considers `<project>-<seat>-<canonical_tool>`. Other tool variants → reject with explicit WARN like:
   ```
   wait-for-seat: stale-tool session detected: found <session>, canonical tool is <X>, skipping
   ```
3. If engineer.toml is unreadable (missing / malformed) → conservative fallback: don't attach, keep waiting; print WARN with fix hint
4. Keep the existing "no bare `project-seat` base session" guardrail (`tests/test_install_lazy_panes.py:589`)

### Lane B — `agent_admin session start-engineer` kills stale-tool tmux variants

When starting `<project>-<seat>-<new_tool>`, first kill any pre-existing `<project>-<seat>-<other_tool>` tmux sessions. This prevents the fallback scan from ever seeing stale variants in the happy path.

1. Find implementation in `core/scripts/agent_admin_session.py` (or wherever start-engineer resolves session names)
2. Before launching the new session, enumerate tmux sessions matching `<project>-<seat>-*` pattern; for any with suffix ≠ `<new_tool>`, `tmux kill-session -t <session>`
3. Log each kill: `start-engineer: killed stale-tool session <session>`
4. Race safety: ignore "no such session" errors when killing (they may have exited)

---

## Tests

1. `tests/test_wait_for_seat_rejects_stale_tool.py` (NEW):
   - scenario: engineer.toml says `default_tool = "claude"`, tmux has only `install-planner-codex`; `wait-for-seat.sh install planner` must NOT attach; must keep waiting + print WARN naming the stale session
   - scenario: canonical `install-planner-claude` exists → must attach cleanly
   - scenario: BOTH exist → must pick canonical, ignore stale

2. `tests/test_start_engineer_kills_stale_tool_variants.py` (NEW):
   - scenario: seed tmux with `install-planner-codex`; run `start-engineer planner --project install` when engineer.toml says claude; assert tmux-session-list shows only `install-planner-claude` (codex killed)
   - scenario: no stale variants → normal start, no kills logged

3. Regression: existing `tests/test_wait_for_seat_persistent_reattach.py` + `tests/test_wait_for_seat_trust_detection.py` + `tests/test_install_lazy_panes.py` + any `tests/test_agent_admin_start_engineer*` must still pass

---

## Fan-out instruction

Lane A and Lane B are **disjoint file sets** (wait-for-seat.sh vs agent_admin_session.py) and disjoint test targets. Use your Agent tool to fan-out per the sub-agent-fan-out rule we just landed (`core/skills/gstack-harness/references/sub-agent-fan-out.md`).

---

## Deliverable

1. Patches on experimental branch (do not commit — planner will commit bundle)
2. `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-WAIT-FOR-SEAT-STALE-TOOL.md` with:
   - Files Changed + diff highlights
   - Tests (new + regression result)
   - Edge cases considered
   - Open questions for planner

## Signal completion

`echo WAIT_SEAT_FIX_DONE`

---

## Constraints

- Don't touch the running ClawSeat install tmux sessions (ancestor/planner/builder/reviewer/qa/designer/memory)
- Don't rerun install.sh
- Parallel-safe with Phase-A user activity (we're only changing script/test files, not live state)
- If you find this fix interacts with round-3a's 1-arg retirement changes, flag in DELIVERY — don't silently re-touch that area

## Context references

- Prior analysis summary (same conversation): fallback scans 3 tool suffixes at `scripts/wait-for-seat.sh:59`, budget retry at `:74`, WARN at `:46`, same-seat restriction at `tests/test_install_lazy_panes.py:516`, no-bare-base guardrail at `tests/test_install_lazy_panes.py:589`
