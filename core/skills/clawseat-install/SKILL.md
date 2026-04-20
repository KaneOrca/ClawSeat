---
name: clawseat-install
description: Install and bootstrap ClawSeat for Codex or Claude Code, including detecting and reusing existing workspaces or live TUIs. Use when a user asks to install ClawSeat, 安装 ClawSeat, wire a shell bundle, create a starter profile, run preflight/bootstrap, start `koder`, or troubleshoot first-launch and tmux/PTY failures.
---

# ClawSeat Install

## Overview

If your chosen profile uses specialist seats (builder/reviewer/qa/designer), gstack is required; see README profile table.

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

## Prerequisites

Before starting, verify these dependencies are installed:
- **Python >= 3.11** — `python3 --version`
- **tmux** — `tmux -V` (if missing: `brew install tmux`)
- **Node.js >= 22** — `node --version` (needed for OpenClaw)
- **At least one seat CLI** — `claude --version` or `codex --version` or `gemini --version`
- **gstack** (for specialist seats) — if `~/.gstack/repos/gstack` does not exist:
  ```bash
  git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.gstack/repos/gstack
  cd ~/.gstack/repos/gstack && ./setup
  ```
  > ⚠️  First run can take 10+ minutes — `./setup` calls `brew` which may trigger `brew update` with no progress output. Do not cancel.
- **lark-cli** (optional, for Feishu bridge) — `brew install larksuite/cli/lark-cli`

Preflight now supports runtime-aware install gating:

- OpenClaw first install: `python3 "$CLAWSEAT_ROOT/core/preflight.py" install --runtime openclaw --auto-fix`
- Local runtime: `python3 "$CLAWSEAT_ROOT/core/preflight.py" install`

## Memory Seat (Required)

Memory CC (`role = "memory-oracle"`, `tool = claude + api + minimax + MiniMax-M2.7-highspeed`) is the mandatory knowledge oracle for environment facts. On first install, have the ancestor agent seed the local knowledge base first, then start memory before dispatching any work to planner or specialist seats. Every seat — including koder and the ancestor Claude Code agent — must query memory before guessing or asking the user for API keys, provider config, feishu group IDs, or file locations.

**Must start before**:
- Dispatching work to planner or any specialist seat
- Prompting the user for something the machine already knows (e.g. minimax API key in `~/.agents/.env.global`)
- Any seat that needs provider / base URL / endpoint configuration

**Minimum flow**:
1. If `~/.agents/memory/index.json` is missing, seed the local knowledge base first:
   ```bash
   python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/scan_environment.py"
   ```
2. Verify `~/.agents/memory/index.json` exists
3. Start memory seat after the KB exists (before planner):
   ```bash
   python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
     --profile <profile.toml> --seat memory --confirm-start
   ```
4. Query via direct file read (fast) or `--ask` (reasoning):
   ```bash
   # direct
   python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
     --key credentials.keys.MINIMAX_API_KEY.value

   # reasoning
   python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
     --ask "Which provider should designer-1 use?" --profile <profile.toml>
   ```
5. If a fact is missing, notify memory to enrich the KB:
   ```bash
   python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/notify_seat.py" \
     --profile <profile.toml> --source koder --target memory \
     --task-id MEM-ENRICH-001 \
     --message "请补充 <具体事实> 并更新知识库"
   ```

Memory CC's knowledge base lives at `~/.agents/memory/` with file permissions `0600`. Do not copy it off the machine.

Seat-to-memory query protocol: see [references/memory-query-protocol.md](references/memory-query-protocol.md).

## Standard Flow

1. Resolve the canonical project/workspace name and check whether an existing TUI or workspace already exists for it.
2. Read [install-flow.md](references/install-flow.md) for the command sequence and fallback rules.
3. Read [interaction-mode.md](references/interaction-mode.md) before interacting with the user during installation.
4. Confirm `CLAWSEAT_ROOT` points at the ClawSeat checkout.
5. **Install skill symlinks** — this is mandatory, do NOT skip:
   - OpenClaw (Phase 0 + Phase 3):
     1. `python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_bundled_skills.py"` — agent-neutral shared skills
     2. `python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_koder_overlay.py" --agent <agent>` — ask memory for `<agent>`; see [references/install-flow.md](references/install-flow.md) for the full 6-phase flow (Phase 0 install skills → Phase 1 memory → Phase 2 query → Phase 3 overlay → Phase 4 planner config → **Phase 5 Feishu bridge smoke**)
     - After overlay, complete **Phase 5: Feishu Bridge Smoke Test** (7-step canonical): auth check → platform scopes → collect group ID → bind project → requireMention config → smoke test → verify parse. This phase is **mandatory** before any Feishu dispatch. See [references/install-flow.md#phase-5](references/install-flow.md) and [references/feishu-bridge-setup.md](references/feishu-bridge-setup.md).
   - Local CLI: `python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"`
   - Do NOT manually copy skill directories — the scripts create symlinks and check dependencies
6. If the runtime is **OpenClaw or Feishu-facing**:
   - Prefer the canonical staged installer:
     1. `python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_bundled_skills.py"`
     2. `test -f "${CLAWSEAT_REAL_HOME:-$HOME}/.agents/memory/index.json" || python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/scan_environment.py"`
     3. `python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" --profile <profile.toml> --seat memory --confirm-start`
     4. `python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" --memory-dir "${CLAWSEAT_REAL_HOME:-$HOME}/.agents/memory" --search agents`
     5. `python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_koder_overlay.py" --agent <agent>`
     6. `python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/init_koder.py" --workspace "${CLAWSEAT_REAL_HOME:-$HOME}/.openclaw/workspace-<agent>" --project install --profile <profile.toml>`
   - **Ask the user for their Feishu group ID** (format: `oc_xxx`) before bridge setup when possible. If they don't have one yet, configure it later during the canonical bridge flow.
   - After it refreshes the chosen `workspace-<agent>`, **re-read your AGENTS.md and TOOLS.md** to load the koder role details and available commands
   - **You (the current agent) ARE koder** — do NOT create a tmux session for koder
   - The canonical project name is `install`
   - If `planner` is still unconfigured, stop at the printed configuration gate instead of guessing seat config
   - Read the profile fields correctly:
     - `seats` = full roster
     - `materialized_seats` = seats whose runtime/session scaffold already exists after bootstrap
     - `default_start_seats` = first seats frontstage should offer/start
     - `bootstrap_seats` = compatibility/frontstage-bootstrap field, not the backend roster
   - After bootstrap, **you MUST ask the user** for each backend seat's configuration before starting ANY seat. Do NOT use template defaults without user confirmation. For each seat, ask:
     - Tool: Claude Code / Codex / Gemini?
     - Auth: OAuth (recommended) or API key?
     - Provider: which provider?
   - Ask about planner first, then each specialist (builder-1, reviewer-1, etc.) one by one
   - Only after the user confirms each seat's config, start planner:
     ```bash
     python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
       --profile <profile.toml> --seat planner \
       --tool <X> --auth-mode <Y> --provider <Z> --confirm-start
     ```
   - Wait for user to confirm planner OAuth/auth is complete
   - Then dispatch remaining specialist seat startups to planner. **You MUST use `dispatch_task.py`** — do NOT use raw `tmux send-keys`:
     ```bash
     python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/dispatch_task.py" \
       --profile <profile.toml> \
       --source koder --target planner \
       --task-id SEAT-STARTUP \
       --title "Start remaining specialist seats" \
       --objective "Start these seats with user-confirmed configs:
         builder-1: tool=<X> auth-mode=<Y> provider=<Z>
         reviewer-1: tool=<X> auth-mode=<Y> provider=<Z>
         (include all remaining seats with their confirmed configs)"
     ```
   - **CRITICAL: 禁止直接用 `tmux send-keys` 给 seat 发消息。** `tmux send-keys` 没有 1 秒延迟，消息会卡在 TUI 输入框不提交。所有 seat 通信必须用 `dispatch_task.py`（派发任务）、`notify_seat.py`（发通知）、或 `send-and-verify.sh`（tmux transport with auto-retry）。
   - **Never let planner choose seat configs on its own** — all config decisions come from the user through koder
7. If the runtime is **local Claude/Codex**, tell the user to run `/cs`; that wrapper delegates to `cs_init.py`, uses `examples/starter/profiles/install.toml`, and starts `planner`.
8. For manual project-specific installs, run `python3 "$CLAWSEAT_ROOT/core/preflight.py" [project]`.
9. If a fresh project is needed, copy `examples/starter/profiles/starter.toml` for a koder-only entrypoint, `examples/starter/profiles/install.toml` for the canonical install project, or `examples/starter/profiles/full-team.toml` for a six-seat roster to `/tmp/{project}-profile-dynamic.toml`.
10. Bootstrap with `python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py" --profile /tmp/{project}-profile-dynamic.toml --project-name {project}` (do NOT pass `--start` in OpenClaw mode — koder is already running).
11. In local CLI mode only: start koder with `start_seat.py --seat koder`. In OpenClaw mode: skip this step — you are koder.
12. Treat OAuth login, workspace trust, and permission prompts as normal first-launch onboarding for backend seats.

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

## Update / Refresh

After `git pull` or any ClawSeat code update, workspace MD files (AGENTS.md, TOOLS.md, WORKSPACE_CONTRACT.toml, settings.local.json) are stale. Run:

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py"
```

Zero arguments needed — auto-detects project, profile, koder workspace, and feishu group ID from existing WORKSPACE_CONTRACT.toml. Regenerates all seat workspace files using the latest template and profile. **After refresh, re-read your AGENTS.md and TOOLS.md.**

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
