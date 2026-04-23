# DELIVERY — 056/059 PYTEST CLOSEOUT

## Summary

Ran the requested full-suite verification after the P1 fixes for `MULTI-IDENTITY-056` and `INSTALL-ROBUST-059`.

- Baseline at `b919a9c`: `1747 passed`
- Current tree after this fix round: `1814 passed, 2 xfailed`
- Net delta vs baseline: `+67` passing tests

The first full run surfaced 4 regressions; all 4 were fixed in this round and the second full run was clean.

## Regressions fixed during full run

- [core/skills/memory-oracle/scripts/query_memory.py](/Users/ywf/ClawSeat/core/skills/memory-oracle/scripts/query_memory.py)
  - `cmd_ask()` now returns `rc=2` for deprecated `--ask`, matching the compatibility test contract.
  - `cmd_list()` now ignores `--project` when `--kind event`, so global `events.log` keeps working under project-scoped queries.
- [core/preflight.py](/Users/ywf/ClawSeat/core/preflight.py)
  - Added the required `# silent-ok:` sentinel to the audited `except ...: pass` block.
- [core/scripts/agent_admin_resolve.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_resolve.py)
  - Added `core/lib` to `sys.path` before importing `project_binding` / `project_tool_root`, fixing clean subprocess imports.

## Verification

- `bash -n scripts/install.sh`
- `bash -n core/launchers/agent-launcher.sh`
- `python3 -m py_compile core/scripts/agent_admin_crud.py core/scripts/agent_admin_resolve.py core/preflight.py core/skills/memory-oracle/scripts/query_memory.py tests/test_install_sandbox_gui_skip.py tests/test_v07_to_v08_migration.py tests/test_multi_identity_isolation.py tests/test_launcher_gemini_trust_sandbox_isolation.py`
- `pytest tests/test_install_sandbox_gui_skip.py tests/test_install_lazy_panes.py -q` -> `12 passed`
- `pytest tests/test_v07_to_v08_migration.py tests/test_multi_identity_isolation.py -q` -> `7 passed`
- `pytest tests/test_project_binding_schema_v3.py tests/test_agent_admin_project_init_tools.py tests/test_agent_admin_project_switch_identity.py tests/test_agent_admin_session_project_tool_seed.py -q` -> `13 passed`
- `pytest tests/test_launcher_gemini_trust_seed.py tests/test_launcher_gemini_trust_sandbox_isolation.py tests/test_launcher_project_tool_seed.py tests/test_agent_admin_session_project_tool_seed.py -q` -> `6 passed`
- `pytest tests/test_agent_admin_project_switch_identity.py tests/test_launcher_gemini_trust_seed.py tests/test_launcher_gemini_trust_sandbox_isolation.py tests/test_v07_to_v08_migration.py tests/test_multi_identity_isolation.py -q` -> `14 passed`
- `pytest tests/test_memory_oracle.py::TestCmdAskPromptFile::test_ask_without_profile_returns_error tests/test_memory_query_v2.py::test_kind_event_project_ignored_still_reads_global_log tests/test_silent_except_audit.py::test_all_silent_excepts_have_sentinel tests/test_smoke_coverage.py::test_admin_module_imports_cleanly[agent_admin_resolve] -q` -> `4 passed`
- `pytest tests/ -q` -> `1814 passed, 2 xfailed in 167.26s`
- `git diff --check`

## Notes

- `markdownlint` / `markdownlint-cli2` are not installed in this workspace, so markdown lint could not be run.
- No additional tmux-session cleanup was required after the final full run.
- No commit.
