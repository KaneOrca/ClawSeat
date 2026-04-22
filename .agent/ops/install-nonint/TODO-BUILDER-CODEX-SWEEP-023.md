# TODO — SWEEP-023 (targeted legacy delete based on INST-RESEARCH-022 verdicts)

```
task_id: SWEEP-023
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat  (experimental worktree, shared .git with /Users/ywf/coding/ClawSeat)
branch: experimental
priority: P0
do-not-delete: anything not listed below — research is authoritative
```

## Context

INST-RESEARCH-022 (tester-minimax) audited 12 cleanup candidates.
This task executes the safe deletes in the correct order.

**DO NOT touch** (all confirmed KEEP or KEEP_BUT_DORMANT):
- core/migration/
- core/tui/ (both files — ancestor_brief.py is live; machine_view.py dormant but entangled)
- core/adapter/ + adapters/
- core/engine/
- core/skills/socratic-requirements/
- core/skills/workflow-architect/
- core/skills/lark-im/ + lark-shared/
- shells/codex-bundle/ + shells/claude-bundle/ + shells/openclaw_plugin/ (openclaw_plugin is a live symlink, NOT empty)

---

## Subagent mode — REQUIRED

Steps 1-4 have zero test coupling and can run in parallel — spawn one subagent per step.
Steps 5, 6, 7 each require test/ref cleanup before git rm — spawn 3 parallel subagents,
each handling its own cleanup + deletion atomically.
Do NOT serialize all 7 steps sequentially; fan-out wherever there are no shared files.

---

## Delete sequence — lowest risk first

### Step 1 — SAFE_TO_DELETE (no test cleanup needed)

```bash
cd /Users/ywf/ClawSeat
git rm -r core/skills/agent-monitor/
```

Also update the single cosmetic reference:
- `core/skills/gstack-harness/SKILL.md` — remove/update the soft reference to agent-monitor
  (grep: `grep -n "agent-monitor" core/skills/gstack-harness/SKILL.md`)

---

### Step 2 — Dormant prose docs (no test coupling)

```bash
git rm docs/PACKAGING.md
git rm docs/TEAM-INSTANTIATION-PLAN.md
```

Fix the one hard link:
- `README.md:198` — remove the line linking to `docs/PACKAGING.md`

---

### Step 3 — Historical design artifacts (no runtime refs)

```bash
git rm design/followups-after-m1.md
git rm design/phase-7-retire.md
git rm -r design/memory-seat-v3/   # SPEC.md + M2-SPEC.md — historical only
```

If `design/` is now empty, remove the directory too.

---

### Step 4 — Legacy profiles (dormant v0.3 TOMLs)

```bash
git rm -r examples/starter/profiles/legacy/
```

Clean prose refs:
- `docs/ARCHITECTURE.md` — remove/update lines referencing `examples/starter/profiles/legacy/`
  (grep: `grep -n "profiles/legacy" docs/ARCHITECTURE.md`)

---

### Step 5 — arena-pretext-ui (requires manifest + test + docs cleanup)

**Do this FIRST before git rm**:
1. `manifest.toml` — remove the `"examples/arena-pretext-ui"` entry (line ~26)
2. `tests/test_portability.py` — remove or skip `test_arena_profile_is_canonical_layout`
   (the test reads `examples/arena-pretext-ui/profiles/arena-pretext-ui.toml` via tomllib)
3. Prose refs — clean up:
   - `docs/ARCHITECTURE.md` lines referencing arena-pretext-ui
   - `README.md` lines referencing arena-pretext-ui (lines ~5, ~60, ~135, ~169)
   - `docs/schemas/v0.4-layered-model.md` — only if referencing as file path (skip if just a string example)

**Then**:
```bash
git rm -r examples/arena-pretext-ui/
```

---

### Step 6 — docs/design/ancestor-responsibilities.md (requires test + skill + template cleanup)

**Do this FIRST before git rm**:
1. `tests/test_ancestor_brief.py:330` — remove the assertion that checks for
   `docs/design/ancestor-responsibilities.md` in the rendered brief output
2. `core/skills/clawseat-ancestor/SKILL.md` — remove/update the `spec_documents` field
   entry referencing `docs/design/ancestor-responsibilities.md`
3. `core/templates/ancestor-engineer.toml` — update comments at lines ~4,70 that cite this file
4. `core/tui/ancestor_brief.py` — remove/update docstring comment + hyperlink at lines ~4,301

**Then**:
```bash
git rm docs/design/ancestor-responsibilities.md
# if docs/design/ is now empty, remove the directory
```

---

### Step 7 — core/skills/clawseat-koder-frontstage/ (requires test cleanup)

**Do this FIRST before git rm**:
1. `tests/test_heartbeat.py` — remove the two text-assertion tests:
   - `test_skill_md_has_heartbeat_section` (line ~429)
   - `test_skill_md_heartbeat_has_five_steps` (line ~438)
   These are fragile doc-shape tests, not behavior tests — remove entirely.
2. Prose refs (doc-comment only, no runtime impact):
   - `docs/ARCHITECTURE.md` lines 133, 144, 443
   - `docs/design/ancestor-responsibilities.md` line 153 — already deleted in Step 6

**Then**:
```bash
git rm -r core/skills/clawseat-koder-frontstage/
```

---

## Verification after all steps

```bash
cd /Users/ywf/ClawSeat

# 1. Confirm deleted paths are gone
ls core/skills/agent-monitor/ 2>&1           # → No such file
ls examples/arena-pretext-ui/ 2>&1           # → No such file
ls examples/starter/profiles/legacy/ 2>&1   # → No such file
ls design/memory-seat-v3/ 2>&1              # → No such file
ls core/skills/clawseat-koder-frontstage/ 2>&1  # → No such file
ls docs/PACKAGING.md 2>&1                   # → No such file
ls docs/design/ancestor-responsibilities.md 2>&1  # → No such file

# 2. No residual dead references
grep -rn "arena-pretext-ui\|profiles/legacy\|agent-monitor\|clawseat-koder-frontstage\|docs/PACKAGING.md\|followups-after-m1\|phase-7-retire\|ancestor-responsibilities" \
  . --include="*.py" --include="*.toml" --include="*.sh" --include="*.md" \
  | grep -v "^Binary\|\.git\|SWEEP-023\|RESEARCH-022\|ACK-INST"

# 3. Tests pass — no new failures (baseline: 1650 passed, 4 pre-existing smoke failures)
python3 -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

---

## Commit strategy

Single commit on experimental branch:

```
chore(experimental): sweep legacy candidates per INST-RESEARCH-022

Delete 9 dead paths confirmed safe by tester-minimax deep audit.
KEEPs: migration, tui, adapter+adapters, engine, socratic-requirements,
workflow-architect, lark-im+lark-shared, shells.
```

---

## Delivery

Write `DELIVERY-SWEEP-023.md` in `/Users/ywf/ClawSeat/.agent/ops/install-nonint/`:

```
task_id: SWEEP-023
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <one line>

## Deleted paths (with line counts)
## Test/ref cleanups applied
## Verification output (pytest tail + grep results)
## Notes / follow-ups
```

Notify planner: "DELIVERY-SWEEP-023 ready".
