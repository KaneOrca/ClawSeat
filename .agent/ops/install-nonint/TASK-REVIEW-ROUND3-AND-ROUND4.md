# TASK: Independent review of round-3a / round-3b / round-4 deliveries

**Assigned to**: `install-reviewer-codex` (gpt-5.4 xhigh via xcode.best)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Source**: planner
**Review authority**: canonical `Verdict:` required per lane + one aggregate

---

## Fan-out instruction (MANDATORY)

This task has **3 independent review lanes**. Files/targets are disjoint across lanes. **Use your agent-dispatch primitive to fan-out**; only serialize the final cross-check and aggregate verdict.

See `core/skills/gstack-harness/references/sub-agent-fan-out.md` (newly added in round-4) for the pattern.

---

## Lane 1 — Round-3a: wait-for-seat 1-arg retire + launcher xcode config.toml

**Delivery**: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND3-XCODE-CONFIG-AND-1ARG-RETIRE.md`
**Task spec**: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/TASK-ROUND3A-CODEX-XCODE.md`

Files to review (from delivery):
- `scripts/wait-for-seat.sh`
- `core/launchers/agent-launcher.sh` (codex xcode auth path)
- `core/skills/clawseat-ancestor/SKILL.md`
- `core/templates/ancestor-brief.template.md`
- `tests/test_wait_for_seat_persistent_reattach.py`
- `tests/test_wait_for_seat_trust_detection.py`
- `tests/test_launcher_codex_xcode_fallback.py`

Focus:
1. Does `wait-for-seat.sh` correctly reject 1-arg with actionable error? (`git diff` on the script)
2. Does launcher xcode branch render `[model_providers.xcodeapi]` + `model_provider = "xcodeapi"` correctly? Does it wipe symlinked config.toml before rendering?
3. Are tests covering the retirement + config rendering realistic (not mocked past the point of verifying behavior)?
4. Any regression risk in `agent-launcher.sh` other auth branches (oauth/custom/chatgpt)?

## Lane 2 — Round-3b: template-copy architecture + start-engineer fix

**Delivery**: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND3B-TEMPLATE-COPY-AND-START-ENGINEER.md`
**Task spec**: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/TASK-ROUND3B-REVISED-TEMPLATE-COPY.md`

Files to review (from delivery, 14 total):
- `core/scripts/agent_admin.py`
- `core/scripts/agent_admin_session.py` (Part A — mapping + error propagation)
- `core/scripts/agent_admin_store.py` (calls new template prep on engineer write)
- `core/scripts/seat_skill_mapping.py` (NEW — central role → skill map)
- `core/scripts/seat_claude_template.py` (NEW — template prep + copy helper)
- `core/launchers/agent-launcher.sh` (Claude sandbox prep: cp instead of symlink)
- `core/skills/memory-oracle/scripts/install_memory_hook.py` (new --settings-path arg)
- `scripts/install.sh` (memory seat template prep)
- 6 tests (listed in delivery)

Focus:
1. **seat_skill_mapping.py**: mapping correctness — planner→planner, memory→memory-oracle, ancestor→clawseat-ancestor, builder/reviewer/qa/designer→clawseat (placeholder); `-1/-2` suffix handling; SHARED_SKILLS inclusion
2. **seat_claude_template.py**: does `write_engineer()` correctly trigger template prep? Is the template truly isolated (no fallback to user-level)?
3. **agent-launcher.sh Claude branch**: are `.claude/skills` and `.claude/settings.json` **real** (not symlinks)? Does the launcher auto-regenerate template if missing (backward compat)?
4. **agent_admin_session.py Part A**: is the `codex+api+xcode-best → --auth xcode` mapping correct? Does launcher rc propagate?
5. **install_memory_hook.py**: does `--settings-path` correctly target template dir? Does memory seat still get Stop-hook when launched?
6. **CROSS-CUT**: round-3b and round-3a both modified `agent-launcher.sh` — do their edits conflict? Run `git diff` on the file vs base, verify both edits coexist cleanly.
7. Any broken-invariant risk: existing installs (pre-template-copy) starting a Claude seat — does launcher's auto-regenerate path work from first principles?

## Lane 3 — Round-4: sub-agent fan-out rule (docs-only)

**Delivery**: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND4-SUBAGENT-FANOUT.md`
**Task spec**: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/TASK-ROUND4-SUBAGENT-FANOUT-RULE.md`

Files to review:
- `core/skills/gstack-harness/SKILL.md` (new Design rule + Load-by-task)
- `core/skills/gstack-harness/references/sub-agent-fan-out.md` (NEW)
- `core/skills/gstack-harness/references/dispatch-playbook.md` (new Fan-out hint section)
- `tests/test_gstack_harness_skill_has_fan_out_rule.py`

Focus:
1. Is the Design rule text accurate + in the right section?
2. Does `sub-agent-fan-out.md` cover trigger rules, pattern, anti-patterns, examples, checklist?
3. Does `dispatch-playbook.md` section include the template objective line?
4. Is the test asserting marker strings that would fail if someone deleted content?

---

## Per-lane deliverable

For each lane, write a section in `/Users/ywf/ClawSeat/.agent/ops/install-nonint/REVIEW-ROUND3-ROUND4.md`:

```markdown
## Lane N — <title>
- Verdict: APPROVED | CHANGES_REQUESTED | BLOCKED
- Scope reviewed: <files verified via git diff>
- Findings: (level + file:line + issue)
- Tests run: <pytest command + result>
- Open questions for planner
```

## Aggregate verdict

At the bottom of `REVIEW-ROUND3-ROUND4.md`, write a final section:

```markdown
## Aggregate verdict
- Lane 1 (3a): <verdict>
- Lane 2 (3b): <verdict>
- Lane 3 (4): <verdict>
- Cross-cut check (shared `agent-launcher.sh` across 3a/3b): <pass|fail>
- Overall: APPROVED_FOR_COMMIT | CHANGES_REQUESTED | BLOCKED
- If CHANGES_REQUESTED: list the minimum viable fix set
```

---

## Constraints

- **READ-ONLY review**. Do NOT patch code; if you find issues, report them as Findings, not fixes.
- Run the delivery-claimed tests yourself to verify: don't take claimed "45 passed" on trust — re-run at least the key new tests
- Use `git diff main...HEAD -- <file>` to see what changed vs base. If a file is unchanged, note as no-op.
- Submit verdict via `send-and-verify.sh --project install reviewer` completion OR write the REVIEW file directly

## Signal completion

When the REVIEW-ROUND3-ROUND4.md file is written with all 3 lanes + aggregate, echo:

`REVIEW_DONE`
