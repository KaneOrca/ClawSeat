---
name: cs
description: Local post-install ClawSeat convenience entrypoint. `/cs` is the thin shortcut that resumes an existing v2 `install` project — it delegates to `install_entrypoint.py` for bootstrap. Use only in local Claude/Codex runtimes after ClawSeat is installed.
---

# ClawSeat `/cs` — local convenience entrypoint

`/cs` is the thin local shortcut for operators who already have ClawSeat installed
and want to quickly **resume** the canonical `install` project. It is NOT the
bootstrap path for a fresh machine.

> **v0.4 layered model**: `/cs` no longer bootstraps from a v1 template.
> See `docs/schemas/v0.4-layered-model.md` for the authoritative architecture.

## What `/cs` does (v0.4)

| State | Behavior |
|-------|----------|
| Existing `install` project with a v2 profile | Resume — verify ancestor tmux session, (re)launch if needed |
| No `install` project yet | **Refuse** — point operator at `install_entrypoint.py` |
| v1 profile at `~/.agents/profiles/install-profile-dynamic.toml` | **Refuse** — point operator at `migrate_profile_to_v2.py apply` |

`/cs` will NEVER:

- write a v1 profile (no longer supported; validator rejects)
- start `koder` as a tmux seat (v0.4: koder is an OpenClaw tenant agent)
- start `memory` as a project seat (v0.4: memory is a machine-layer singleton)
- create a parallel `install-*` project when the canonical one already exists

## Run

1. Confirm `CLAWSEAT_ROOT` points at the ClawSeat checkout.
2. Run:

   ```bash
   python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/cs_init.py"
   ```

3. Report one of:
   - `resumed` — existing v2 profile reused, planner (if in seats) launched/reattached
   - `refused_v1` — profile is v1; operator must run `migrate_profile_to_v2.py apply`
   - `refused_missing` — no profile; operator must run `install_entrypoint.py`

## Bootstrap (fresh machine)

For the first-ever install on a new machine, `/cs` is NOT the entry — use:

```bash
python3 -m core.tui.install_entrypoint --project install
```

This is the v0.4 canonical install flow. It:

1. Runs `install_wizard` to produce a v2 project profile via `profile_validator.write_validated`.
2. Renders `ancestor-bootstrap.md` via `ancestor_brief.py`.
3. Launches the **ancestor seat** (the desktop frontstage — not koder) via `agent-launcher.sh --headless`.
4. Opens an iTerm monitor window via `iterm_panes_driver.py`.
5. Hands control to ancestor for Phase-A (seat provisioning) and Phase-B (patrol).

Ancestor (not `/cs`) is the one that subsequently launches planner / builder /
reviewer / qa / designer.

## Interaction rules

- `/cs` itself is the operator's explicit approval to resume the canonical
  `install` project.
- Reuse an existing `install` workspace / live tmux sessions — no parallel
  `install-*` projects.
- Treat Claude OAuth, workspace trust, and permissions prompts as normal manual
  onboarding (handled by the agent-launcher).
- If tmux or PTY support is unavailable, stop cleanly and hand the next terminal
  command back to the operator.
- For all **post-resume** steps (adding seats, Feishu binding, patrol), ancestor
  owns the flow — do not drive them from `/cs`.

## References

- `{CLAWSEAT_ROOT}/core/tui/install_entrypoint.py` — fresh bootstrap
- `{CLAWSEAT_ROOT}/core/tui/install_wizard.py` — v2 profile generator
- `{CLAWSEAT_ROOT}/core/tui/ancestor_brief.py` — bootstrap brief renderer
- `{CLAWSEAT_ROOT}/core/launchers/agent-launcher.sh` — seat launcher
- `{CLAWSEAT_ROOT}/core/scripts/migrate_profile_to_v2.py` — v1→v2 migration
- `{CLAWSEAT_ROOT}/core/lib/profile_validator.py` — v2 schema validator
- `{CLAWSEAT_ROOT}/docs/schemas/v0.4-layered-model.md` — architecture spec
- `{CLAWSEAT_ROOT}/core/skills/clawseat-install/SKILL.md` — installer playbook
- `{CLAWSEAT_ROOT}/docs/install/gotchas-for-install-agents.md` — pitfalls for any agent helping install
