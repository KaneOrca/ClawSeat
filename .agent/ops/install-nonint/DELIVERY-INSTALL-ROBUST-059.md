# DELIVERY — INSTALL-ROBUST-059

## Summary

Implemented the install-time robustness fixes from `INSTALL-ROBUST-059`:

- Q1: tmux session lifecycle no longer dies between launcher return and `configure_tmux_session_display`.
- Q2: repeat installs now short-circuit on `phase=ready` unless the operator explicitly asks to rebuild.
- Q3: provider selection can be driven non-interactively with candidate index selection.

The merged RCA remains [RCA-INSTALL-ROBUST-058-059.md](/Users/ywf/ClawSeat/.agent/ops/install-nonint/RCA-INSTALL-ROBUST-058-059.md).

## Changes

- [scripts/install.sh](/Users/ywf/ClawSeat/scripts/install.sh)
  - Added `--reinstall` and `--force` aliases.
  - Step 1 now exits immediately when `~/.agents/tasks/<project>/STATUS.md` already says `phase=ready`.
  - Added `--provider <n>` / `CLAWSEAT_INSTALL_PROVIDER=<n>` candidate selection for noninteractive runs.
  - Added a tmux survival probe before display configuration so a vanished session fails with a focused diagnostic.
  - Updated the generated operator guide to point restart flows at `--reinstall`.
- [core/launchers/agent-launcher.sh](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh)
  - `detach-on-destroy off` now gets chained into the tmux create path.
  - Reused sessions are also forced back to `detach-on-destroy off`.
- [docs/INSTALL.md](/Users/ywf/ClawSeat/docs/INSTALL.md)
  - Documented `phase=ready` early-exit behavior.
  - Documented noninteractive provider candidate selection.
- Tests
  - Added [tests/test_install_seat_session_survives_create.py](/Users/ywf/ClawSeat/tests/test_install_seat_session_survives_create.py)
  - Added [tests/test_install_phase_ready_early_exit.py](/Users/ywf/ClawSeat/tests/test_install_phase_ready_early_exit.py)
  - Added [tests/test_install_provider_noninteractive.py](/Users/ywf/ClawSeat/tests/test_install_provider_noninteractive.py)
  - Updated [tests/test_install_isolation.py](/Users/ywf/ClawSeat/tests/test_install_isolation.py) tmux stub to normalize `=session` prefixes.
  - Updated [tests/test_install_memory_singleton.py](/Users/ywf/ClawSeat/tests/test_install_memory_singleton.py) tmux stub to use registry-based `has-session` semantics.

## 顺手修了

- `tests/test_install_isolation.py` 的 tmux stub 原先没有把 `=session` 前缀归一化，导致新加的 `tmux has-session -t "=name"` 存活探测在测试里误判失败。
- `tests/test_install_memory_singleton.py` 的 tmux stub 原先只认识 `machine-memory-claude`，新加的 ancestor 存活探测把它暴露出来，所以顺手补成了 registry 语义。

根因是测试桩没有贴近真实 tmux 语义，而不是生产逻辑本身有回归。影响范围仅限测试 harness。

## Patch 历程

- 1st pass: 先把 `phase=ready` 检测做成 `return 0`，随后在回归里发现主流程仍然继续往下跑。
- 2nd pass: 改成真正的 `exit 0`，让重复安装在 Step 1 完整短路。
- 3rd pass: 补齐 tmux 测试桩的 `=session` 归一化，并把 memory singleton 的 stub 改成 registry 语义，修平新旧测试的行为差异。
- 4th pass: 按 058 RCA 的 Q4 补上 sandbox GUI gate。`open_iterm_window()` 在 sandbox/headless 调用里把前置 iTerm fail 改成 `WARN + skip`，并让 Step 9 ancestor focus 跟随 `GRID_WINDOW_ID` 做 best-effort。

## Verification

- `bash -n scripts/install.sh`
- `bash -n core/launchers/agent-launcher.sh`
- `python3 -m py_compile tests/test_install_isolation.py tests/test_install_seat_session_survives_create.py tests/test_install_phase_ready_early_exit.py tests/test_install_provider_noninteractive.py tests/test_install_memory_singleton.py`
- `pytest tests/test_install_seat_session_survives_create.py tests/test_install_phase_ready_early_exit.py tests/test_install_provider_noninteractive.py tests/test_install_lazy_panes.py tests/test_install_seat_session_detach_on_destroy.py tests/test_install_auto_kickoff.py tests/test_install_memory_singleton.py -q` -> `23 passed`
- `pytest tests/test_install_isolation.py -q` -> `3 passed`
- `git diff --check`
- `markdownlint` not available in this workspace

## Risk / Impact

- `phase=ready` now requires `--reinstall` or `--force` for a deliberate rebuild. That is intentional idempotence, but it changes the operator flow for repeat installs.
- `--provider <n>` selects from the detected provider list only; explicit `--provider minimax|ark|anthropic_console|custom_api` still forces a specific mode.
- The launcher tmux change is narrow: it only moves `detach-on-destroy off` earlier and re-applies it when reusing an existing session.

No commit.
