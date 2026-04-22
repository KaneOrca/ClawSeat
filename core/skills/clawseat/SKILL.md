---
name: clawseat
description: Canonical product entrypoint for ClawSeat. Use this skill when OpenClaw, Feishu, Claude Code, or Codex should load ClawSeat as an installable workflow and route to the v0.5 install playbook.
---

# ClawSeat

## Overview

Treat `clawseat` as the product-level entrypoint.

- In **OpenClaw / Feishu** environments, this is the canonical way to start
  ClawSeat. Do not require the user to know `/cs`.
- In **Claude Code / Codex** local runtimes, this skill points to the install
  playbook. `/cs` remains only a re-entry shortcut after install state exists.
- This skill does not implement install logic itself. It routes the runtime to
  `clawseat-install`, `docs/INSTALL.md`, and the OpenClaw wrapper as needed.

## Canonical Behavior

1. Detect the host runtime.
2. Ensure the repo is cloned to a user-level directory, not inside
   `~/.openclaw/`.
3. Route to [`core/skills/clawseat-install/SKILL.md`](../clawseat-install/SKILL.md)
   and [`docs/INSTALL.md`](../../../docs/INSTALL.md).
4. Keep product framing consistent:
   - fresh install -> run the playbook
   - local re-entry -> `/cs`
   - OpenClaw bootstrap -> plugin wrapper + same playbook
5. Once ancestor is prompt-ready, treat ancestor as the install frontstage and
   stop inventing parallel bootstrap paths.

## OpenClaw / Feishu Contract

When the user wants OpenClaw to run ClawSeat as a skill:

- prefer the OpenClaw shell/plugin path
- keep ClawSeat core logic inside the ClawSeat repo
- do not patch OpenClaw source code to implement ClawSeat behavior
- allow the user to invoke ClawSeat through natural language such as
  “安装 ClawSeat” or “启动 ClawSeat”, with this skill acting as the product
  wrapper

**Critical: clone location**

When cloning from git, install ClawSeat to a user-level directory, NOT inside
`~/.openclaw/`. ClawSeat is a standalone project, not an OpenClaw internal
component.

- Correct: `git clone <url>` in any user-level directory (e.g. home dir, projects dir)
- Wrong: `git clone <url> ~/.openclaw/workspace-clawseat` or anywhere inside `~/.openclaw/`

Then follow [`docs/INSTALL.md`](../../../docs/INSTALL.md). The playbook scans
the machine, records runtime selection, materializes validated state, launches
ancestor, and hands off the rest of seat bring-up to ancestor. Do not resurrect
retired manual bootstrap paths.

**Critical: koder identity in OpenClaw mode**

In the OpenClaw path, **you (the current agent) ARE koder**. You are the
frontstage. You do NOT need a separate tmux session for koder.

- Do NOT run `start_seat.py --seat koder` — that creates a redundant tmux session
- Do NOT bootstrap a project named after yourself (e.g. `koder-frontstage`)
- The canonical project name is `install`
- Only backend seats (planner, builder, reviewer, qa, designer) run in tmux
- You talk to the user directly; backend seats talk to you via TODO/DELIVERY protocol

## Local Runtime Contract

When the host runtime is local and supports explicit skills:

- install `clawseat`, `clawseat-install`, and `cs`
- explain that `clawseat` is the product entry
- explain that `/cs` is only the fast local shortcut after install

## References

- `core/skills/clawseat-install/SKILL.md`
- `core/skills/cs/SKILL.md`
- `docs/INSTALL.md`
- `shells/openclaw-plugin/README.md`
