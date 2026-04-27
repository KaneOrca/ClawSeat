---
name: clawseat-install
description: "Installer playbook; bootstraps ClawSeat projects through install.sh."
---

# ClawSeat Install (v0.7 — CLI-first)

You (the running Claude Code) are the installer.

There is no install binary and no TUI wizard.
The single source of truth for flags and options is **`docs/INSTALL.md` in the cloned repo**.
This skill is a thin pointer so you know what to do when the user asks
for install.

## When the user asks to install

1. **If the repo is not yet on disk** — `git clone` the ClawSeat repo
   to a user-level directory (NOT inside `~/.openclaw/`). Example:
   `git clone <repo-url> ~/ClawSeat`.

2. **Read `docs/INSTALL.md`** from the clone. That file is the
   executable playbook: prerequisites, env scan, runtime choice,
   seat infrastructure, project memory launch, and the workers window
   handoff. Follow it top-to-bottom.

3. **Do not invent steps.** If something you need is not in
   `docs/INSTALL.md`, ask the user or stop and flag the doc as
   incomplete. Do not reach for the retired TUI helpers from older
   install generations.

## Canonical execution path

The canonical fresh-install command is:

```bash
bash scripts/install.sh
```

For non-default cases, follow the playbook and pass only the flags it
documents, for example `--project`, `--repo-root` (FR-7: point memory to a
different business repo), `--template` (select project roster: `clawseat-default` |
`clawseat-engineering` | `clawseat-creative`), `--provider`, `--base-url`,
`--api-key`, `--model`, `--reinstall`, or `--reset-harness-memory` (FR-1: clear
saved per-seat harness choices).

Important:
- `scripts/install.sh` is the L1 user-facing entrypoint. Do not replace it
  with `scripts/launch_ancestor.sh`, direct `agent-launcher.sh`, or ad-hoc
  `tmux` commands for fresh installs.
- When the provider menu appears in a non-interactive or CI-style run, use the
  documented `--provider 1` / `CLAWSEAT_INSTALL_PROVIDER=1` path from
  `docs/INSTALL.md`.
- `--model` is only meaningful when the documented provider path supports it.

After `install.sh` finishes, the **project memory seat takes over**. The installer does
not manually recreate the memory launch sequence.

## Runtime topology (what memory brings up)

- **Project memory layer**: `<project>-memory` is the primary frontstage and orchestration hub.
- **Project workers window**: worker seats are template-driven from `project.toml`.
  `clawseat-minimal` uses planner / builder / designer; richer templates can add reviewer and qa.
- **Tenant layer (Feishu optional)**: `koder` — optional OpenClaw-side
  Feishu reverse channel adapter / async notification sink, not a tmux
  seat and not the primary frontstage.

Frontstage identity depends on runtime:
- **CLI install** → project memory is frontstage
- **Feishu / OpenClaw path** → project memory remains the CLI frontstage;
  `koder` is only an optional post-install reverse-channel overlay

## Orchestration boundary

Follow the runtime boundaries in `docs/INSTALL.md` and `docs/ARCHITECTURE.md`:

- `install.sh` handles host bootstrap, machine scan, provider selection,
  memory launch, workers window open, and shared memories window setup.
- Once project memory is prompt-ready, memory owns Phase-A and later seat
  lifecycle.
- Do not parallelize B3.5 engineer bring-up. Provider clarification is
  intentionally one-by-one via CLI prompt.
- Do not use Feishu delegation reports as the provider-clarification channel.

## What to NOT do

- Do **not** resurrect the retired TUI/bootstrap commands from older
  releases.
- Do **not** rely on the old batch flags from the removed installer
  surface.
- Do **not** call `scripts/launch_ancestor.sh` for fresh install. That is a
  legacy helper, not the canonical v0.7 bootstrap path.
- Do **not** invoke `/cs` for fresh installs — `/cs` is a separate
  resumer skill for "memory crashed, come back up"; it does not
  replace the v0.7 playbook.
- Do **not** describe your work using retired launch choreography from older
  install generations.
- Do **not** write v1 profiles. v2 schema only (`core/lib/profile_validator.py`).
- Do **not** edit `openclaw/` source to fix an install problem. Use
  ClawSeat config or the OpenClaw plugin shell only.
- Do **not** use Feishu delegate report (`OC_DELEGATION_REPORT_V1`) as
  the primary channel for seat provider clarification.
- Do **not** use Feishu `chat_id` as the project identifier — use
  `agent_admin project bootstrap` / `agent_admin project use`.

## Resume / re-entry

If install was interrupted mid-flow, re-read `docs/INSTALL.md`. Its
"Resume" section tells you how to re-scan state and pick up where you
stopped. Typically:

1. Check what seats are already up (`tmux list-sessions | grep <project>-`).
2. Fill the gaps.
3. If project memory is alive, defer the rest to memory's Phase-A checklist.

## References

- [`docs/INSTALL.md`](../../../docs/INSTALL.md) — **the playbook you execute**
- [`scripts/install.sh`](../../../scripts/install.sh) — canonical fresh-install entrypoint
- [`core/lib/profile_validator.py`](../../lib/profile_validator.py) — v2 schema validator (still authoritative)
- [`core/launchers/agent-launcher.sh`](../../launchers/agent-launcher.sh) — low-level seat launcher used internally by `install.sh` / `agent_admin`
- [`core/scripts/agent_admin.py`](../../scripts/agent_admin.py) — session lifecycle CLI
- [`core/skills/clawseat-memory/SKILL.md`](../clawseat-memory/SKILL.md) — memory's own skill, owns everything post-launch
- [`core/skills/cs/SKILL.md`](../cs/SKILL.md) — `/cs` resumer (separate from fresh install)
