# DELIVERY — MULTI-IDENTITY-056 CHUNK 3

## Summary

Added the `agent_admin project init-tools` command so a project can explicitly initialize its project-scoped user-tool state.

The command is the canonical bootstrap path for `per-project` isolation. It can seed from real home, start empty, or copy from another project.

## Changes

- [core/scripts/agent_admin_parser.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py)
  - Added the `project init-tools` CLI surface.
  - Exposed `--from`, `--source-project`, `--tools`, and `--dry-run`.

- [core/scripts/agent_admin_crud.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_crud.py)
  - Implemented `CrudHandlers.project_init_tools()`.
  - Copies the requested tool set into the project-scoped root.
  - Flips the binding to `tools_isolation = "per-project"`.
  - Reseeds any existing engineer seats after initialization.

- [core/scripts/agent_admin.py](/Users/ywf/ClawSeat/core/scripts/agent_admin.py)
  - Wired the parser command into the dispatch path.

- Tests
  - Added [tests/test_agent_admin_project_init_tools.py](/Users/ywf/ClawSeat/tests/test_agent_admin_project_init_tools.py)

## 顺手修了

- The command refuses to guess a seed path when the binding is missing; operators must bind first.
- Root cause: tool initialization needs an explicit project binding so the isolation mode is not inferred from loose filesystem state.
- Risk/impact: this is an intentional explicit bootstrap gate, not a silent fallback.

## Verification

- `python -m pytest /Users/ywf/ClawSeat/tests/test_agent_admin_project_init_tools.py -q` -> `2 passed`
- `python -m py_compile /Users/ywf/ClawSeat/core/scripts/agent_admin_crud.py /Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py /Users/ywf/ClawSeat/core/scripts/agent_admin.py`

## Patch 历程

- 1st pass: added the command surface and the copy-from-real-home path.
- 2nd pass: added the empty-seed and dry-run behaviors.

No commit.
