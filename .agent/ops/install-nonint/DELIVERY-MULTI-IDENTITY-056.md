# DELIVERY — MULTI-IDENTITY-056

Status: complete, not committed.

## Summary

This batch delivered per-project user-tool isolation for `ClawSeat` without changing the global `real_user_home()` SSOT.

The new steady state is:

- `shared-real-home` remains the compatibility default.
- `per-project` switches a project to `~/.agent-runtime/projects/<project>/...`.
- `project init-tools` initializes that project-scoped tool root.
- `project switch-identity` rewrites the project binding and reseeds existing seats.
- launcher/session code now honors `CLAWSEAT_PROJECT` and `CLAWSEAT_TOOLS_ISOLATION`.

## Chunks

### Chunk 1

- Upgraded `PROJECT_BINDING.toml` to schema v3 in [core/lib/project_binding.py](/Users/ywf/ClawSeat/core/lib/project_binding.py).
- Added v3 schema coverage in [tests/test_project_binding_schema_v3.py](/Users/ywf/ClawSeat/tests/test_project_binding_schema_v3.py).
- Preserved legacy `feishu_bot_account` read compatibility and defaulted older bindings to `shared-real-home`.

### Chunk 2

- Added [core/lib/project_tool_root.py](/Users/ywf/ClawSeat/core/lib/project_tool_root.py).
- The helper resolves `~/.agent-runtime/projects/<project>` and the nested subpath helper used by CLI and runtime code.

### Chunk 3

- Added `agent_admin project init-tools <project> [--from real-home|empty] [--source-project ...] [--tools ...] [--dry-run]`.
- Implemented in [core/scripts/agent_admin_crud.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_crud.py) and exposed through [core/scripts/agent_admin_parser.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py) and [core/scripts/agent_admin.py](/Users/ywf/ClawSeat/core/scripts/agent_admin.py).
- Added tests in [tests/test_agent_admin_project_init_tools.py](/Users/ywf/ClawSeat/tests/test_agent_admin_project_init_tools.py).

### Chunk 4

- Patched [core/scripts/agent_admin_session.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py) to:
  - read project binding isolation mode
  - seed sandbox HOME from project tool root when `per-project`
  - export `CLAWSEAT_PROJECT`, `CLAWSEAT_TOOLS_ISOLATION`, and `CLAWSEAT_PROJECT_TOOL_ROOT` to launcher subprocesses
  - emit a migration warning when a `per-project` binding exists but the project tool root has not been initialized yet
- Patched [core/scripts/agent_admin_resolve.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_resolve.py) with the same project isolation env wiring for preview/effective-launch flows.
- Patched [core/launchers/agent-launcher.sh](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh) so `seed_user_tool_dirs` can seed from per-project roots and `prepare_codex_home` / `prepare_gemini_home` consume the runtime's project-local tool state.
- Patched [scripts/install.sh](/Users/ywf/ClawSeat/scripts/install.sh) to pass `CLAWSEAT_PROJECT` into launcher invocations.
- Added tests in [tests/test_agent_admin_session_project_tool_seed.py](/Users/ywf/ClawSeat/tests/test_agent_admin_session_project_tool_seed.py) and [tests/test_launcher_project_tool_seed.py](/Users/ywf/ClawSeat/tests/test_launcher_project_tool_seed.py).

### Chunk 5

- Added `agent_admin project switch-identity <project> --tool feishu|gemini|codex --identity ... [--dry-run]`.
- The command updates the binding fields for the chosen identity, flips the project to `per-project`, and reseeds existing seats.
- Added tests in [tests/test_agent_admin_project_switch_identity.py](/Users/ywf/ClawSeat/tests/test_agent_admin_project_switch_identity.py).

### Chunk 6

- Kept legacy bindings compatible by defaulting missing `tools_isolation` to `shared-real-home` and normalizing older versions to v3.
- Added a migration warning path for `per-project` bindings that have not had `project init-tools` run yet.
- The warning points operators at the canonical init command instead of silently guessing a copy path.
- Added the explicit TODO-mandated migration/isolation suites:
  - [tests/test_v07_to_v08_migration.py](/Users/ywf/ClawSeat/tests/test_v07_to_v08_migration.py)
  - [tests/test_multi_identity_isolation.py](/Users/ywf/ClawSeat/tests/test_multi_identity_isolation.py)

## Behavioral Notes

- Existing v0.7 projects keep working in `shared-real-home` mode.
- `project bind` now preserves project tool isolation/account fields when re-binding Feishu metadata.
- Memory remains a machine-level singleton; this work only affects project-scoped user tools.
- `test_v07_to_v08_migration.py` locks the v1/v2 -> v3 runtime upgrade contract and the missing-tool-root migration warning into a standalone suite.
- `test_multi_identity_isolation.py` locks the cross-project isolation contract into a standalone suite so smoke01/smoke02 style identity drift cannot hide inside broader tests.

## Verification

- `bash -n /Users/ywf/ClawSeat/core/launchers/agent-launcher.sh`
- `bash -n /Users/ywf/ClawSeat/scripts/install.sh`
- `python3 -m py_compile` on all touched Python modules
- `pytest ...` on the new and impacted suites -> `53 passed`
- `git diff --check`
- `markdownlint` / `markdownlint-cli2` are not installed in this workspace

## Patch History

- Replaced the old `test_project_binding_schema_v2.py` with v3 coverage.
- Expanded launcher seeding from a single real-home source to an explicit project-root source while preserving the real-home fallback.
- Tightened `project bind` so it no longer resets the new per-project isolation fields on rebind.

## Follow-up Suggestions

1. If the planner wants fully automatic first-launch migration, add a thin wrapper that runs `project init-tools <project> --from real-home` when a `per-project` binding exists but the project root is absent.
2. If the planner wants a debug rollback path, add a `project use-real-home <project>` command that flips `tools_isolation` back to `shared-real-home`.
