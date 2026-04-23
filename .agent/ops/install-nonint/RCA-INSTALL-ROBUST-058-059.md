# RCA — INSTALL-ROBUST-058-059

Merged research for INSTALL-LLM-RUN-058 and [INSTALL-ROBUST-059](/Users/ywf/ClawSeat/.agent/ops/install-nonint/TODO-BUILDER-CODEX-INSTALL-ROBUST-059.md).

These two TODOs belong together: both are install-time robustness issues, both surface during repeat or sandboxed runs, and both are safest to fix by tightening `install.sh` / launcher boundaries rather than widening the launcher's responsibilities.

## Executive Summary

- **Q1 and Q4 are the immediate blockers.**
  - Q1 is the tmux session lifecycle deadlock.
  - Q4 is the sandbox / real-home detection gate.
- **Q2 and Q3 are install.sh-only fixes.**
  - Q2 prevents repeat installs from re-entering the bad state.
  - Q3 makes provider selection automation-friendly.
- **Q5 is not a blocker.**
  - Recovery should remain owned by the canonical `agent_admin window open-grid --recover [--open-memory]` path.

Recommended order:

1. Q1 + Q4
2. Q2
3. Q3
4. Q5 as documentation / call-site wiring only

## Q1 — Session lifecycle deadlock

### Symptom

`install.sh` launches a seat, then `configure_tmux_session_display` runs after the session may already have disappeared.

The failure mode looks like:

- `tmux new-session -d ...` returns success
- the seat process exits immediately
- tmux destroys the session
- later `tmux set-option -t "=<session>" detach-on-destroy off` fails because the session no longer exists

### Root cause

The launcher leaves tmux in its default `detach-on-destroy=on` state until after the session has already survived creation. That is too late.

### Recommendation

- Move `detach-on-destroy off` into the session creation path or immediately after `tmux new-session` while the session is still alive.
- Keep GUI failures best-effort, not fatal, so the launcher can still recover in headless/sandbox scenarios.
- If the GUI open/focus path cannot obtain a window id, skip focus rather than turning the whole install into a hard failure.

### Scope / owner

- Primary fix: launcher
- Secondary fix: `install.sh` call-site should treat GUI open/focus as recoverable

### Workload

- **Moderate**

## Q2 — `phase=ready` repeat-install early exit

### Symptom

Repeat installs continue past the preflight step even when `STATUS.md` already says the project is ready.

### Root cause

`install.sh` does not currently gate on the install status file before rebuilding the runtime.

### Recommendation

- Add a Step 1 preflight against `~/.agents/tasks/install/STATUS.md`.
- If the phase is already `ready`, exit cleanly with a clear message.
- Add an explicit `--force` / `--reinstall` override for operators who truly want a rebuild.

### Scope / owner

- `install.sh` only

### Workload

- **Trivial to moderate**

## Q3 — Provider selection must be non-interactive

### Symptom

The install flow still expects interactive provider selection, which is brittle for smoke, CI, and sandbox runs.

### Root cause

Provider choice is prompt-driven instead of being fully overrideable from CLI or env.

### Recommendation

- Add `--provider <n>` and/or `CLAWSEAT_INSTALL_PROVIDER=<n>`.
- Preserve the existing short-circuit for explicit `--base-url + --api-key` inputs.
- Do not move provider selection into launcher or agent_admin.

### Scope / owner

- `install.sh` only

### Workload

- **Trivial**

## Q4 — Sandbox HOME / GUI gate

### Symptom

The installer tries to behave like a full desktop install even when the run is a sandbox / smoke run that should stay headless or recover through canonical seat commands.

### Root cause

The gate is not using the real-home SSOT, so sandboxed runs can be misclassified or treated as full desktop installs.

### Recommendation

- Use the existing real-home SSOT semantics from `core/lib/real_home.py` for sandbox detection.
- In sandbox/headless runs, keep GUI open/focus best-effort and let the canonical seat recovery path handle recovery.
- Avoid pushing this predicate into launcher or `agent_admin_session.py` unless a shared helper is needed.

### Scope / owner

- `install.sh`

### Workload

- **Trivial to moderate**

## Q5 — Recovery ownership

### Symptom

When install-time recovery is needed, there is pressure to teach the launcher more recovery behavior.

### Root cause

This is not a launcher problem. The recovery surface already exists higher up the stack.

### Recommendation

- Keep `agent_admin window open-grid --recover [--open-memory]` as the canonical recovery path.
- Treat `AGENT_HOME` export in the launcher as defense-in-depth only.
- If install docs need a recovery pointer, wire that into `install.sh` and operator docs rather than the launcher.

### Scope / owner

- `agent_admin` and `install.sh` docs/call-sites

### Workload

- **Not a blocker**

## Combined Recommendation

The merged fix plan should be:

1. Harden tmux/session survival first.
2. Add repeat-install idempotence.
3. Make provider selection non-interactive.
4. Gate GUI behavior on the real-home SSOT for sandbox/headless runs.
5. Keep recovery through the canonical `agent_admin window open-grid` path.

## Risks

- If Q1 is fixed but Q2 is skipped, repeat installs will still wander back into the broken path.
- If Q3 is changed without preserving the explicit base-url/api-key precedence, custom provider regression is easy to reintroduce.
- If the sandbox gate uses raw `HOME` or `Path.home()` instead of the real-home SSOT, symlinked homes will be misclassified.
- If recovery ownership is pulled into launcher code, the install path becomes harder to reason about and easier to regress.

## Workload Estimate

- Q1: moderate
- Q2: trivial to moderate
- Q3: trivial
- Q4: trivial to moderate
- Q5: not a blocker

## Implementation Boundary

This RCA recommends **not** touching `agent_admin_session.py` or `agent_admin_resolve.py` for the primary install robustness fix unless a shared predicate is required.

The clean split is:

- `launcher` for tmux survival
- `install.sh` for idempotence and provider selection
- `agent_admin` for canonical recovery commands
