# DELIVERY — MULTI-IDENTITY-056 CHUNK 6

## Summary

Added the migration guardrail for projects that are marked `per-project` but have not yet been initialized with a project tool root.

This keeps the v0.7 `shared-real-home` fallback intact while making the v0.8 migration path explicit: initialize the project tool root first, then start the seat.

## Changes

- [core/scripts/agent_admin_session.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py)
  - `start_engineer()` now checks whether the project tool root exists when `tools_isolation=per-project`.
  - If the root is missing, it prints a warning with the exact remediation command:
    - `agent_admin project init-tools <project> --from real-home`
  - The warning is emitted before the runtime launch attempt, so the operator gets a clear migration signal instead of a silent fallback.

- [core/scripts/agent_admin_resolve.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_resolve.py)
  - Continues to surface `CLAWSEAT_TOOLS_ISOLATION` and `CLAWSEAT_PROJECT_TOOL_ROOT` for per-project runtime start.
  - Shared-real-home remains the default compatibility mode when the binding does not opt into isolation.

- [core/launchers/agent-launcher.sh](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh)
  - The seed helper still returns early when the runtime HOME already equals the real HOME.
  - This preserves the compatibility path and avoids self-loop seeding during migration.

- [tests/test_agent_admin_session_project_tool_seed.py](/Users/ywf/ClawSeat/tests/test_agent_admin_session_project_tool_seed.py)
  - Covers the missing-root warning path.
- [tests/test_v07_to_v08_migration.py](/Users/ywf/ClawSeat/tests/test_v07_to_v08_migration.py)
  - Adds the standalone v0.7 -> v0.8 migration coverage requested in the TODO: v1/v2 binding upgrade, missing project-root warning, and bootstrap rebind preservation.
- [tests/test_multi_identity_isolation.py](/Users/ywf/ClawSeat/tests/test_multi_identity_isolation.py)
  - Adds the standalone multi-project isolation coverage requested in the TODO: separate per-project tool roots, switch-identity locality, and source-project copy-not-move behavior.

## 顺手修了

- The migration path now produces an explicit operator instruction instead of hiding behind the old shared-home fallback.
- Root cause: a per-project binding without a project-local tool root is an incomplete migration, not a valid steady state.
- Risk/impact: low to moderate. The old path still works, but the warning makes the required migration step visible.

## Verification

- `python3 -m py_compile /Users/ywf/ClawSeat/core/scripts/agent_admin_session.py`
- `pytest /Users/ywf/ClawSeat/tests/test_agent_admin_session_project_tool_seed.py /Users/ywf/ClawSeat/tests/test_v07_to_v08_migration.py /Users/ywf/ClawSeat/tests/test_multi_identity_isolation.py -q` -> covered in the shared verification run

## Patch 历程

- 1st pass: detect the missing project tool root.
- 2nd pass: print the explicit init-tools command as the remediation.
- 3rd pass: keep the shared-real-home fallback intact for compatibility projects.

No commit.
