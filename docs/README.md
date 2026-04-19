# ClawSeat Docs Index

This directory has three kinds of documents. Pick by what you're trying to do.

## 🚀 I want to install or run ClawSeat

| File | Who for | What |
|------|---------|------|
| [INSTALL_GUIDE.md](INSTALL_GUIDE.md) | End user | Quickstart, dependency tiers, runtime-aware preflight, configuration gate |
| [INSTALL.md](INSTALL.md) | End user / maintainer | Canonical path contract (`$CLAWSEAT_ROOT`, portable profile placeholders), role-first bootstrap |
| [POST_INSTALL.md](POST_INSTALL.md) | End user | Daily use: start/stop seats, change provider, read logs, diagnose the configuration gate |
| [RUNTIME_ENV.md](RUNTIME_ENV.md) | Maintainer | Env vars, directory contracts, how to tell which ClawSeat checkout OpenClaw is actually loading |

Read order for a first install: INSTALL_GUIDE → (when it stops at the gate) POST_INSTALL → (only when debugging drift) RUNTIME_ENV.

## 🏗️ I want to understand how ClawSeat is put together

| File | Who for | What |
|------|---------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Contributor | The five layers (control plane / runtime contracts / skills / adapters / fixtures) and what lives in each |
| [CANONICAL-FLOW.md](CANONICAL-FLOW.md) | Contributor | The dispatch → completion → ACK protocol, the `OC_DELEGATION_REPORT_V1` envelope, three required artifacts per handoff, project-group bridge binding |
| [PACKAGING.md](PACKAGING.md) | Maintainer / packager | What goes into the minimum OpenClaw-facing ClawSeat product bundle vs. what's optional |
| [TEAM-INSTANTIATION-PLAN.md](TEAM-INSTANTIATION-PLAN.md) | Contributor (historical) | Original design intent for template-driven team instantiation and the planner/koder protocol. The system today matches this design |

## 🔧 I'm debugging something specific

| File | Who for | What |
|------|---------|------|
| [ITERM_TMUX_REFERENCE.md](ITERM_TMUX_REFERENCE.md) | On-call / integrator | iTerm + tmux baseline: error codes, official-practice audit, `send-and-verify` semantics, recovery path |
| [RUNTIME_ENV.md](RUNTIME_ENV.md) | On-call | Which checkout is OpenClaw actually loading? Symlink spelunking. |
| [POST_INSTALL.md](POST_INSTALL.md) | On-call | Self-heal commands by scope (refresh → bundle → preflight → first_install) |

## Conventions

- **Language**: Mixed Chinese / English, favouring Chinese for user-facing content and English for protocol / reference material.
- **Paths**: All paths are relative to the ClawSeat repo root (e.g. `core/skills/clawseat-install/`). Where a file expands a variable, it uses `$CLAWSEAT_ROOT` explicitly.
- **Commands are copy-pastable**: Code blocks here should run as-is on a machine with `CLAWSEAT_ROOT` exported and the canonical install path (`~/.clawseat`). If a block requires other env vars, it says so inline.
- **Stale content policy**: If a doc refers to a file path or command that no longer exists, please fix the doc in the same commit as the rename / removal, or open an issue. Docs drift faster than code if left alone.
