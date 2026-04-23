# DELIVERY-ROUND2-FALLBACK-AND-YOLO

Date: 2026-04-24
Repo: `/Users/ywf/ClawSeat`
Branch: `experimental`
Commit: not created
Task: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/TASK-CODEX-XCODE-ROUND2.md`

## Scope Completed

Implemented both Round-2 fixes on `experimental`:

1. `scripts/wait-for-seat.sh`
   - Kept `agentctl session-name <seat> --project <project>` as the primary path.
   - Restored suffix fallback only as a guarded last resort after a retry budget.
   - Restricted fallback scan to the fixed suffix set:
     - `claude`
     - `codex`
     - `gemini`
   - Added visible `stderr` WARN on fallback attach.
   - Added periodic degraded `stderr` WARN when neither canonical resolution nor fixed-suffix fallback succeeds.
   - Kept base-session fallback removed; `spawn49-planner` alone is not reattached without canonical resolution.
   - Kept resolver alias rollback untouched; no ambiguous alias bridge was reintroduced.

2. `core/launchers/agent-launcher.sh`
   - Added `--dangerously-bypass-approvals-and-sandbox` to all 4 `exec codex` call sites.
   - Left Claude `--dangerously-skip-permissions` behavior unchanged.

## Files Changed

- `scripts/wait-for-seat.sh`
- `core/launchers/agent-launcher.sh`
- `tests/test_install_lazy_panes.py`
- `tests/test_launcher_codex_xcode_fallback.py`

## Test Coverage

New coverage added:

- `tests/test_install_lazy_panes.py`
  - fixed-suffix fallback attaches after primary budget exhaustion
  - degraded WARN repeats when primary and fallback both fail
- `tests/test_launcher_codex_xcode_fallback.py`
  - all 4 Codex exec sites carry the YOLO flag

Existing coverage strengthened:

- `tests/test_install_lazy_panes.py`
  - canonical primary attach emits no WARN
  - base-session fallback remains forbidden
- `tests/test_launcher_codex_xcode_fallback.py`
  - xcode exec-agent smoke now asserts the launched Codex argv contains the YOLO flag

## Pytest Runs

Per-fix validation:

- `pytest /Users/ywf/ClawSeat/tests/test_install_lazy_panes.py -q`
  - `13 passed`
- `pytest /Users/ywf/ClawSeat/tests/test_launch_permissions.py /Users/ywf/ClawSeat/tests/test_launcher_codex_xcode_fallback.py -q`
  - `9 passed`

Round-2 regression sweep:

- `pytest /Users/ywf/ClawSeat/tests/test_install_lazy_panes.py /Users/ywf/ClawSeat/tests/test_window_open_grid.py /Users/ywf/ClawSeat/tests/test_agent_admin_window_reseed.py /Users/ywf/ClawSeat/tests/test_install_auto_kickoff.py /Users/ywf/ClawSeat/tests/test_install_isolation.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_spawn49.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_no_retry_loop.py /Users/ywf/ClawSeat/tests/test_ancestor_skill_seat_tui_lifecycle.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_seat_tui_lifecycle.py /Users/ywf/ClawSeat/tests/test_launch_permissions.py /Users/ywf/ClawSeat/tests/test_launcher_codex_xcode_fallback.py -q`
  - `43 passed`

## Notes

- `wait-for-seat.sh` now defaults to a 2-second poll, with a 10-poll primary budget and 15-poll degraded WARN interval, matching the Round-2 intent of "primary first, fallback visible, no ambiguity".
- No commit was created.
- Reviewer handoff was sent via `core/shell-scripts/send-and-verify.sh` to `agent-launcher-codex-chatgpt-20260423-230652`.
