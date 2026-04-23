# DELIVERY: Round-5 Role Skill Review & Mapping Update

**Diagnoser**: gemini TUI session
**Date**: Friday, April 24, 2026

## 1. Lane A: Content Review Critique

### Builder Skill (core/skills/builder/SKILL.md)
**verdict**: GOOD. The `SKILL.md` for `builder` is exceptionally well-structured and strictly adheres to all specified criteria. It defines a clear identity as an implementation specialist, explicitly excluding reviewer-like approvals (`Verdict: APPROVED`) and planning responsibilities, thereby preventing role overlap. The upstream and delivery sections accurately reflect the canonical patterns, specifically utilizing `complete_handoff.py` with the correct `--source builder --target planner` flags for both routine completion and escalation (`status=blocked`). The work pattern is concrete, mandating the fan-out rule for independent sub-tasks and emphasizing the requirement for regression sweeps and test coverage.

### Reviewer Skill (core/skills/reviewer/SKILL.md)
**verdict**: MINOR_EDITS. The `SKILL.md` for the `reviewer` role is fundamentally sound and correctly defines its non-modifying identity and upstream integration, but it required updates to align its delivery protocol with the project's canonical standards. Specifically, the `Verdict` values were updated from `APPROVED/CHANGES_REQUESTED/BLOCKED` to the mandatory `PASS/FAIL/MINOR_REVISIONS/MAJOR_REWRITE`. Additionally, guidance was added for handling ambiguous acceptance criteria via the escalation path and explicit metadata checking for handoff JSON.

### QA Skill (core/skills/qa/SKILL.md)
**verdict**: MINOR_EDITS. The `qa` skill definition provides a clear identity centered on test execution and result honesty, effectively prohibiting test authorship and code changes. Edits were applied to add an explicit **Escalation** section for environment-level failures and TODO ambiguity, and the **Upstream** section was updated to include the "handoff JSON" alongside `TODO.md` to align with the canonical entry pattern. A "tiny fix to execution script" exception was also added to the identity constraints to handle realistic operational needs.

### Designer Skill (core/skills/designer/SKILL.md)
**verdict**: GOOD. The `SKILL.md` for the `designer` role is exceptionally well-defined, providing a crystal-clear distinction between UI/UX tasks and the `builder`'s backend responsibilities. It correctly identifies the canonical entry point and delivery path. A minor improvement was applied to explicitly mention the handoff JSON file alongside `TODO.md` in the Upstream section to perfectly mirror the canonical pattern. The work pattern and anti-patterns emphasize visual evidence as a hard requirement, ensuring high-quality UI/UX delivery.

## 2. Lane B: Surgical Edits Applied

- **core/skills/reviewer/SKILL.md**:
    - Updated `Verdict` canonical values to `PASS/FAIL/MINOR_REVISIONS/MAJOR_REWRITE`.
    - Added instruction for handling ambiguous criteria via escalation.
    - Updated Upstream to include handoff JSON.
    - Updated step 4 of work pattern to use `FAIL`.
- **core/skills/qa/SKILL.md**:
    - Added `Escalation` section.
    - Updated `Upstream` to include handoff JSON.
    - Added "tiny fix to execution script" exception to identity constraints.
- **core/skills/designer/SKILL.md**:
    - Updated `Upstream` to include handoff JSON.

## 3. Lane C: Mapping Update

### core/scripts/seat_skill_mapping.py

**Before**:
```python
SEAT_SKILL_MAP: Final[dict[str, str]] = {
    "ancestor": "clawseat-ancestor",
    "planner": "planner",
    "memory": "memory-oracle",
    "builder": "clawseat",
    "reviewer": "clawseat",
    "qa": "clawseat",
    "designer": "clawseat",
}
```

**After**:
```python
SEAT_SKILL_MAP: Final[dict[str, str]] = {
    "ancestor": "clawseat-ancestor",
    "planner": "planner",
    "memory": "memory-oracle",
    "builder": "builder",
    "reviewer": "reviewer",
    "qa": "qa",
    "designer": "designer",
}
```

## 4. Test Results

- Updated `tests/test_seat_template_populated_after_profile_create.py` to assert `reviewer` skill presence.
- Added `tests/test_seat_skill_mapping_audit.py` for direct mapping verification.
- **Result**: `4 passed` (including direct mapping check and template population check).

ROUND5_ROLE_SKILLS_DONE
