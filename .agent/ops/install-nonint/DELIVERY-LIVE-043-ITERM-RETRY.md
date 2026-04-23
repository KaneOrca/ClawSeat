# DELIVERY — LIVE-043 iTerm Connect Resilience

## Summary

Fixed the live smoketest blocker that was stopping `scripts/install.sh` at Step 7 while opening the native iTerm grid.

The failure mode was:

- `core/scripts/iterm_panes_driver.py` could not connect to iTerm2 after the app had been restarted into a stale API state.
- `scripts/install.sh` used `tmux set-option -t "=$session"` for tmux session display config, but `tmux set-option` on this host rejects the exact-match `=` target form even when `has-session` accepts it.

The end result was that the installer reached `Step 7: open six-pane iTerm grid`, then died before `Step 9.5`.

## Changes

- [core/scripts/iterm_panes_driver.py](/Users/ywf/ClawSeat/core/scripts/iterm_panes_driver.py)
  - Switched the entrypoint to `iterm2.run_until_complete(_main, retry=True)` so the SDK can retry a transient iTerm connection miss instead of failing immediately.
  - Kept the driver bounded by the caller’s wall-clock timeout so it cannot hang forever.

- [scripts/install.sh](/Users/ywf/ClawSeat/scripts/install.sh)
  - Added `ITERM_DRIVER_TIMEOUT_SECONDS=30`.
  - Wrapped the iTerm driver invocation in `timeout ...` so a bad iTerm state fails with a bounded diagnostic instead of hanging the installer.
  - Fixed `configure_tmux_session_display()` to target the plain session name instead of `=session`, which `tmux set-option` rejected.

- Tests
  - Updated [tests/test_seat_session_status_line.py](/Users/ywf/ClawSeat/tests/test_seat_session_status_line.py)
  - Updated [tests/test_install_phase_ready_early_exit.py](/Users/ywf/ClawSeat/tests/test_install_phase_ready_early_exit.py)
  - Updated [tests/test_install_provider_noninteractive.py](/Users/ywf/ClawSeat/tests/test_install_provider_noninteractive.py)
  - Updated [tests/test_install_seat_session_detach_on_destroy.py](/Users/ywf/ClawSeat/tests/test_install_seat_session_detach_on_destroy.py)
  - Updated [tests/test_install_seat_session_survives_create.py](/Users/ywf/ClawSeat/tests/test_install_seat_session_survives_create.py)
  - Added a static source assertion in [tests/test_iterm_panes_driver.py](/Users/ywf/ClawSeat/tests/test_iterm_panes_driver.py) to lock in `retry=True`

## 顺手修了

- `tmux set-option -t "=$session"` looked symmetrical with `has-session`, but on this host it is not valid for `set-option`.
- Root cause: the tmux exact-match `=` prefix is accepted by `has-session`, but `set-option` expects a plain session target.
- Risk/impact: only the install-time tmux display configuration path changed; session creation, launch, and attach semantics are unchanged.

## Verification

- `bash -n scripts/install.sh`
- `python3 -m py_compile core/scripts/iterm_panes_driver.py`
- `pytest tests/test_iterm_panes_driver.py tests/test_install_provider_noninteractive.py tests/test_install_seat_session_detach_on_destroy.py tests/test_install_seat_session_survives_create.py tests/test_seat_session_status_line.py -q` -> `51 passed`
- Live smoketest on `install-runner` reached:
  - `Step 7: open six-pane iTerm grid`
  - `Step 8: ensure memory singleton daemon`
  - `Step 9.5: auto-send Phase-A kickoff prompt`
  - final banner: `ClawSeat install complete`

## Patch 历程

- 1st pass: added `retry=True` to the iTerm driver to recover a transient connection miss.
- 2nd pass: observed that the driver could wait too long when iTerm was still stale, so the install script now wraps the driver in a bounded `timeout`.
- 3rd pass: fixed tmux `set-option` to use the plain session name target after reproducing the `no such session: =...` failure directly.

No commit.
