## Task
- task_id: WINDOW-OPS-054
- target: builder-codex
- repo: /Users/ywf/ClawSeat (experimental)
- scope: add canonical `agent_admin window open-grid <project> [--recover] [--open-memory]`

## 改动清单
- [core/scripts/agent_admin_window.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_window.py)
  - added pure helpers for `open-grid` payload generation and iTerm window probing
  - `build_grid_payload()` now derives the roster from `project.engineers`, keeps ancestor first, skips frontstage overlay seats, and falls back to ancestor-only when the roster is empty
  - `run_iterm_panes_driver()` invokes `core/scripts/iterm_panes_driver.py`
  - `open_grid_window()` implements `--recover` focus/no-redrive and optional `--open-memory`
  - `open_memory_window()` reuses the singleton tmux session when present and skips when the memory seat is missing
- [core/scripts/agent_admin_commands.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_commands.py)
  - added `window_open_grid()` handler
  - project-not-registered now fails with `project not registered: <name>`
- [core/scripts/agent_admin_parser.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py)
  - added `window open-grid` parser with `--recover` and `--open-memory`
- [core/scripts/agent_admin.py](/Users/ywf/ClawSeat/core/scripts/agent_admin.py)
  - wired the new parser hook and top-level wrapper
- [core/templates/ancestor-brief.template.md](/Users/ywf/ClawSeat/core/templates/ancestor-brief.template.md)
  - brief now points ancestor at `agent_admin window open-grid ...`
  - B3.5.0 now tells ancestor to use `--recover` instead of hand-splicing payloads
- [core/skills/clawseat-ancestor/SKILL.md](/Users/ywf/ClawSeat/core/skills/clawseat-ancestor/SKILL.md)
  - added a small window-ops cheat sheet for `open-grid`
- [tests/test_window_open_grid.py](/Users/ywf/ClawSeat/tests/test_window_open_grid.py)
  - new unit tests for payload generation, recover skip, memory payload, not-registered error, and empty-roster fallback
- [tests/test_ancestor_brief_spawn49.py](/Users/ywf/ClawSeat/tests/test_ancestor_brief_spawn49.py)
  - brief assertion updated to include `open-grid`
- [tests/test_ancestor_skill_lark_cli_cheat_sheet.py](/Users/ywf/ClawSeat/tests/test_ancestor_skill_lark_cli_cheat_sheet.py)
  - skill assertion updated to include `open-grid`, `--recover`, and `--open-memory`

## Verification
- `bash -n /Users/ywf/ClawSeat/scripts/install.sh`
- `python3 -m py_compile /Users/ywf/ClawSeat/core/scripts/agent_admin_window.py /Users/ywf/ClawSeat/core/scripts/agent_admin_commands.py /Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py /Users/ywf/ClawSeat/core/scripts/agent_admin.py /Users/ywf/ClawSeat/tests/test_window_open_grid.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_spawn49.py /Users/ywf/ClawSeat/tests/test_ancestor_skill_lark_cli_cheat_sheet.py`
- `pytest /Users/ywf/ClawSeat/tests/test_window_open_grid.py /Users/ywf/ClawSeat/tests/test_project_binding_schema_v2.py /Users/ywf/ClawSeat/tests/test_batch_start_engineer.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_spawn49.py /Users/ywf/ClawSeat/tests/test_ancestor_skill_lark_cli_cheat_sheet.py -q`
  - result: `19 passed`
- `pytest /Users/ywf/ClawSeat/tests/test_monitor_layout_n_panes.py -q`
  - result: `14 passed`
- `git -C /Users/ywf/ClawSeat diff --check`
- `markdownlint` not installed in this workspace

## Patch 历程
- 1. Added the pure iTerm/grid helpers and command plumbing.
- 2. Synchronized the ancestor brief + skill guidance.
- 3. Added focused regression tests and ran the relevant suite.

## Notes
- No changes were made to `scripts/install.sh` or `core/scripts/iterm_panes_driver.py`.
- `--recover` only skips rebuilding when an existing `clawseat-<project>` window is present; it does not bootstrap anything new.
- `--open-memory` only opens the memory iTerm window when the memory tmux session already exists.

