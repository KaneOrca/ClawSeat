task_id: PLIST-FIX
owner: codex-chatgpt
repo: /Users/ywf/ClawSeat
branch: experimental
status: done

## Task Source Note

The requested task file `TASK-CODEX-CHATGPT-PLIST.md` was not present at the
provided path. I executed against the issue statement from the user:

- full-chain install Issue #3
- `ancestor-patrol` plist not installed

## Root Cause

There were two separate breaks in the current chain:

1. `scripts/install.sh` never rendered or bootstrapped
   `~/Library/LaunchAgents/com.clawseat.<project>.ancestor-patrol.plist`.
   The template existed, but no live install step consumed it.
2. `core/templates/ancestor-patrol.plist.in` still hardcoded the retired
   `=<project>-ancestor-<tool>` tmux session naming scheme. Current install
   uses the canonical project session alias (`<project>-ancestor`) and session
   resolution now flows through `agentctl/session-name`, so even a manually
   installed plist would miss the live ancestor session.

## Changes

- `scripts/install.sh`
  - added Step 6 `install_ancestor_patrol_plist`
  - computes LaunchAgent label/path/log dir from project name
  - renders the plist from `core/templates/ancestor-patrol.plist.in`
  - validates rendered XML with `plutil -lint` when available
  - bootouts any existing label, then bootstraps the new plist with `launchctl`
  - skips `launchctl` only for non-macOS or sandbox/headless edge cases
  - supports cadence override via `CLAWSEAT_ANCESTOR_PATROL_CADENCE_MINUTES`

- `core/templates/ancestor-patrol.plist.in`
  - updated install provenance comment from launcher preflight to `install.sh`
  - removed the stale `{TOOL}` dependency
  - now resolves the canonical ancestor session via
    `agentctl.sh session-name ancestor --project <project>`
  - keeps `send-and-verify.sh` as the delivery path for `/patrol-tick`

- `docs/schemas/ancestor-bootstrap-brief.md`
  - synced the Phase-B contract text with the new install path and canonical
    session resolution behavior

- `tests/test_install_isolation.py`
  - fake install root now includes the patrol plist template
  - fake host tools now include `launchctl` and `plutil` stubs for install tests

- `tests/test_install_ancestor_patrol_plist.py`
  - new regression coverage for real install rendering/bootstrap
  - new dry-run coverage for the new Step 6 output

- `tests/test_ancestor_skill_comm_discipline.py`
  - tightened the template contract to require canonical session resolution and
    reject the stale suffixed session target

## Verification

Syntax:

```bash
bash -n scripts/install.sh
```

Targeted regression:

```bash
pytest tests/test_install_ancestor_patrol_plist.py \
       tests/test_install_isolation.py \
       tests/test_ancestor_skill_comm_discipline.py -q
```

Result:

- `6 passed in 5.64s`

Broader install/live-flow regression:

```bash
pytest tests/test_install_auto_kickoff.py \
       tests/test_install_lazy_panes.py \
       tests/test_install_ancestor_patrol_plist.py \
       tests/test_install_isolation.py \
       tests/test_window_open_grid.py \
       tests/test_agent_admin_window_reseed.py \
       tests/test_agent_admin_session_name_alias.py \
       tests/test_ancestor_brief_spawn49.py \
       tests/test_ancestor_brief_no_retry_loop.py \
       tests/test_ancestor_skill_comm_discipline.py -q
```

Result:

- `35 passed in 20.39s`

Post-doc-sync sanity:

```bash
pytest tests/test_install_ancestor_patrol_plist.py \
       tests/test_ancestor_skill_comm_discipline.py -q
```

Result:

- `3 passed in 2.46s`

## Notes

- I did not touch the launcher runtime start logic.
- I did not revert any unrelated work already present in the dirty branch.
- The current implementation intentionally does not `kickstart` the LaunchAgent
  on install, so Phase-B cadence begins on the normal launchd schedule rather
  than forcing an immediate patrol tick during Phase-A.
