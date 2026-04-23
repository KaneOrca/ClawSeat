# DELIVERY-ROUND3-XCODE-CONFIG-AND-1ARG-RETIRE

Date: 2026-04-24
Repo: `/Users/ywf/ClawSeat`
Branch: `experimental`
Commit: not created
Task: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/TASK-ROUND3A-CODEX-XCODE.md`

## Scope Completed

Completed both Round-3a parts:

1. Retired the `wait-for-seat.sh` 1-arg interface
2. Fixed launcher `codex --auth xcode` config rendering

## Part A — wait-for-seat.sh 1-arg retirement

Changes:

- `scripts/wait-for-seat.sh`
  - usage now advertises only `wait-for-seat.sh <project> <seat>`
  - 1-arg invocation now exits with code `2` and a direct migration error:
    - `error: 1-arg form is retired; rerun as: ... <project> <seat>`
  - internal resolution path is now simplified around the 2-arg contract only

- Docs updated to match the retired interface:
  - `core/skills/clawseat-ancestor/SKILL.md`
  - `core/templates/ancestor-brief.template.md`

- Tests updated:
  - `tests/test_wait_for_seat_persistent_reattach.py`
  - `tests/test_wait_for_seat_trust_detection.py`
  - added explicit regression coverage that the retired 1-arg form is rejected

Result:

- The round-2 open question is now closed by contract, not by accidental partial support.

## Part B — launcher xcode config.toml render

Changes:

- `core/launchers/agent-launcher.sh`
  - in the Codex `xcode` auth path, launcher now removes any existing/symlinked `"$CODEX_HOME/config.toml"` before rendering
  - writes a fresh config with:
    - `model_provider = "xcodeapi"`
    - `model = "gpt-5.4"`
    - `[model_providers.xcodeapi]`
    - `base_url = "<provider default xcode-best url>"`
    - `wire_api = "responses"`
    - `experimental_bearer_token = "$OPENAI_API_KEY"`
  - keeps the Round-2 Codex YOLO flag behavior intact

Result:

- `--auth xcode` no longer depends on ambient/shared user Codex config.
- xcode.best token + base URL are now rendered into the runtime-local `config.toml`, which fixes the observed `api.openai.com` / 401 failure mode.

## Files Changed

- `scripts/wait-for-seat.sh`
- `core/launchers/agent-launcher.sh`
- `core/skills/clawseat-ancestor/SKILL.md`
- `core/templates/ancestor-brief.template.md`
- `tests/test_wait_for_seat_persistent_reattach.py`
- `tests/test_wait_for_seat_trust_detection.py`
- `tests/test_launcher_codex_xcode_fallback.py`

## Tests

Targeted validation:

- `pytest /Users/ywf/ClawSeat/tests/test_wait_for_seat_persistent_reattach.py /Users/ywf/ClawSeat/tests/test_wait_for_seat_trust_detection.py /Users/ywf/ClawSeat/tests/test_launcher_codex_xcode_fallback.py -q`
  - `7 passed`

Regression sweep:

- `pytest /Users/ywf/ClawSeat/tests/test_install_lazy_panes.py /Users/ywf/ClawSeat/tests/test_window_open_grid.py /Users/ywf/ClawSeat/tests/test_agent_admin_window_reseed.py /Users/ywf/ClawSeat/tests/test_install_auto_kickoff.py /Users/ywf/ClawSeat/tests/test_install_isolation.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_spawn49.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_no_retry_loop.py /Users/ywf/ClawSeat/tests/test_ancestor_skill_seat_tui_lifecycle.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_seat_tui_lifecycle.py /Users/ywf/ClawSeat/tests/test_launch_permissions.py /Users/ywf/ClawSeat/tests/test_launcher_codex_xcode_fallback.py /Users/ywf/ClawSeat/tests/test_wait_for_seat_persistent_reattach.py /Users/ywf/ClawSeat/tests/test_wait_for_seat_trust_detection.py -q`
  - `48 passed`

## Reviewer Handoff

- Review summary sent via `core/shell-scripts/send-and-verify.sh`
- Target session: `agent-launcher-codex-chatgpt-20260423-230652`

## Notes

- No end-to-end `scripts/install.sh` run was performed, per task constraint.
- No commit was created.
