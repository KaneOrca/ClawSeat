---
name: clawseat-install
description: Install and bootstrap ClawSeat for Codex or Claude Code, including detecting and reusing existing workspaces or live TUIs. Use when a user asks to install ClawSeat, 安装 ClawSeat, wire a shell bundle, create a starter profile, run preflight/bootstrap, start `koder`, or troubleshoot first-launch and tmux/PTY failures.
---

# ClawSeat Install

## Overview

Use this skill to choose and run the standard ClawSeat installation path. Keep the flow narrow: confirm the target runtime, run preflight, bootstrap the project, and report the first-launch state clearly.
Before creating anything new, resolve whether the target already has a workspace, project record, or live tmux/TUI seat. Reuse it if present.
For OpenClaw or Feishu-facing usage, prefer the product entry skill
`clawseat`; it should route here and then use the OpenClaw plugin/bootstrap
path. Only local Claude/Codex runtimes should treat `/cs` as the preferred
post-install convenience command.

## Choose The Install Path

- First check for an existing canonical workspace/TUI for the requested project or seat label. If one exists, treat it as the source of truth instead of creating a parallel install.
- If the user wants OpenClaw or Feishu to load ClawSeat as a product skill,
  start from `core/skills/clawseat/SKILL.md`; keep `/cs` out of the primary
  user experience.
- If the user wants the standard first-run path after installing ClawSeat onto Claude/Codex, install the entry skills and route them to `/cs`.
- If the user wants this agent runtime to load ClawSeat, use the `shells/codex-bundle/` or `shells/claude-bundle/` entrypoint for that runtime.
- If the user wants the canonical install workspace, use `install.toml`.
- If the user wants a fresh project workspace, use `starter.toml` for a koder-only entrypoint or `full-team.toml` when they explicitly want the full six-seat roster.
- If the user wants OpenClaw integration, use `shells/openclaw-plugin/openclaw_bootstrap.py` and keep core logic in ClawSeat, not OpenClaw.

## Standard Flow

1. Resolve the canonical project/workspace name and check whether an existing TUI or workspace already exists for it.
2. Read [install-flow.md](references/install-flow.md) for the command sequence and fallback rules.
3. Read [interaction-mode.md](references/interaction-mode.md) before interacting with the user during installation.
4. Confirm `CLAWSEAT_ROOT` points at the ClawSeat checkout.
5. Install the entry skills with `python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"`.
6. If the runtime is OpenClaw or Feishu-facing, route through `shells/openclaw-plugin/openclaw_bootstrap.py` and keep the user experience centered on `clawseat`.
7. If the runtime is local Claude/Codex, tell the user to run `/cs`; that wrapper delegates to `cs_init.py`, uses `examples/starter/profiles/install.toml`, and starts `planner`.
8. For manual project-specific installs, run `python3 "$CLAWSEAT_ROOT/core/preflight.py" [project]`.
9. If a fresh project is needed, copy `examples/starter/profiles/starter.toml` for a koder-only entrypoint, `examples/starter/profiles/install.toml` for the canonical install project, or `examples/starter/profiles/full-team.toml` for a six-seat roster to `/tmp/{project}-profile-dynamic.toml`.
10. Bootstrap with `python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py" --profile /tmp/{project}-profile-dynamic.toml --project-name {project} --start`.
11. Start or verify `koder` with `start_seat.py --seat koder`, then check `render_console.py`.
12. Treat OAuth login, workspace trust, and permission prompts as normal first-launch onboarding.

## Interaction Contract

- Auto-run inspection, preflight, profile creation, bootstrap, and console verification when the target project/runtime is already clear.
- If an existing workspace or live TUI is already present, reuse it and report that it is being resumed instead of creating a parallel project.
- Treat `/cs` as explicit approval to bootstrap or resume the canonical `install` project and launch `planner`.
- Tell the user exactly when installation leaves the automatic path and requires manual action.
- Ask for user confirmation before launching any non-frontstage seat or changing runtime/provider choices that affect an existing seat.
- When Claude first-launch prompts appear, explain that the user must complete the TUI step, then resume the install flow afterwards.
- When the host terminal cannot provide PTY/tmux capability, stop cleanly and hand the next command to the user instead of masking it as a ClawSeat failure.
- `qa-1` is not part of the default `/cs` first-launch roster; only bring it up when the current chain is explicitly test / smoke / regression heavy.
- After runtime bootstrap, move into a configuration phase before normal task execution. That phase owns project/group binding plus the runtime values that make seats usable: provider choice, auth mode, API key material, and base URL / endpoint configuration.
- Treat configuration as two sub-phases: configuration entry first, configuration verification second.
- Once the user provides a Feishu group ID during install bring-up, first confirm whether that group binds the current project, another existing project, or a new project; only then proactively delegate the smoke test to `planner`, tell the user `收到测试消息即可回复希望完成什么任务`, and launch `reviewer-1` in parallel when that seat exists.
- When the current chain is verification-heavy, ask `planner` to launch `qa-1` in parallel with or immediately after `reviewer-1`; `qa-1` owns smoke / regression / preflight verification, not execution planning.
- `qa-1` validates configuration changes but does not become the secret owner: it should verify Feishu bridge health, key usability, URL reachability, and provider correctness without becoming the seat that records or stores raw secrets.
- Any change to Feishu bridge settings, new API keys, key rotation, base URL / endpoint values, or auth_mode / provider bindings should be treated as configuration work and considered a QA-triggering event.
- When a Feishu group is bound, planner should use `OC_DELEGATION_REPORT_V1` over the user-identity bridge for koder-facing closeouts; legacy auto-broadcast is opt-in only and should stay disabled by default.
- When the stage closeout later returns to frontstage, koder should read the linked delivery trail, reconcile the wrap-up, and update the project docs before summarizing to the user.

## Troubleshooting

- If `tmux new-session` or `openpty` fails with `Device not configured`, report a host terminal limitation instead of a ClawSeat config failure.
- If `CLAWSEAT_ROOT` is missing or wrong, stop and ask the user to export the correct path.
- Do not patch OpenClaw source to solve a ClawSeat install issue; use config or the plugin shell only.

## Feishu Bridge Setup

After planner is live, the configuration phase includes Feishu bridge setup:

1. **Verify lark-cli**: planner must check `lark-cli auth status` and run `lark-cli auth login` if the token is expired. This is a user action — planner should surface the auth URL and wait.
2. **Collect group ID**: koder asks the user for the Feishu group ID.
3. **Confirm binding**: koder confirms whether the group binds the current project, switches to another, or creates a new project.
4. **Smoke test**: planner sends a test `OC_DELEGATION_REPORT_V1` to the bound group and verifies koder can parse it.

See `references/feishu-bridge-setup.md` for the complete step-by-step guide.

## Reference Points

- `docs/INSTALL_GUIDE.md` for the human install guide
- `docs/INSTALL.md` for path placeholders and contract
- `core/skills/clawseat/SKILL.md` for the product-level entrypoint
- `core/skills/gstack-harness/SKILL.md` for harness and seat semantics
- `core/skills/cs/SKILL.md` for the first-run `/cs` entrypoint
- `references/feishu-bridge-setup.md` for Feishu bridge setup and smoke test
