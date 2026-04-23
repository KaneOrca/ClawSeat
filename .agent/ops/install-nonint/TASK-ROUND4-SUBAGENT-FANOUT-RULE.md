# TASK: Round-4 — Codify sub-agent fan-out rule in gstack-harness skill

**Assigned to**: codex-chatgpt (round-4, dispatched after round-3b lands)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Type**: docs / skill-content change (no runtime code)

---

## Background — why this rule needs to exist

Observed in round-3 dispatch (2026-04-24 planner Claude Code installing ClawSeat v0.7):

1. **Round-3a codex-xcode**: task had 2 fully-independent sub-goals — (Part A) retire `wait-for-seat.sh` 1-arg form + migrate 3 tests, (Part B) fix launcher `--auth xcode` config.toml rendering + 2 new tests. The TUI serialized them across ~30 minutes. Each part touched different files (`scripts/wait-for-seat.sh` + docs/tests vs `core/launchers/agent-launcher.sh`); nothing shared between them. Fan-out would have halved wall-clock.

2. **Round-3c gemini MATRIX audit**: read-only investigation of N `(tool, auth_mode, provider)` combinations against launcher's case-branches. Each combo is an independent verification lane. Gemini walked them linearly.

3. **Round-3b codex-chatgpt (previous, pivoted)**: Part A (`#16` start-engineer silent fail, `agent_admin_session.py`) and Part B (`#14` seat `.claude/` isolation, `agent-launcher.sh`) — zero file overlap. Planner's dispatch prompt did NOT mention fan-out; TUI defaulted to serial.

4. **Planner Claude Code itself**: defaulted to serial `Grep` / `Read` even when searching multiple independent codepaths where `Explore` sub-agent would have been faster.

Root cause: **the protocol never tells seats/TUIs to fan out**. `gstack-harness` skill (the one every seat loads as a shared baseline) is silent on this. `dispatch-playbook.md` gives serial templates only.

---

## Deliverable — 3 patches

### Patch 1: Add a Design rule to `SKILL.md`

**File**: `/Users/ywf/ClawSeat/core/skills/gstack-harness/SKILL.md`

In the existing `## Design rules` list (starts around line 128), append the following bullet (after the existing bullets, before `## Claude recovery rule`):

```markdown
- Sub-agent fan-out is the default for tasks with independent sub-goals. If a
  dispatched task has two or more sub-parts that touch disjoint files, run
  disjoint tests, or investigate disjoint code paths, the receiving seat must
  fan them out via its agent-dispatch primitive (Claude Code `Agent` tool,
  Codex subagent, Gemini subagent) and only serialize the final cross-check /
  delivery step. See [Sub-agent fan-out](references/sub-agent-fan-out.md) for
  the trigger rules, pattern, and anti-patterns.
```

Also update the `## Load by task` section (around line 34-57) to add a new loading trigger:

```markdown
- parallel execution of independent sub-tasks
  - [Sub-agent fan-out](references/sub-agent-fan-out.md)
```

(insert between existing bullets, wherever organizationally clean)

### Patch 2: Create `references/sub-agent-fan-out.md`

**File**: `/Users/ywf/ClawSeat/core/skills/gstack-harness/references/sub-agent-fan-out.md` (NEW)

Full content (copy-paste ready):

````markdown
# Sub-agent Fan-out

When a dispatched task has independent sub-goals, the receiving seat/TUI must
parallelize them via sub-agents instead of serializing. This is a default, not
an optimization.

## When to fan out (trigger rules)

Fan-out is **required** if any of the following are true:

1. **Disjoint file sets** — Part A and Part B modify non-overlapping files
   (e.g., Part A touches `scripts/a.sh`, Part B touches `core/b.py`)
2. **Disjoint test targets** — Part A adds/modifies tests in `tests/test_a_*`,
   Part B adds/modifies tests in `tests/test_b_*`, and they don't share
   fixtures under test
3. **Disjoint research queries** — the task is read-only investigation with N
   independent lanes (e.g., audit N `(tool, auth_mode, provider)` combos;
   check N endpoints; diff N versions)
4. **Explicitly named multi-part task** — the task spec labels parts as
   "Part A / Part B / Part C" without stated interdependence

Fan-out is **not required** when:

- Parts share mutable state (e.g., both modify the same config file, the same
  function, or the same test fixture)
- The task is a single short change (<5 minutes estimated wall-clock)
- The receiving tool/agent does not support sub-agents (plain shell workers,
  some minimal Codex profiles)
- Parts must observe each other's intermediate state to be correct
  (e.g., Part B verifies the side-effect of Part A)

## Fan-out pattern

```
1. Split the task brief into N self-contained sub-briefs. Each sub-brief must
   name its own file scope, test targets, and acceptance criteria. A sub-brief
   that says "also coordinate with the other lane" is NOT self-contained —
   split again or keep serial.

2. Spawn N sub-agents in parallel:
   - Claude Code: single message with N `Agent` tool calls
   - Codex: `codex subagent` per lane (launcher-dependent)
   - Gemini: sub-agent task per lane

3. Collect N deliverables. Each sub-agent returns: files touched, tests run,
   verdict (pass/fail/blocked).

4. Serial finalization:
   - Cross-check: do the N deliverables conflict? (shared imports, stale
     snapshots, duplicated logic, etc.)
   - Regression sweep: run the combined test matrix once, not N times
   - Write ONE DELIVERY-*.md summarizing all lanes + the cross-check result
```

## Anti-patterns

- **"I'll do Part A first, then Part B"** when parts are disjoint → serial
  when you could fan out
- **Fan-out without cross-check** → two sub-agents independently patch the
  same enum in different files and silently disagree
- **Splitting a single bug fix into fake parallel lanes** → e.g., "Lane 1:
  change variable name in call site, Lane 2: change variable name in
  definition" — these are one atomic edit
- **Delegating judgment to sub-agents** → the top-level seat must still
  synthesize the final verdict; sub-agents report, they do not decide

## Example — round-3a codex-xcode (what should have happened)

Task: retire `wait-for-seat.sh` 1-arg form AND fix launcher `--auth xcode`
config.toml rendering.

Disjoint file sets:
- Part A: `scripts/wait-for-seat.sh`, 3 existing tests, 2 docs
- Part B: `core/launchers/agent-launcher.sh`, 2 new tests

Disjoint test targets: `test_wait_for_seat_*` vs `test_launcher_codex_xcode_*`.

Correct execution:

```
parallel:
  agent_A brief: "Retire wait-for-seat.sh 1-arg form.
    Scope: scripts/wait-for-seat.sh + tests + docs.
    Verdict: report files touched + pytest result."

  agent_B brief: "Fix launcher --auth xcode config.toml rendering.
    Scope: core/launchers/agent-launcher.sh + 2 new tests.
    Verdict: report files touched + pytest result."

serial (main):
  1. Read both agent reports
  2. Run combined regression sweep (48 existing tests)
  3. Write DELIVERY-ROUND3-XCODE-CONFIG-AND-1ARG-RETIRE.md merging both
```

Wall-clock savings: ~40-50% on the per-part investigate+implement+test loop.

## Example — audit/investigation (round-3c gemini)

Task: audit N combinations in `SUPPORTED_RUNTIME_MATRIX` against launcher
case-branches.

Each combo is an independent verification lane — no shared mutable state, no
cross-combo dependencies.

Correct execution:

```
parallel:
  agent_1: verify claude+oauth+anthropic against launcher
  agent_2: verify claude+api+minimax against launcher
  agent_3: verify codex+api+xcode-best against launcher
  ...
  agent_N: verify gemini+oauth+google against launcher

serial (main):
  1. Collect N verdicts
  2. Cluster into keep / fix / drop recommendations
  3. Write DIAGNOSIS-MATRIX-AUDIT.md
```

## How this interacts with dispatch_task.py

`dispatch_task.py` writes a `TODO.md` entry for the target seat. When the
dispatching planner knows the task is fan-out-eligible, the `--objective` or
task body should include the explicit instruction:

> "This task has N independent sub-parts. Fan them out to sub-agents; only
> serialize the final cross-check and single DELIVERY write-up."

Planner's default dispatch prompt template (see `dispatch-playbook.md`) must
include a fan-out hint when the task has a Part A / Part B / Part C structure.

## Checklist for the receiving seat

Before starting work, the seat should ask:

- [ ] Are there 2+ named parts in the task brief?
- [ ] Do the parts touch disjoint files?
- [ ] Do the parts modify disjoint test targets?
- [ ] Is any part >5 minutes of estimated work?

If any two of those are "yes", **fan out**. If all are "no", proceed serial.
````

### Patch 3: Update `references/dispatch-playbook.md`

**File**: `/Users/ywf/ClawSeat/core/skills/gstack-harness/references/dispatch-playbook.md`

Insert a new section **after** the `## Planner -> specialist` section (currently ends around line 44, before `## Specialist -> planner completion`):

```markdown
## Fan-out hint for multi-part tasks

When a `planner -> specialist` task has 2+ independent sub-parts, the
dispatch `--objective` (or the linked task file body) must explicitly include
a fan-out hint. This tells the specialist to parallelize via sub-agents
instead of serializing.

Template line to include in the objective or task body:

> "This task has <N> independent sub-parts (Part A: <scope>; Part B: <scope>
> [...]). Fan them out to sub-agents using your agent-dispatch primitive
> (Claude `Agent` tool, Codex subagent, Gemini subagent). Serialize only the
> final cross-check and single DELIVERY write-up. See
> [references/sub-agent-fan-out.md] for the full pattern."

See [Sub-agent fan-out](sub-agent-fan-out.md) for the trigger rules and
anti-patterns.
```

---

## Tests / validation

1. `tests/test_gstack_harness_skill_has_fan_out_rule.py` (new):
   - Assert `core/skills/gstack-harness/SKILL.md` contains the string
     `Sub-agent fan-out is the default`
   - Assert `core/skills/gstack-harness/references/sub-agent-fan-out.md` exists
     and contains sections `## When to fan out` and `## Fan-out pattern`
   - Assert `core/skills/gstack-harness/references/dispatch-playbook.md`
     contains `## Fan-out hint for multi-part tasks`

2. Manual: `grep -r "fan.out" core/skills/gstack-harness/` should return at
   least 3 files

3. No regression in existing `gstack-harness` tests (if any exist under
   `tests/`)

---

## Deliverable

1. 3 patches applied on experimental branch
2. 1 new test file
3. `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND4-SUBAGENT-FANOUT.md`
4. Send summary via `send-and-verify.sh` to codex-xcode (204444) for review
5. echo `ROUND4_DONE`

---

## Constraints

- Docs-only / skill-content change; no runtime code edits
- Do NOT apply this rule retroactively to in-flight tasks (round-3b still
  running under the old protocol — let it finish)
- Don't touch other skills (this rule is gstack-harness-specific because
  gstack-harness is the shared baseline for every seat)
- The actual enforcement of fan-out happens at dispatch-time (planner writes
  the hint) and at seat-time (seat reads and obeys) — this patch only
  codifies the rule, not any enforcement

---

## Why this is docs-only

Fan-out is a behavioral norm, not a runtime behavior. Enforcement would
require inspecting the seat's tool-calls at runtime, which is out of scope
for ClawSeat. Instead:

- The rule lives in the shared skill every seat loads
- Every future task dispatch references it in the objective
- Planner Claude Code audits its own behavior against the rule

This gives the observable, grep-able norm without implementing a runtime
enforcer.
