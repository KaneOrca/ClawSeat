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
- This skill does not implement install logic itself or claim long-lived
  runtime ownership. It routes to `clawseat-install`,
  `docs/INSTALL.md`, and the OpenClaw wrapper as needed.

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
5. Keep frontstage semantics consistent:
   - local CLI install -> `ancestor` becomes the install frontstage after launch
   - Feishu / OpenClaw tenant path -> `koder` remains the tenant frontstage and
     `ancestor` runs behind it
6. Once ancestor is prompt-ready, treat ancestor as the runtime owner for seat
   lifecycle and patrol. Do not invent parallel bootstrap paths.

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

**Critical: OpenClaw tenant frontstage**

In the OpenClaw / Feishu path, the user-facing tenant frontstage is `koder`.
If this skill is already running inside that tenant-facing agent, treat the
current runtime as the existing `koder` frontstage instead of trying to spawn
another one.

- Do NOT run `start_seat.py --seat koder` — that creates a redundant tmux session
- Do NOT bootstrap a project named after yourself (e.g. `koder-frontstage`)
- The canonical project name is `install`
- The tmux-backed project grid is still `ancestor`, `planner`, `builder`,
  `reviewer`, `qa`, `designer`
- Once ancestor is prompt-ready, seat lifecycle and patrol belong to ancestor

## Local Runtime Contract

When the host runtime is local and supports explicit skills:

- install `clawseat`, `clawseat-install`, and `cs`
- explain that `clawseat` is the fresh-install product entry
- explain that `/cs` is only the post-install re-entry shortcut
- explain that local fresh install hands off to `ancestor`, not directly to
  `koder`

## References

- `core/skills/clawseat-install/SKILL.md`
- `core/skills/cs/SKILL.md`
- `docs/INSTALL.md`
- `shells/openclaw-plugin/README.md`
