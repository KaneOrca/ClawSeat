# ClawSeat Install Flow

## Critical: koder identity

There are two runtime modes. The koder identity rule differs:

- **OpenClaw / Feishu mode**: You (the current agent) ARE koder. You do NOT
  need a tmux session. Only backend seats (planner, builder, reviewer, qa,
  designer) run in tmux. The canonical project name is `install`.
- **Local CLI mode** (`/cs`): koder runs as a tmux session alongside other
  seats. `cs_init.py` handles koder startup.

Never create a project named after yourself (e.g. `koder-frontstage`).
Never run `start_seat.py --seat koder` in OpenClaw mode.

## Decision Tree

1. First check whether there is already a workspace, seat, or TUI for the requested project/seat label.
2. If one exists, reuse it and report that the install is a resume/recovery path, not a fresh bootstrap.
3. If the user wants OpenClaw or Feishu to load ClawSeat, use the `clawseat` product skill or the OpenClaw plugin shell as the entrypoint.
4. If the user wants a local Claude/Codex runtime to load ClawSeat, use the relevant bundle first, then install the entry skills.
5. If the user is following the local first-run shortcut path, have them execute `/cs`.
6. If the user wants a new project outside the canonical install project, bootstrap a starter profile and run the harness.

## Required Environment

```sh
export CLAWSEAT_ROOT="/path/to/ClawSeat"
```

If `CLAWSEAT_ROOT` is unset, check the current checkout before doing anything else.

## AGENT_HOME — lark-cli in tmux seats (G12)

`lark-cli` auth config lives under the **real user HOME**, not the isolated seat runtime HOME. When running from inside a tmux seat, the seat's `HOME` points to a sandbox path. Without `AGENT_HOME`, lark-cli reads the wrong config and fails.

**Before any lark-cli call inside a tmux seat**:

```sh
export AGENT_HOME=/Users/<real-user>   # e.g. /Users/ywf
```

The ClawSeat scripts pass `AGENT_HOME` automatically when launched via `start_seat.py`. If you see `FileNotFoundError: HOME/.openclaw not found` from `send_delegation_report.py` inside a tmux seat, check that `AGENT_HOME` is set.

See `references/feishu-bridge-setup.md` for the full troubleshooting context.

## Phase 0 — Bootstrap Project Workspace

Bootstrap is the **headline P0 action**: it creates `~/.agents/projects/<project>/`, the profile runtime, the seat session.toml files (incl. memory), and the tasks_root. Without bootstrap, `start_seat.py --seat memory` at P1 exits because `~/.agents/sessions/<project>/memory/session.toml` does not exist.

### Step 0.1 — Install bundled skills (idempotent prerequisite)

Agent-neutral skill symlinks into `~/.openclaw/skills/`. One-time per Claude Code install; idempotent on re-run.

```sh
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_bundled_skills.py"
```

- Creates symlinks for `clawseat`, `clawseat-install`, `clawseat-koder-frontstage`, and memory-oracle skills.
- Checks external dependencies: gstack + lark-cli.
- exit 0 = all OK; exit 2 = external dependency missing (gstack/lark-cli).

### Step 0.2 — Profile prep + bootstrap_harness (headline)

```sh
PROJECT=my-project
PROFILE_TEMPLATE="$CLAWSEAT_ROOT/examples/starter/profiles/install-with-memory.toml"  # declares the memory seat P1 needs
cp "$PROFILE_TEMPLATE" "/tmp/${PROJECT}-profile-dynamic.toml"

# B2: tasks_root is quoted in the template ("~/.agents/tasks/install").
# A simple `sed 's/install/my-project/'` misses the quote boundary. Use Python:
python3 - <<PY
import re, pathlib
p = pathlib.Path("/tmp/${PROJECT}-profile-dynamic.toml")
t = p.read_text()
t = t.replace('project_name = "install"', 'project_name = "${PROJECT}"')
t = re.sub(r'(tasks_root\s*=\s*["\']?)~/.agents/tasks/install',
          r'\g<1>~/.agents/tasks/${PROJECT}', t)
p.write_text(t)
PY

python3 "$CLAWSEAT_ROOT/core/preflight.py" "$PROJECT"
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --project-name "$PROJECT" \
  --start
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/render_console.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml"
```

**Verify** (hard precondition for P1):
```sh
test -f ~/.agents/sessions/${PROJECT}/memory/session.toml && echo "bootstrap_ok"
```

- `install-with-memory.toml` (default) is `install.toml` plus a `memory` seat declaration — required for the P1 memory flow.
- `starter.toml` creates a minimal frontstage entrypoint (no memory seat — not compatible with canonical P1).
- `install.toml` (legacy) lacks a `memory` seat; P1 will fail unless you add it to the roster before bootstrap.
- `full-team.toml` creates `koder`, `planner`, `builder-1`, `reviewer-1`, `qa-1`, and `designer-1` workspaces in one bootstrap.
- Even with `full-team.toml`, `--start` still only auto-starts `koder`; other seats require explicit confirmation and launch.
- `clawseat` is the product path for OpenClaw/Feishu; `/cs` is the local-runtime exception path that counts as explicit approval to bootstrap or resume `install` and start `planner`.
- `qa-1` is not part of the default `/cs` first-launch roster; bring it up only for test / smoke / regression heavy chains, usually after the bridge or implementation lane has started.

> **Partial reinstall / repair**: All per-step scripts are idempotent. If `~/.agents/sessions/${PROJECT}/memory/session.toml` already exists (P0.2 produced it), skip straight to Phase 1 (memory). Re-running `install_bundled_skills.py` is also safe — it only patches missing symlinks.

## Phase 1 — Memory Seat + Comms Smoke

Memory seat is the knowledge oracle for environment facts (credentials, API keys, provider config, feishu group IDs). P1 combines launching the seat with a round-trip smoke that both exercises the tmux/handoff path and tells memory to populate its KB.

### Step 1.1 — Start memory seat

```sh
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" --seat memory --confirm-start
```

**Verify**: `tmux has-session -t ${PROJECT}-memory-claude 2>/dev/null && echo seat_ok`

**Halt condition**: session not running → USER_DECISION_NEEDED (check P0.2 session.toml existence first).

### Step 1.2 — Ancestor → Memory comms smoke (LEARNING REQUEST)

One message exercises: tmux send-keys delivery, memory `/clear` Stop hook timing, `complete_handoff.py` receipt, and — via memory's SKILL.md routing — a `scan_environment.py` run that populates `machine/`.

```sh
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/notify_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --source ancestor --target memory \
  --task-id MEMORY-SCAN-001 --kind learning \
  --message "LEARNING REQUEST: Run scan_environment.py --output ~/.agents/memory to populate the machine/ knowledge base. Confirm 5 files (credentials, network, openclaw, github, current_context) land."
```

> **Why notify_seat, not dispatch_task**: the T22 guard (`assert_target_not_memory`) blocks `dispatch_task.py --target memory` with exit 2 because memory does not read `TODO.md`. `notify_seat.py` is the canonical path for sending memory a learning request — see [tests/test_memory_target_guard.py](../../../../tests/test_memory_target_guard.py) and `core/templates/shared/TOOLS/memory.md`.

### Step 1.3 — Verify KB populated + receipt landed

```sh
for f in credentials network openclaw github current_context; do
  test -f ~/.agents/memory/machine/${f}.json && echo "machine/${f}.json ok"
done

ls ~/.agents/tasks/${PROJECT}/MEMORY-SCAN-001/ 2>/dev/null | grep -E 'ack|receipt|done' || echo "WARN: no ACK yet — poll again after memory /clear fires"
```

**Halt condition**: any `machine/*.json` missing after 60s → USER_DECISION_NEEDED: memory scan did not complete. Do NOT proceed to P2 with empty KB.

Every other seat (including koder and the ancestor Claude Code agent) must query memory before guessing environment facts. See [memory-query-protocol.md](memory-query-protocol.md) for the mandatory query/escalation contract.

If memory seat is not declared in the profile roster, add it before rerunning bootstrap — memory is no longer optional.

## Phase 2 — Query Memory → Confirm Target Agent with User

Before applying any per-agent overlay, query memory to enumerate the available OpenClaw agents, then **ask the user which agent** should receive the koder overlay. Do not hardcode "koder" and do not auto-pick even if memory returns a single candidate — agent selection is a user decision.

```sh
# G15 — correct syntax: use --memory-dir + --key or --search (NOT --file --section)
# Search for known agents
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
  --memory-dir ~/.agents/memory \
  --search agents

# Or reasoning query with profile context
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
  --ask "which OpenClaw agent should receive the koder overlay?" --profile "/tmp/${PROJECT}-profile-dynamic.toml"
```

If memory returns no result, escalate to memory seat per the [query protocol](memory-query-protocol.md) before proceeding. Do not guess.

## Phase 3 — Install Koder Overlay

Apply the ClawSeat koder templates into the chosen agent's workspace (`~/.openclaw/workspace-<agent>/skills/`). Requires `--agent <NAME>` — the name resolved in Phase 2:

```sh
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_koder_overlay.py" \
  --agent <chosen-agent-name>
```

Optional flags:
- `--openclaw-home <path>` — override `~/.openclaw` (default)
- `--dry-run` — preview changes without writing

Omitting `--agent` → exit 2. If this happens, return to Phase 2 and consult the memory seat query protocol.

## Phase 4 — Start Planner + Configuration

> **AGENT_HOME automatic resolution**: All `agent_admin` scripts and `install_complete.py`
> automatically detect when they are running inside a seat sandbox HOME
> (`~/.agents/runtime/identities/<tool>/<auth>/<identity>/home/`) and fall back to the
> real operator HOME via `pwd.getpwuid`. The `CLAWSEAT_REAL_HOME` env var provides an
> explicit override if auto-detection fails. You do **not** need to set `AGENT_HOME`
> manually — it is injected by `start_seat.py` at seat startup.
> Use `CLAWSEAT_SANDBOX_HOME_STRICT=1` only in tests to force sandbox paths.

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"
```

Then, inside OpenClaw/Feishu, invoke `clawseat`. Inside local Claude Code or Codex, you may run:

```text
/cs
```

`/cs` delegates to:

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/cs_init.py"
```

That wrapper will:

- ensure `/tmp/install-profile-dynamic.toml` exists from `examples/starter/profiles/install.toml`
- run preflight for `install`
- bootstrap or repair the canonical `install` workspace
- ensure every declared seat already has its managed scaffold (`session.toml`,
  isolated `runtime_dir`, workspace guide, `WORKSPACE_CONTRACT.toml`, `repos/`,
  and idle `TODO.md`) before dispatch begins
- in local CLI mode: start or resume `koder` as a tmux session
- in OpenClaw mode: skip koder startup — the current agent IS koder
- start `planner` (the only backend seat started during bootstrap)
- render the install console state
- then tell frontstage to finish the OpenClaw/Feishu bridge:
  ask the user for the group ID, keep `main` on `requireMention=true`, keep
  the project-facing `koder` account on `requireMention=false` by default,
  require an explicit project-binding confirmation, then delegate the smoke
  test to `planner`, tell the user `收到测试消息即可回复希望完成什么任务`, and
  bring up review in parallel
- after bootstrap, enter a configuration phase before normal task execution:
  finish project binding, Feishu bridge binding, provider/auth selection, API
  key setup, and base URL / endpoint configuration
- configuration should be split into configuration entry and configuration
  verification; do not collapse secret entry and validation into one opaque step
- once the project-group binding exists, planner decision gates and closeouts
  should use that same group through `OC_DELEGATION_REPORT_V1`; do not rely on
  the legacy auto-broadcast path as a control packet

## First-Launch Notes

- Fresh Claude seats may ask for OAuth login, workspace trust, or permission confirmation.
- Those prompts are normal onboarding, not install failures.
- A pre-existing TUI is not "new install" state; do not create a second project when the first seat is already present.
- For non-frontstage seats, require explicit confirmation before launching them.

## User And Agent Interaction Mode

- The agent should auto-run the deterministic setup steps: env check, preflight, starter profile preparation, bootstrap, and console verification.
- The agent should pause only for real user actions: CLI login, workspace trust, permission prompts, or moving to a host terminal that supports PTY/tmux.
- The agent should keep the user informed of which stage is active and whether `koder` is merely bootstrapped or already live.
- The agent must not silently launch `planner` or specialist seats during manual installation.
- `/cs` counts as an explicit user request to launch `planner` for the canonical `install` project.
- once `planner` is up, the agent should proactively ask for the Feishu group ID
  needed for the OpenClaw bridge; do not wait for the user to suggest group
  wiring
- once the user provides the group ID, the agent should first confirm whether
  the group binds the current project, another existing project, or a new
  project; only then should it delegate the bridge smoke test to `planner`,
  tell the user `收到测试消息即可回复希望完成什么任务`, and start
  `reviewer-1` in parallel when that seat exists
- if the current chain is verification-heavy, start `qa-1` in parallel with
  or immediately after `reviewer-1`; `qa-1` owns the smoke/regression lane
  rather than execution planning
- if configuration changes touch Feishu bridge settings, API keys, key
  rotation, base URL / endpoint values, or auth/provider bindings, treat that
  as configuration verification work and prefer launching `qa-1`
- `qa-1` should verify connectivity and behavior, not become the long-term
  owner of plaintext secrets
- when the closeout eventually comes back to frontstage, koder should read the
  linked delivery trail, reconcile the stage result, and update the project
  docs before summarizing to the user

## Common Failures

| Symptom | Meaning | Action |
|---|---|---|
| `Device not configured` | Host PTY/tmux limitation | Tell the user to run in a real terminal session |
| `CLAWSEAT_ROOT` missing | Environment not initialized | Export the repo root and rerun preflight |
| `dynamic profile not found` | Project profile missing | `install` 项目会自动从 shipped `install.toml` 补种；其他项目需先创建 `/tmp/{project}-profile-dynamic.toml` |
| `tmux server` absent | tmux not running | Start a tmux server, then rerun preflight |
| memory seat not started | Query protocol unavailable; seats will guess or block | Run `start_seat.py --seat memory --confirm-start` immediately after bootstrap |
| `install_koder_overlay` exit 3 | Target agent workspace does not exist | Verify the OpenClaw agent was created first, or query memory for agent status |
| Feishu event scope missing | 群消息 not delivered without @mention | Enable `im:message.group_msg:receive` in Feishu Open Platform → Event Subscriptions |

## Phase 5: Feishu Bridge Smoke Test

After Phase 4 seat provisioning, complete the Feishu bridge setup. This is a **mandatory** phase — do not skip it. Full guide: [feishu-bridge-setup.md](feishu-bridge-setup.md).

### Step 5.1: Verify lark-cli auth

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py" --check-auth
```

Expected: `"status": "ok"`. If not, run `lark-cli auth login` in a terminal with browser access (**user action** — agent cannot complete this).

**In tmux seats**: lark-cli reads auth from the real user HOME, not the seat sandbox. Ensure `AGENT_HOME` is set:

```bash
export AGENT_HOME=/Users/<real-user>
```

**Halt condition**: auth not ok → USER_DECISION_NEEDED.

### Step 5.2: Enable Feishu platform scopes (pre-smoke, user action)

In Feishu Open Platform → App, enable **before** running any smoke test:

**Event Subscriptions**:
- `im:message` — 聊天消息事件
- `im:message.group_msg:receive` — 群消息免@（**critical**: without this, koder only responds to @mentions）
- `im:chat:access` — 聊天管理

**Permissions & Scopes**:
- `im:chat` — 读写群消息
- `im:chat.members` — 读取群成员

Then publish a new app version: 开放平台 → 版本管理与发布 → 提交审核 → 发布 (required version: **2026.4.9+**).

**Halt condition**: scopes not enabled/published → USER_DECISION_NEEDED: enable and publish before proceeding.

### Step 5.3: Collect Feishu group ID

Ask the user for the group ID, or scan sessions:

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/find_feishu_group_ids.py"
```

Format: `oc_` + hex string (e.g. `oc_0e1305956760980a9728cb427375c3b3`).

**Confirm with user before binding**:
1. Is this group for the current project?
2. Or switch to an existing project?
3. Or create a new project?

One project = one group.

### Step 5.4: Bind project to group

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, "$CLAWSEAT_ROOT")
from core.skills.clawseat_install.scripts.bind_project import bind_project_to_group
bind_project_to_group(
    project="$PROJECT",
    group_id="$GROUP_ID",
    bound_by="<user>",
    authorized=True,
)
PY
```

Verify: `~/.agents/projects/$PROJECT/BRIDGE.toml` exists.

### Step 5.5: Configure requireMention

| Group type | requireMention | Reason |
|---|---|---|
| Main koder-facing group | `true` (default) | Prevents noise from unrelated messages |
| Project koder group | `false` | Enables no-@mention dispatch for chain closeouts |

See `references/feishu-group-no-mention.md`.

### Step 5.6: Smoke test (dry-run first, then real)

```bash
# Dry-run — verify envelope format
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py" \
  --project "$PROJECT" --lane planning --task-id BRIDGE-SMOKE-001 \
  --report-status done --decision-hint proceed \
  --user-gate none --next-action consume_closeout \
  --summary 'Feishu bridge smoke test' --dry-run

# Send for real
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py" \
  --project "$PROJECT" --lane planning --task-id BRIDGE-SMOKE-001 \
  --report-status done --decision-hint proceed \
  --user-gate none --next-action consume_closeout \
  --summary 'Feishu bridge smoke test — if you see this message, the bridge is working' \
  --chat-id "$GROUP_ID"
```

Tell the user: `收到测试消息即可回复希望完成什么任务`

### Step 5.7: Verify koder receives and parses

Koder should receive `OC_DELEGATION_REPORT_V1` in the group and confirm:
- `project=$PROJECT` matches
- `task_id=BRIDGE-SMOKE-001`
- `report_status=done` + `next_action=consume_closeout` → auto-advance

**Halt condition**: delivery fails → check AGENT_HOME (G12), platform scopes (G14), lark-cli auth; escalate via error reference in [feishu-bridge-setup.md](feishu-bridge-setup.md).

### Common Feishu Failures

| Symptom | Meaning | Action |
|---|---|---|
| `auth_expired` / `auth_needs_refresh` | OAuth token expired | User runs `lark-cli auth login` in terminal with browser access |
| `lark_cli_missing` | lark-cli not in PATH | `brew install larksuite/cli/lark-cli` |
| `event scope missing` | 群消息 not delivered without @mention | Enable `im:message.group_msg:receive` + publish new app version |
| `group_not_found` / 404 | Group ID invalid or bot not in group | Verify group ID; ensure bot app is added to target group |
| `message_id` duplicate / no delivery | Message sent but koder doesn't see it | Check `requireMention=false` + restart OpenClaw gateway |
