# TASK: Round-5 — Review & enhance 4 role-specific SKILL.md files + update seat mapping

**Assigned to**: gemini TUI (idle, read-heavy investigation + small surgical edits)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Type**: docs/skill review + small code change

---

## Background

During round-3b pivot, planner Claude Code wrote 4 role-skill skeletons at:

- `core/skills/builder/SKILL.md` (~80 lines)
- `core/skills/reviewer/SKILL.md` (~90 lines)
- `core/skills/qa/SKILL.md` (~90 lines)
- `core/skills/designer/SKILL.md` (~100 lines)

These are currently **placeholders from the perspective of `seat_skill_mapping.py`** — round-3b's mapping still points builder/reviewer/qa/designer → `clawseat` (generic), NOT to these new files, because round-3b was written before the files existed.

Two things need to happen:

1. **Review the 4 SKILL.md files** — are they good enough? Structure, completeness, anti-patterns, escalation. If you find gaps, add surgical content (not a rewrite).
2. **Update `core/scripts/seat_skill_mapping.py`** — point each role to its own skill, so seats actually load role-specific content after template-copy fix (round-3b) lands.

---

## Lane A — Content review (read-only critique)

For each of the 4 SKILL.md files, check:

1. **Frontmatter**: `name` matches dir name; `description` is meaningful (not "TBD")
2. **身份约束** section: role's scope is clear; "what they are NOT" is explicit; no overlap with other roles
3. **Upstream section**: task entry point matches canonical pattern (TODO.md + handoff JSON from planner)
4. **Work pattern**: step-by-step concrete; references fan-out rule where independent sub-tasks exist
5. **Deliver**: uses `complete_handoff.py` with correct `--source`/`--target` + role-specific flags (e.g., reviewer has `--verdict`)
6. **Anti-patterns**: section exists with ≥3 concrete mistakes to avoid
7. **Escalation**: explicit path when stuck (status=blocked, etc.)
8. **Role-specific content**:
   - **builder**: code/tests/config-changes scope; "not reviewer" constraint
   - **reviewer**: Verdict canonical values; "not modifier" constraint; review + diff + test verification flow
   - **qa**: test execution only; "not test author" constraint; result honesty
   - **designer**: UI/UX + visual evidence requirement; "not backend" constraint

Write a one-paragraph critique per file with:
- verdict: GOOD (ship as-is) / MINOR_EDITS (list them) / MAJOR_REWRITE (specify why)
- anything you'd add (specific scenario, edge case, anti-pattern you've seen)

## Lane B — Quick surgical edits (if Lane A finds MINOR_EDITS)

Only apply edits that are unambiguous improvements — don't rewrite sections, don't impose a new structure. Good targets:

- Adding 1-2 missing anti-patterns with concrete "don't do X" line
- Fixing typos
- Making a vague instruction concrete (e.g., "run tests" → "run `pytest tests/<relevant> -q`")
- Adding a missing reference link to `gstack-harness/references/`

Do NOT:

- Restructure sections
- Add long prose sections
- Change role definitions or constraint lists
- Rewrite the deliver command templates

If Lane A's verdict is MAJOR_REWRITE for any file, STOP and flag it in the delivery — planner will decide.

## Lane C — Update `seat_skill_mapping.py`

File: `core/scripts/seat_skill_mapping.py` (NEW from round-3b)

Current mapping (per round-3b delivery):

```python
ancestor -> clawseat-ancestor
planner -> planner
memory -> memory-oracle
builder/reviewer/qa/designer -> clawseat  # placeholder
```

Target mapping:

```python
ancestor -> clawseat-ancestor
planner -> planner
memory -> memory-oracle
builder -> builder
reviewer -> reviewer
qa -> qa
designer -> designer
```

Important:

1. Keep SHARED_SKILLS list unchanged (every seat still gets `clawseat`, `gstack-harness`, `tmux-basics`)
2. The suffixed id handling (`builder-1`, `reviewer-1`, etc.) must still work — check that the map lookup handles the suffix
3. Update any existing test that asserted the old placeholder mapping

---

## Fan-out instruction (MANDATORY)

This task has 3 lanes. Lane A alone has 4 independent file reads (per-file critique). **Use your Agent tool to fan-out**:

- Parallel: 4 sub-agents, one per SKILL.md file (Lane A critique)
- Serial: Lane B edits (if needed) + Lane C mapping update + delivery

See `core/skills/gstack-harness/references/sub-agent-fan-out.md` (round-4) for the pattern.

---

## Tests

- Existing round-3b tests asserting the mapping (`test_seat_template_populated_after_profile_create.py` + similar): update if they hardcoded `builder -> clawseat`, re-run and confirm pass
- Add minimum assertion to a mapping test: `SEAT_SKILL_MAP['builder'] == 'builder'` (and for reviewer/qa/designer)

---

## Deliverable

Write `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND5-ROLE-SKILLS-REVIEW.md`:

- Per-file critique (4 paragraphs)
- Lane B edits applied (diff list)
- Lane C mapping update (before/after)
- Test result

## Signal completion

`echo ROUND5_ROLE_SKILLS_DONE`

---

## Constraints

- READ-ONLY for the 4 SKILL.md files unless Lane A explicitly finds MINOR_EDITS
- No rewrites without planner approval (escalate via DELIVERY section for MAJOR_REWRITE)
- Parallel-safe with Matrix reconcile (different files) and reviewer (different files)
- No commit — planner commits after reviewer verdict
