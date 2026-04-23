# DELIVERY-CODEX-XCODE-REGRESSIONS

Date: 2026-04-24
Repo: `/Users/ywf/ClawSeat`
Branch: `experimental`
Commit: not created

## Task Input

Requested task file path:

`/Users/ywf/ClawSeat/.agent/ops/install-nonint/TASK-CODEX-XCODE-REGRESSIONS.md`

Result:

- File not present in the worktree at execution time.
- Execution proceeded from the explicit user brief: fix 2 regressions
  - `HIGH` ambiguous alias
  - `MEDIUM` fallback all delete

## Fixes Applied

### 1. HIGH — ambiguous alias removed

Removed the temporary `project-engineer` base alias acceptance from:

- `core/scripts/agent_admin_resolve.py`

Effect:

- `resolve_session()` no longer accepts ambiguous names like `install-designer`
  as a canonical session alias.
- Pane/session recovery must go through explicit canonical resolution.

### 2. MEDIUM — fallback deleted

Removed the remaining base-session fallback from:

- `scripts/wait-for-seat.sh`

Effect:

- `wait-for-seat.sh` now only attaches when `agentctl session-name` resolves a
  canonical session and that exact session exists.
- It no longer falls back to:
  - suffix scanning (`-claude/-codex/-gemini`) from the old implementation
  - exact base-session attach like `spawn49-planner`

## Supporting Adjustments Kept

These changes remain because they are required for the non-fallback path:

- `core/scripts/agent_admin_window.py`
  - grid and `reseed-pane` use explicit `wait-for-seat.sh <project> <seat>`
- `scripts/install.sh`
  - grid payload uses explicit `project + seat`
  - kickoff auto-send active-response detection remains improved
- `core/templates/ancestor-brief.template.md`
- `core/skills/clawseat-ancestor/SKILL.md`
  - documentation stays aligned with canonical pane reseed/session-name flow

## Tests

Passed:

- `pytest tests/test_install_lazy_panes.py tests/test_window_open_grid.py tests/test_agent_admin_window_reseed.py tests/test_install_auto_kickoff.py -q`
  - `26 passed`
- `pytest tests/test_install_isolation.py tests/test_ancestor_brief_spawn49.py tests/test_ancestor_brief_no_retry_loop.py tests/test_ancestor_skill_seat_tui_lifecycle.py tests/test_ancestor_brief_seat_tui_lifecycle.py -q`
  - `7 passed`

Regression coverage added/updated:

- `tests/test_install_lazy_panes.py`
  - canonical attach only
  - no cross-attach to tool-suffix sessions
  - no fallback attach to base session

Regression coverage removed:

- `tests/test_agent_admin_session_name_alias.py`
  - deleted because the alias behavior is now intentionally unsupported

## Review Handoff

Review summary resent to tmux review target via:

- `core/shell-scripts/send-and-verify.sh`

Target session:

- `agent-launcher-codex-chatgpt-20260423-230652`
