# DELIVERY-ROUND3B-TEMPLATE-COPY-AND-START-ENGINEER

Date: 2026-04-24
Repo: `/Users/ywf/ClawSeat`
Branch: `experimental`
Commit: not created
Task: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/TASK-ROUND3B-REVISED-TEMPLATE-COPY.md`

## Scope Completed

Completed both revised Round-3b parts:

1. Fixed `start-engineer` launcher mapping / visibility for `codex + api + xcode-best`
2. Replaced the abandoned runtime symlink/skills-array idea with static per-seat `.claude-template` generation + runtime copy

## Part A — start-engineer mapping + launcher failure visibility

Changes:

- `core/scripts/agent_admin_session.py`
  - maps `codex + api + xcode-best` to launcher `--auth xcode`
  - keeps `CLAWSEAT_PROVIDER=xcode-best`
  - passes `CLAWSEAT_SEAT=<engineer_id>` into launcher so seat runtime can load the correct template
  - prints a stderr debug line before launcher invocation:
    - `start_engineer_launch: session=... cmd=... provider=... engineer=...`

- `core/scripts/agent_admin.py`
  - catches `SessionStartError` at CLI top level and returns exit code `1` with a readable stderr message instead of letting the exception unwind

Tests:

- `tests/test_agent_admin_session_isolation.py`
  - updated matrix/runtime-dir expectations from `custom` to `xcode` for `codex + api + xcode-best`
- `tests/test_agent_admin_start_engineer_codex_mapping.py`
  - new coverage for:
    - launcher auth mapping = `xcode`
    - `CLAWSEAT_PROVIDER` + `CLAWSEAT_SEAT` env propagation
    - debug stderr line
    - non-zero launcher rc surfacing as `SessionStartError`

## Part B — per-seat `.claude-template` copy architecture

### New static mapping

- `core/scripts/seat_skill_mapping.py`
  - central seat/role mapping:
    - `ancestor -> clawseat-ancestor`
    - `planner -> planner`
    - `memory -> memory-oracle`
    - `builder/reviewer/qa/designer -> clawseat`
  - shared skills for every seat:
    - `clawseat`
    - `gstack-harness`
    - `tmux-basics`
  - supports suffixed ids like `builder-1`, `reviewer-1`, `qa-1`, `designer-1`

### Template generation

- `core/scripts/seat_claude_template.py`
  - new helper that:
    - renders `~/.agents/engineers/<seat>/.claude-template/settings.json`
    - copies the mapped skill directories into `.../.claude-template/skills/`
    - adds the memory Stop-hook only for the `memory` seat
    - exposes `copy_seat_claude_template_to_runtime(...)` for launcher use

- `core/scripts/agent_admin_store.py`
  - `write_engineer()` now prepares the seat’s `.claude-template` whenever an engineer profile is written

- `scripts/install.sh`
  - install memory path now prepares the `memory` template explicitly before launching the singleton seat
  - memory Stop-hook now lands in:
    - `~/.agents/engineers/memory/.claude-template/settings.json`
  - launcher receives `CLAWSEAT_SEAT=ancestor|memory` for install-time Claude seats

- `core/skills/memory-oracle/scripts/install_memory_hook.py`
  - added `--settings-path` and `install_memory_hook_at(...)`
  - can now target template settings directly, not only `<workspace>/.claude/settings.json`

### Launcher runtime copy

- `core/launchers/agent-launcher.sh`
  - Claude sandbox no longer links seat `settings.json` / `skills` from user-level `~/.claude`
  - instead, launcher copies from:
    - `~/.agents/engineers/<seat>/.claude-template/settings.json`
    - `~/.agents/engineers/<seat>/.claude-template/skills/*`
  - runtime `settings.json` and `skills/` are now real file/dirs, not symlinks
  - kept compatibility links for `.claude.json`, `statsig`, `commands`, and `agents`
  - if a seat template is missing, launcher regenerates it from the static mapping before copy so existing installs do not stay broken

## Files Changed

- `core/scripts/agent_admin.py`
- `core/scripts/agent_admin_session.py`
- `core/scripts/agent_admin_store.py`
- `core/scripts/seat_skill_mapping.py`
- `core/scripts/seat_claude_template.py`
- `core/launchers/agent-launcher.sh`
- `core/skills/memory-oracle/scripts/install_memory_hook.py`
- `scripts/install.sh`
- `tests/test_agent_admin_session_isolation.py`
- `tests/test_agent_admin_start_engineer_codex_mapping.py`
- `tests/test_launcher_claude_home_seed.py`
- `tests/test_seat_template_populated_after_profile_create.py`
- `tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py`
- `tests/test_install_isolation.py`

## Tests

Static checks:

- `bash -n /Users/ywf/ClawSeat/core/launchers/agent-launcher.sh`
- `bash -n /Users/ywf/ClawSeat/scripts/install.sh`
- `python3 -m py_compile ...` on all changed Python modules/tests

Targeted:

- `pytest /Users/ywf/ClawSeat/tests/test_agent_admin_session_isolation.py /Users/ywf/ClawSeat/tests/test_agent_admin_start_engineer_codex_mapping.py /Users/ywf/ClawSeat/tests/test_launcher_claude_home_seed.py /Users/ywf/ClawSeat/tests/test_seat_template_populated_after_profile_create.py /Users/ywf/ClawSeat/tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py /Users/ywf/ClawSeat/tests/test_install_memory_singleton.py /Users/ywf/ClawSeat/tests/test_install_isolation.py /Users/ywf/ClawSeat/tests/test_project_bootstrap_repo_template.py -q`
  - `40 passed`

Regression sweep:

- `pytest /Users/ywf/ClawSeat/tests/test_install_lazy_panes.py /Users/ywf/ClawSeat/tests/test_window_open_grid.py /Users/ywf/ClawSeat/tests/test_agent_admin_window_reseed.py /Users/ywf/ClawSeat/tests/test_install_auto_kickoff.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_spawn49.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_no_retry_loop.py /Users/ywf/ClawSeat/tests/test_ancestor_skill_seat_tui_lifecycle.py /Users/ywf/ClawSeat/tests/test_ancestor_brief_seat_tui_lifecycle.py /Users/ywf/ClawSeat/tests/test_launch_permissions.py /Users/ywf/ClawSeat/tests/test_launcher_codex_xcode_fallback.py /Users/ywf/ClawSeat/tests/test_wait_for_seat_persistent_reattach.py /Users/ywf/ClawSeat/tests/test_wait_for_seat_trust_detection.py -q`
  - `45 passed`

## Notes

- No end-to-end `scripts/install.sh` run was performed, per task constraint.
- No live tmux seat state was modified.
- Existing installs with already-written engineer profiles but missing `.claude-template/` are covered by launcher-side auto-regeneration on next seat start.
