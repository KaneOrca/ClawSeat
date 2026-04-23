# TASK: Mechanical switch of `Path.home()` → `real_user_home()` for 12 HIGH-PRIORITY sites (#15)

**Assigned to**: `install-builder-codex` (or `install-builder` fallback)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Source**: planner

---

## Background

Gemini's round-4 audit (see `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DIAGNOSIS-15-SANDBOX-HOME-LEAK.md`) identified 12 HIGH-PRIORITY sites where `Path.home()` is called from within a seat sandbox context and leaks the sandbox HOME into constructs that should target the operator's REAL HOME.

Root cause: when a "Manager" seat (ancestor) spawns a new agent, `Path.home()` inside agent_admin scripts returns the Manager's sandbox HOME, nesting the new agent's identity dir at `<ancestor_sandbox>/.agent-runtime/...` instead of `<real_home>/.agent-runtime/...`.

Canonical fix: use `real_user_home()` from `core.lib.real_home`.

---

## Fan-out instruction (MANDATORY)

This task has 2 independent lanes (different files, no shared state). **Use your agent-dispatch primitive to fan-out**.

See `core/skills/gstack-harness/references/sub-agent-fan-out.md` for the pattern.

---

## Lane A — Switch sites in `core/scripts/agent_admin_session.py`

3 HIGH-RISK sites per audit (line numbers are approximate; re-locate the exact call sites since round-3b recently modified this file):

- Fallback in `_real_home_for_tool_seeding`
- Used to locate launcher secret targets (`<home>/.agents/secrets/...`)
- Used to construct runtime identity dirs (`<home>/.agent-runtime/identities/...`)

Required:
1. `grep -n "Path.home()" core/scripts/agent_admin_session.py` — locate all sites (may be more than 3 after round-3b edits)
2. For each site: decide KEEP vs SWITCH using the audit classification (SWITCH when the path targets `~/.agents/` or `~/.agent-runtime/` or `~/.openclaw/` or `~/.lark-cli/` — i.e., operator-visible shared state)
3. Replace with `from core.lib.real_home import real_user_home` + `real_user_home()`
4. Add a test `tests/test_agent_admin_session_real_home_switch.py` that monkeypatches `Path.home()` to return a sandbox path and verifies the constructed paths still land under the REAL home

## Lane B — Switch sites in remaining 9 HIGH-PRIORITY files

Sites per audit:

- `core/tui/ancestor_brief.py:129, 168, 335`
- `core/launchers/agent-launcher-discover.py:46`
- `core/launchers/agent-launcher-fuzzy.py:11`
- `core/scripts/seat_claude_template.py:15` (this is NEW from round-3b — verify the line)
- `core/migration/dynamic_common.py:295`

Required:
1. For each file, `grep -n "Path.home()"` to confirm current line numbers
2. Apply SWITCH — import + replace
3. Run the tests that touch these modules to confirm no regression
4. If a file doesn't have pytest coverage yet, add a minimal smoke test verifying the SWITCH

## Lane C — `scripts/install.sh` ($HOME sites)

Shell script. AMBIGUOUS per audit — "Multiple sites; some need REAL_HOME for persistent state."

Required:
1. `grep -n '\$HOME' scripts/install.sh` — list all sites
2. Classify each:
   - KEEP `$HOME` — install.sh is always run from operator's shell before any seat exists, so $HOME IS real HOME
   - SWITCH — if the site runs from inside a seat subshell (unlikely but check)
3. If all KEEP, document the reasoning in a short comment at top of install.sh

---

## Deliverable

1. Patches applied on experimental branch
2. All existing tests still pass (run `pytest tests/ -q`)
3. New test(s) covering the SWITCH behavior
4. Write `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ISSUE15-SANDBOX-HOME-SWITCH.md`:
   - Files Changed (exact paths)
   - For each file: before/after snippet + classification reasoning
   - Tests: new + regression sweep result
   - Risks / open questions

## Signal completion

`echo ISSUE15_DONE`

---

## Constraints

- Do NOT touch the canonical resolver `core/lib/real_home.py` itself
- Do NOT modify scripts flagged KEEP in the audit (env_scan.py, modal_detector.py, etc.)
- Parallel-safe with round-3b and round-4 (different files / different functions)
- No commit yet — planner will commit after reviewer verdict

---

## Why this is mechanical

All 12 sites have the same pattern: `Path.home() / X / Y` → `real_user_home() / X / Y`. There's no policy judgement, just locate + replace + test. Perfect candidate for fan-out to sub-agents that each handle one file.
