# DELIVERY — MULTI-IDENTITY-056 CHUNK 2

## Summary

Added the project-scoped tool root helper that anchors per-project identity state under `~/.agent-runtime/projects/<project>`.

This is the filesystem primitive that chunk 3+4 build on. It keeps `real_user_home()` as the global SSOT while giving project-scoped code a stable place to read/write tool state.

## Changes

- [core/lib/project_tool_root.py](/Users/ywf/ClawSeat/core/lib/project_tool_root.py)
  - Added `project_tool_root(project, home=None)`.
  - Added `project_tool_subpath(project, subpath, home=None)`.
  - Both helpers validate the project name through `project_binding.validate_project_name()`.

- Tests
  - Added [tests/test_project_tool_root.py](/Users/ywf/ClawSeat/tests/test_project_tool_root.py)

## 顺手修了

- This helper deliberately does not reinterpret `real_user_home()` as project-aware.
- Root cause: multi-identity needs a new project-local layer, not a rewritten global home SSOT.
- Risk/impact: no migration behavior changes yet; this is a pure path helper addition.

## Verification

- `python -m pytest /Users/ywf/ClawSeat/tests/test_project_tool_root.py -q` -> `2 passed`
- `python -m py_compile /Users/ywf/ClawSeat/core/lib/project_tool_root.py`

## Patch 历程

- 1st pass: defined the project root anchor.
- 2nd pass: added the child-path helper so CLI/runtime code does not duplicate path joins.

No commit.
