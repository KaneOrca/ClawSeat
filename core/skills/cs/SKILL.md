---
name: cs
description: Local ClawSeat re-entry helper. `/cs` is the shorthand for the v0.5 Resume / Re-entry contract in docs/INSTALL.md; use it only after install state already exists.
---

# ClawSeat `/cs` — local re-entry entrypoint

`/cs` is the thin local shortcut for operators who already have ClawSeat
installed and want to quickly re-enter the canonical `install` project. It is
NOT the bootstrap path for a fresh machine.

The source of truth is still [`docs/INSTALL.md`](../../../docs/INSTALL.md).
`/cs` is just the local shorthand for that file's `Resume / Re-entry` section.

## What `/cs` does

| State | Behavior |
|-------|----------|
| Existing `install` project with valid profile + binding + runtime metadata | Resume — inspect the current sessions and continue |
| Existing install state but ancestor session is missing | Relaunch ancestor via `scripts/launch_ancestor.sh`, then continue |
| Missing or invalid install state | **Refuse** — point operator at `docs/INSTALL.md` fresh-install path |

`/cs` will NEVER:

- synthesize a fresh profile or PROJECT_BINDING on its own
- start a parallel `install-*` project when the canonical one already exists
- bypass ancestor and directly own seat lifecycle
- treat local re-entry as a substitute for the install playbook

## Run

1. Confirm `CLAWSEAT_ROOT` points at the ClawSeat checkout.
2. Open [`docs/INSTALL.md`](../../../docs/INSTALL.md) and follow its
   `Resume / Re-entry` section.
3. Reuse the existing project state. If ancestor is missing but the project
   state is valid, relaunch ancestor with the runtime tuple already recorded for
   the project.
4. Report one of:
   - `resumed` — ancestor/session state already healthy
   - `relaunched_ancestor` — ancestor was missing and has been brought back
   - `refused_missing_state` — no install state exists yet
   - `refused_invalid_state` — state exists but is inconsistent and needs a
     playbook-guided repair

## Fresh install

For the first install on a new machine, `/cs` is NOT the entry. Run the
playbook in [`docs/INSTALL.md`](../../../docs/INSTALL.md).

## Interaction rules

- `/cs` itself is the operator's explicit approval to resume the canonical
  `install` project.
- Reuse an existing `install` workspace / live tmux sessions — no parallel
  `install-*` projects.
- Treat OAuth, workspace trust, and permissions prompts as normal manual
  onboarding handled by the launcher/runtime.
- If tmux or PTY support is unavailable, stop cleanly and hand the next terminal
  command back to the operator.
- For all **post-re-entry** steps (adding seats, Feishu binding, patrol), ancestor
  owns the flow — do not drive them from `/cs`.

## References

- `{CLAWSEAT_ROOT}/docs/INSTALL.md` — fresh install + resume playbook
- `{CLAWSEAT_ROOT}/scripts/launch_ancestor.sh` — ancestor relaunch path
- `{CLAWSEAT_ROOT}/core/launchers/agent-launcher.sh` — seat launcher
- `{CLAWSEAT_ROOT}/core/scripts/agent_admin.py` — session lifecycle
- `{CLAWSEAT_ROOT}/core/lib/profile_validator.py` — v2 schema validator
- `{CLAWSEAT_ROOT}/core/skills/clawseat-install/SKILL.md` — installer playbook
