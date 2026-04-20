---
name: clawseat
description: Canonical product entrypoint for ClawSeat. Use this skill when OpenClaw, Feishu, Claude Code, or Codex should load ClawSeat as an installable workflow and automatically run the full bootstrap/configure/verify path.
---

# ClawSeat

## Overview

Treat `clawseat` as the product-level entrypoint.

- In **OpenClaw / Feishu** environments, this is the canonical way to start
  ClawSeat. Do not require the user to know `/cs`.
- In **Claude Code / Codex** local runtimes, this skill may install the local
  entry skills first; after that, `/cs` remains only a thin convenience alias.

This skill does not replace the core install/bootstrap engine. It routes to:

- `core/skills/clawseat-install/SKILL.md` for the narrow install/bootstrap flow
- `shells/openclaw-plugin/openclaw_bootstrap.py` when the host runtime is
  OpenClaw
- `core/skills/cs/SKILL.md` only when the runtime explicitly supports local
  slash-skill entrypoints and the user wants that shortcut

## Canonical Behavior

1. Detect the host runtime.
2. If the host is **OpenClaw** or the user is interacting through **Feishu**:
   - use the OpenClaw plugin/bootstrap path
   - keep the experience product-shaped: “install/start ClawSeat”
   - do not assume `/cs` is available
   - treat the canonical bootstrap project as `install`, not as a smoke-only placeholder
3. If the host is **Claude Code** or **Codex**:
   - install the local entry skills when needed
   - use `/cs` or `$cs` only as a convenience alias after install
4. Continue through the standard ClawSeat phases:
   - install
   - bootstrap
   - project/group binding
   - configuration entry
   - configuration verification
   - normal execution

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

Then follow the canonical 6-phase install flow in
`core/skills/clawseat-install/references/ancestor-runbook.md`. Phase 0.1
runs `install_bundled_skills.py` to create symlinks in `~/.openclaw/skills/`
with dependency checks (lark-cli, gstack). Do NOT manually copy skill
directories. Do NOT run individual scripts out of order — the flow is
interactive and halts at user-decision points (agent selection, seat
provider/auth choice, Feishu group ID).

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
- `docs/INSTALL_GUIDE.md`
- `shells/openclaw-plugin/README.md`
