## Lane 1 — Round-3a: wait-for-seat retire + launcher xcode config
- Verdict: CHANGES_REQUESTED
- Scope reviewed: `scripts/wait-for-seat.sh`, `core/launchers/agent-launcher.sh`, `core/skills/clawseat-ancestor/SKILL.md`, `core/templates/ancestor-brief.template.md`, `tests/test_wait_for_seat_persistent_reattach.py`, `tests/test_wait_for_seat_trust_detection.py`, `tests/test_launcher_codex_xcode_fallback.py`
- Findings:
  - Medium — `main...HEAD` does not carry the delivered Part A/Part B changes. The delivery claims the 1-arg form was retired and the xcode `config.toml` render landed, but `git diff main...HEAD -- scripts/wait-for-seat.sh core/launchers/agent-launcher.sh tests/test_launcher_codex_xcode_fallback.py` does not contain those changes. The stronger implementation exists only in the dirty worktree, e.g. [scripts/wait-for-seat.sh](/Users/ywf/ClawSeat/scripts/wait-for-seat.sh:16) and [core/launchers/agent-launcher.sh](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh:860). As reviewed against the requested branch diff, this lane is not ready to land.
  - Medium — the committed test coverage in `main...HEAD` is weaker than the delivery claims. The current worktree test file now checks `xcodeapi` config rendering and symlink replacement at [tests/test_launcher_codex_xcode_fallback.py](/Users/ywf/ClawSeat/tests/test_launcher_codex_xcode_fallback.py:90), but those assertions are not present in the committed review diff.
- Tests run:
  - `pytest /Users/ywf/ClawSeat/tests/test_wait_for_seat_persistent_reattach.py /Users/ywf/ClawSeat/tests/test_wait_for_seat_trust_detection.py /Users/ywf/ClawSeat/tests/test_launcher_codex_xcode_fallback.py -q`
    - Result: `7 passed`
- Open questions for planner:
  - Should this lane be re-reviewed only after the delivery is committed so `git diff main...HEAD` contains the actual retirement/config changes?

## Lane 2 — Round-3b: template-copy architecture + start-engineer fix
- Verdict: CHANGES_REQUESTED
- Scope reviewed: `core/scripts/agent_admin.py`, `core/scripts/agent_admin_session.py`, `core/scripts/agent_admin_store.py`, `core/scripts/seat_skill_mapping.py`, `core/scripts/seat_claude_template.py`, `core/launchers/agent-launcher.sh`, `core/skills/memory-oracle/scripts/install_memory_hook.py`, `scripts/install.sh`, `tests/test_agent_admin_session_isolation.py`, `tests/test_agent_admin_start_engineer_codex_mapping.py`, `tests/test_launcher_claude_home_seed.py`, `tests/test_seat_template_populated_after_profile_create.py`, `tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py`, `tests/test_install_isolation.py`
- Findings:
  - Medium — most of Part B is not in the requested review range. `git diff --name-only main...HEAD` for the lane-2 file set only includes `core/launchers/agent-launcher.sh`, `core/scripts/agent_admin.py`, `core/scripts/agent_admin_session.py`, `scripts/install.sh`, `tests/test_agent_admin_session_isolation.py`, `tests/test_install_isolation.py`, and `tests/test_launcher_claude_home_seed.py`. The key template-copy files called out by the delivery, including [core/scripts/seat_skill_mapping.py](/Users/ywf/ClawSeat/core/scripts/seat_skill_mapping.py:1), [core/scripts/seat_claude_template.py](/Users/ywf/ClawSeat/core/scripts/seat_claude_template.py:1), [core/skills/memory-oracle/scripts/install_memory_hook.py](/Users/ywf/ClawSeat/core/skills/memory-oracle/scripts/install_memory_hook.py:1), [tests/test_agent_admin_start_engineer_codex_mapping.py](/Users/ywf/ClawSeat/tests/test_agent_admin_start_engineer_codex_mapping.py:1), [tests/test_seat_template_populated_after_profile_create.py](/Users/ywf/ClawSeat/tests/test_seat_template_populated_after_profile_create.py:1), and [tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py](/Users/ywf/ClawSeat/tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py:1), are untracked/working-tree only.
  - High — the current worktree does not match the lane spec’s stated mapping. The task asked for placeholder mapping `builder/reviewer/qa/designer -> clawseat`, but [core/scripts/seat_skill_mapping.py](/Users/ywf/ClawSeat/core/scripts/seat_skill_mapping.py:16) maps them to dedicated `builder` / `reviewer` / `qa` / `designer` skills instead.
  - High — the claimed targeted test sweep does not reproduce. Re-running the delivery’s lane-2 test command fails in [tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py](/Users/ywf/ClawSeat/tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py:74) because the reviewer sandbox now contains an unexpected `reviewer` skill directory, which follows directly from the mapping in [core/scripts/seat_skill_mapping.py](/Users/ywf/ClawSeat/core/scripts/seat_skill_mapping.py:17).
  - Low — the memory Stop-hook logic now has two sources of truth: hardcoded template rendering in [core/scripts/seat_claude_template.py](/Users/ywf/ClawSeat/core/scripts/seat_claude_template.py:34) and separate mutation logic in [core/skills/memory-oracle/scripts/install_memory_hook.py](/Users/ywf/ClawSeat/core/skills/memory-oracle/scripts/install_memory_hook.py:46). It is currently idempotent, but drift risk is real.
- Tests run:
  - `pytest /Users/ywf/ClawSeat/tests/test_agent_admin_session_isolation.py /Users/ywf/ClawSeat/tests/test_agent_admin_start_engineer_codex_mapping.py /Users/ywf/ClawSeat/tests/test_launcher_claude_home_seed.py /Users/ywf/ClawSeat/tests/test_seat_template_populated_after_profile_create.py /Users/ywf/ClawSeat/tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py /Users/ywf/ClawSeat/tests/test_install_memory_singleton.py /Users/ywf/ClawSeat/tests/test_install_isolation.py /Users/ywf/ClawSeat/tests/test_project_bootstrap_repo_template.py -q`
    - Result: `1 failed, 39 passed`
- Open questions for planner:
  - Is the intended design still placeholder mapping to `clawseat`, or has the lane silently expanded to dedicated `builder/reviewer/qa/designer` skills?
  - Should review gate on the committed `main...HEAD` diff only, or on the dirty worktree delivery snapshot?

## Lane 3 — Round-4: sub-agent fan-out rule docs
- Verdict: CHANGES_REQUESTED
- Scope reviewed: `core/skills/gstack-harness/SKILL.md`, `core/skills/gstack-harness/references/sub-agent-fan-out.md`, `core/skills/gstack-harness/references/dispatch-playbook.md`, `tests/test_gstack_harness_skill_has_fan_out_rule.py`
- Findings:
  - Medium — the rule text is internally inconsistent. [core/skills/gstack-harness/references/sub-agent-fan-out.md](/Users/ywf/ClawSeat/core/skills/gstack-harness/references/sub-agent-fan-out.md:9) says fan-out is required if any listed trigger is true, but the receiving-seat checklist later says to fan out only if any two checklist items are yes at [core/skills/gstack-harness/references/sub-agent-fan-out.md](/Users/ywf/ClawSeat/core/skills/gstack-harness/references/sub-agent-fan-out.md:136). That ambiguity blocks approval for a policy doc.
  - Medium — the regression test is too weak for the claimed guardrail. [tests/test_gstack_harness_skill_has_fan_out_rule.py](/Users/ywf/ClawSeat/tests/test_gstack_harness_skill_has_fan_out_rule.py:10) only asserts marker headings/phrases; deleting the receiving-seat checklist or the quoted dispatch objective line would still leave the test passing.
  - Medium — as with Lane 1, the delivery is not committed. `git diff main...HEAD` for the lane-3 file set is empty; the reviewed content exists only in the worktree.
- Tests run:
  - `pytest /Users/ywf/ClawSeat/tests/test_gstack_harness_skill_has_fan_out_rule.py -q`
    - Result: `1 passed`
- Open questions for planner:
  - Which rule is intended to be authoritative: “any trigger is true” or “any two checklist answers are yes”?

## Aggregate verdict
- Lane 1 (3a): CHANGES_REQUESTED
- Lane 2 (3b): CHANGES_REQUESTED
- Lane 3 (4): CHANGES_REQUESTED
- Cross-cut check (shared `agent-launcher.sh` across 3a/3b): pass
- Overall: CHANGES_REQUESTED
- If CHANGES_REQUESTED: list the minimum viable fix set
  - Commit the delivered lane files so `git diff main...HEAD` matches what was asked to be reviewed.
  - Lane 2: reconcile `seat_skill_mapping.py` with the approved architecture. Either restore placeholder mapping to `clawseat`, or update the task/delivery/tests to the dedicated-skill design and make the targeted suite pass.
  - Lane 2: fix the failing targeted test sweep so the claimed command reproduces cleanly.
  - Lane 3: make the fan-out policy internally consistent and strengthen the regression test to assert the actual required guidance, not just section markers.
