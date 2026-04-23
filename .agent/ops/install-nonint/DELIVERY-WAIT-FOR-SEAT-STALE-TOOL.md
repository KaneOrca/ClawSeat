# Delivery: wait-for-seat stale-tool fallback fix

## Files Changed

- `scripts/wait-for-seat.sh`
- `core/scripts/agent_admin_session.py`
- `tests/test_wait_for_seat_rejects_stale_tool.py`
- `tests/test_start_engineer_kills_stale_tool_variants.py`
- `tests/test_install_lazy_panes.py`
- `tests/test_agent_admin_session_isolation.py`

## Diff Highlights

### Lane A: wait-for-seat stale-tool-safe fallback

- `wait-for-seat.sh` now resolves the engineer profile path from:
  - `AGENTS_ROOT`
  - else `CLAWSEAT_REAL_HOME/.agents`
  - else `HOME/.agents`
- At degraded fallback time it reads `~/.agents/engineers/<seat>/engineer.toml`,
  parses `default_tool`, and only accepts:
  - `<project>-<seat>-<default_tool>`
- If stale same-seat variants exist, it now warns and skips them:
  - `WARN: wait-for-seat stale-tool session detected: found <session>, canonical tool is <tool>, skipping`
- If `engineer.toml` is missing, unreadable, or malformed, it refuses fallback
  attach and keeps waiting with a fix hint.
- The existing guardrails remain intact:
  - 2-arg interface only
  - no fallback to bare `<project>-<seat>`
  - trust-prompt detection still works
  - reattach loop still works

### Lane B: start-engineer stale variant cleanup

- `SessionService.start_engineer()` now performs a pre-launch tmux sweep for
  same-seat variants matching:
  - `<project>-<seat>-*`
- Any session with the same `<project>-<seat>` prefix but a different tool
  suffix is killed before launcher startup.
- Each successful cleanup logs:
  - `start-engineer: killed stale-tool session <session>`
- `kill-session` races with:
  - `can't find session`
  - `no such session`
  are ignored.
- This cleanup is prefix-scoped, so it does not cross to other seats.

## Edge Cases Considered

- `wait-for-seat.sh` sees only stale same-seat different-tool sessions:
  - warns and keeps waiting
- `wait-for-seat.sh` sees both canonical and stale variants:
  - warns on stale, attaches only canonical
- `wait-for-seat.sh` cannot parse `engineer.toml`:
  - conservative behavior, no fallback attach
- `start-engineer` sees no stale variants:
  - normal launch path, only one pre-launch `list-sessions`
- `start-engineer` hits a stale-variant race during kill:
  - ignores “no such session” and continues
- round-3a 1-arg retirement:
  - untouched

## Tests

### New / lane-specific

```bash
bash -n scripts/wait-for-seat.sh

pytest -q \
  tests/test_wait_for_seat_rejects_stale_tool.py \
  tests/test_wait_for_seat_persistent_reattach.py \
  tests/test_wait_for_seat_trust_detection.py \
  tests/test_install_lazy_panes.py -k wait_for_seat
```

Result:

- `15 passed, 7 deselected in 9.98s`

```bash
pytest -q \
  tests/test_start_engineer_kills_stale_tool_variants.py \
  tests/test_start_engineer_no_kill_during_onboard.py \
  tests/test_start_engineer_onboarding_detect.py \
  tests/test_agent_admin_session_isolation.py \
  tests/test_agent_admin_session_project_tool_seed.py \
  tests/test_agent_admin_session_reseed.py \
  tests/test_session_start_ancestor_env.py \
  tests/test_agent_admin_start_engineer_codex_mapping.py
```

Result:

- `38 passed in 1.23s`

### Combined regression slice

```bash
pytest -q \
  tests/test_wait_for_seat_rejects_stale_tool.py \
  tests/test_start_engineer_kills_stale_tool_variants.py \
  tests/test_wait_for_seat_persistent_reattach.py \
  tests/test_wait_for_seat_trust_detection.py \
  tests/test_install_lazy_panes.py \
  tests/test_agent_admin_session_isolation.py \
  tests/test_start_engineer_no_kill_during_onboard.py \
  tests/test_start_engineer_onboarding_detect.py \
  tests/test_agent_admin_start_engineer_codex_mapping.py
```

Result:

- `54 passed in 20.05s`

## Open Questions For Planner

- `wait-for-seat.sh` currently shells out to `python3` to parse `engineer.toml`.
  That is fine on this repo’s current host assumptions, but if you want this
  script to remain maximally portable in degraded shells, we could later move to
  a simpler line-based parser or a shared Python helper script.
- The stale-tool cleanup uses tmux `list-sessions` on every non-idempotent
  `start-engineer` launch. That is cheap today; if seat counts grow a lot, we
  could later optimize with a prefix-filtered query helper.
