# ClawSeat Install Flow

An **interactive 6-phase flow** driven by an ancestor Claude Code session
that overlays ClawSeat onto an existing OpenClaw agent. Do NOT run
individual scripts out of order; halt conditions and user-decision gates
exist on purpose.

Narrative in one paragraph:

> The ancestor scans the host for API credentials, bootstraps the project
> workspace, starts the memory seat, tells memory to scan the OpenClaw
> configuration, waits for the operator to report back, asks the operator
> which OpenClaw agent to overlay koder onto, installs the overlay,
> prompts the operator to verify koder identity via `/new` in OpenClaw and
> to create a Feishu group, starts planner, has planner push a Feishu
> smoke message, and finally hands off control to koder — the ancestor
> goes standby and only re-engages to debug.

## Critical: koder identity

There are two runtime modes. This flow is for the **overlay mode**:

- **OpenClaw / Feishu overlay mode** (this flow): ClawSeat templates are
  overlaid onto an existing OpenClaw agent workspace. The chosen agent
  (e.g. `mor`, `cartooner`) becomes koder. Koder is NOT a tmux seat —
  only `memory`, `planner`, `builder-*`, `reviewer-*`, `qa-*`,
  `designer-*` run in tmux.
- **Local CLI mode** (`/cs`): `cs_init.py` handles a self-contained
  koder-as-tmux startup. Not covered here.

Never create a project named after yourself (e.g. `koder-frontstage`).
Never run `start_seat.py --seat koder` in overlay mode.

## Required Environment

```sh
export CLAWSEAT_ROOT="/path/to/ClawSeat"
```

If `CLAWSEAT_ROOT` is unset, check the current checkout before doing
anything else.

## AGENT_HOME — lark-cli in tmux seats

`lark-cli` auth config lives under the **real user HOME**, not the
isolated seat runtime HOME. When running from inside a tmux seat, the
seat's `HOME` points to a sandbox path. Without `AGENT_HOME`, lark-cli
reads the wrong config and fails.

The ClawSeat scripts pass `AGENT_HOME` automatically when launched via
`start_seat.py`. If you see `FileNotFoundError: HOME/.openclaw not found`
from `send_delegation_report.py` inside a tmux seat, set
`export AGENT_HOME=/Users/<real-user>` before the call.

See [`feishu-bridge-setup.md`](feishu-bridge-setup.md) for the full
troubleshooting context.

---

## Phase 0 — Preflight, Credentials, Bootstrap

Scan the host for the credentials memory will authenticate with, seed
them, and only then build the project workspace scaffolding.
Credential discovery runs **before** bootstrap on purpose: bootstrap's
`seed_empty_secret_from_peer` reads `~/.agents/.env.global`, so
writing `.env.global` first lets a single bootstrap pass produce a
complete `memory.env`. Running bootstrap on an empty `.env.global`
produces an empty `memory.env` and memory lands in OAuth-prompt mode
at P1.2 (see Common Failures: `memory.env is empty`).

### Step 0.0 — Preflight (halt on failure)

```sh
python3.11 "$CLAWSEAT_ROOT/core/preflight.py" install
```

Verifies Python ≥ 3.11, tmux, gstack, lark-cli, and repo integrity. If
any check is HARD_BLOCKED the script exits non-zero — **stop and fix
before proceeding**. Installing Python 3.11 is the most common blocker
on macOS (default `python3` is 3.9, which lacks `tomllib` and will
crash downstream `agent_admin.py` subprocesses).

| Failure | Fix |
|---|---|
| `python 3.9 < 3.11 (tomllib requires 3.11+)` | `brew install python@3.11` and rerun |
| `tmux not found` | `brew install tmux` |
| `gstack skills missing` | `cd ~/.gstack/repos/gstack && ./setup` |
| `CLAWSEAT_ROOT` missing | `export CLAWSEAT_ROOT=/path/to/ClawSeat` |

### Step 0.1 — Install bundled OpenClaw skills (idempotent prerequisite)

Symlinks the agent-neutral shared skills into `~/.openclaw/skills/`.

```sh
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_bundled_skills.py"
```

- Creates symlinks for `clawseat`, `clawseat-install`,
  `clawseat-koder-frontstage`, `gstack-harness`, `memory-oracle`,
  `socratic-requirements`, `agent-monitor`, `lark-shared`, `lark-im`,
  `tmux-basics`, `cs`.
- Checks for external dependencies: gstack + lark-cli.
- exit 0 = all OK; exit 2 = external dependency missing.

### Step 0.2 — Install entry skills (ancestor / local CLI)

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"
```

Symlinks `clawseat`, `clawseat-install`, `cs` into `~/.claude/skills/`
and `~/.codex/skills/` so the ancestor (and any other Claude/Codex on
this host) can invoke `/clawseat` and `/cs`.

### Step 0.3 — Ancestor credential scan + seed (halt if no creds)

Ancestor runs a **narrow** scan for Claude-compatible API credentials
and writes them to `~/.agents/.env.global` + `memory.env` so memory
can authenticate in Phase 1. This step **must complete before**
bootstrap (P0.5) — otherwise `seed_empty_secret_from_peer` finds
nothing to propagate and memory lands in OAuth prompt mode.

```sh
# Minimal scan: credentials + oauth evidence only. Ancestor uses this
# to pre-seed memory's secret file; it does NOT populate machine/ KB
# here — that's memory's job in Phase 1.
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/scan_environment.py" \
  --only credentials --output /tmp/ancestor-precheck
```

Then ask the operator which provider/auth to bind to the memory seat.
**Recommend MiniMax API** (cheapest per-turn cost; Anthropic-compatible
endpoint). Accept: `minimax`, `xcode-best`, `anthropic-oauth`.

Seed `.env.global` + `memory.env` (assuming MiniMax is chosen):

```sh
mkdir -p ~/.agents
cat > ~/.agents/.env.global <<EOF
MINIMAX_API_KEY=<from credentials scan>
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
EOF
chmod 600 ~/.agents/.env.global

# Defensive: write memory.env directly so bootstrap's seed logic is
# not the single point of failure.
mkdir -p ~/.agents/secrets/claude/minimax
cat > ~/.agents/secrets/claude/minimax/memory.env <<EOF
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_AUTH_TOKEN=<from credentials scan>
ANTHROPIC_MODEL=MiniMax-M2.7-highspeed
EOF
chmod 600 ~/.agents/secrets/claude/minimax/memory.env
```

**Halt conditions** (three cases):

1. **API key found** → seed `.env.global` + `memory.env`, proceed.
2. **No API key but OAuth evidence** (`credentials.json.oauth.has_any`
   is `true` → `~/.claude/credentials.json` exists OR
   `CLAUDE_CODE_OAUTH_TOKEN` in env) → USER_DECISION_NEEDED: present
   both paths, ask operator to pick MiniMax API or OAuth.
3. **No API key AND no OAuth** → USER_DECISION_NEEDED: ask operator to
   supply a MiniMax / Anthropic API key OR run `claude auth login`.

Do not fabricate credentials in any case.

### Step 0.4 — Generate project profile

```sh
PROJECT=install
PROFILE_TEMPLATE="$CLAWSEAT_ROOT/examples/starter/profiles/install-with-memory.toml"
cp "$PROFILE_TEMPLATE" "/tmp/${PROJECT}-profile-dynamic.toml"

# Profile substitution (B2 — handle quoted strings)
python3 - <<PY
import re, pathlib
p = pathlib.Path("/tmp/${PROJECT}-profile-dynamic.toml")
t = p.read_text()
t = t.replace('project_name = "install"', 'project_name = "${PROJECT}"')
t = re.sub(r'(tasks_root\s*=\s*["\']?)~/.agents/tasks/install',
          r'\g<1>~/.agents/tasks/${PROJECT}', t)
p.write_text(t)
PY
```

`install-with-memory.toml` is required — it declares the `memory` seat.
`install.toml` (no memory) does not work with this flow.

### Step 0.5 — Bootstrap workspace (**no `--start`**)

```sh
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --project-name "$PROJECT"
```

**Do NOT pass `--start`** in overlay mode. `--start` auto-launches the
profile's `heartbeat_owner` (koder) as a tmux seat, which is wrong for
overlay mode — koder will be the chosen OpenClaw agent, not a tmux seat.

**Verify** (hard precondition for P1):

```sh
test -f ~/.agents/sessions/${PROJECT}/memory/session.toml && echo "bootstrap_ok"
```

### Step 0.6 — Refresh workspaces

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml"
```

Synchronizes ClawSeat templates into each seat's workspace.

---

## Phase 1 — Memory seat online + system knowledge base

### Step 1.1 — Start memory seat

```sh
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --seat memory --confirm-start
```

**Verify**: `tmux has-session -t ${PROJECT}-memory-claude` → 0

### Step 1.2 — (USER ACTION) Complete memory TUI onboarding

`start_seat.py` already opens an iTerm window attached to the new
memory seat (via its internal `window open-engineer`). **Do NOT run
an additional `osascript`** — that produces a duplicate iTerm window
attached to the same tmux session.

The operator clicks through the first-launch sequence in the iTerm
window that `start_seat.py` opened:

| Prompt | Answer |
|---|---|
| Theme picker (1-7) | `1` + Enter |
| Security notes | Enter |
| Trust this folder | `1` + Enter |
| Login method | `2` + Enter (Anthropic Console account — uses `ANTHROPIC_API_KEY`) |

After onboarding, the TUI shows `❯` with `MiniMax-M2.7-highspeed · API
Usage Billing` in the banner.

**Halt condition**: TUI shows `Claude account with subscription` (OAuth
mode) instead of `API Usage Billing` → `memory.env` credentials did not
load. Go back to P0.3.

### Step 1.3 — Dispatch the system-scan task

Ancestor sends memory a canonical LEARNING REQUEST to scan the host and
build its `machine/` knowledge base. The emphasis is **OpenClaw
configuration** so Phase 2 agent enumeration has data.

```sh
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/notify_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --source ancestor --target memory \
  --task-id MEMORY-SCAN-001 --kind learning \
  --message "LEARNING REQUEST: Run scan_environment.py (no --output flag — the default resolves to the operator's real ~/.agents/memory via pwd-based _real_user_home(), bypassing the seat sandbox HOME). Focus on openclaw (OpenClaw agents, workspace directories, feishu bindings). Confirm 5 machine/*.json files are written. Report completion via complete_handoff.py."
```

> **Why no `--output` flag**: bash in the memory seat expands `~` /
> `$HOME` against the seat's isolated sandbox HOME (e.g.
> `~/.agents/runtime/identities/claude/api/.../home`). An explicit
> `--output ~/.agents/memory` would therefore write to the sandbox
> instead of the operator's real home. Omitting the flag lets
> `scan_environment.py`'s `DEFAULT_OUTPUT = _real_user_home() /
> ".agents" / "memory"` resolve correctly via `pwd.getpwuid`.

> **Why notify_seat, not dispatch_task**: the T22 guard
> (`assert_target_not_memory`) blocks `dispatch_task.py --target memory`
> with exit 2 because memory does not read `TODO.md`. `notify_seat.py`
> is the canonical path for learning requests — see
> [`test_memory_target_guard.py`](../../../../tests/test_memory_target_guard.py)
> and [`TOOLS/memory.md`](../../../templates/shared/TOOLS/memory.md).

### Step 1.4 — (USER SYNC POINT) Wait for operator to report

Memory runs `scan_environment.py` in its TUI, writes 5 files to
`~/.agents/memory/machine/`, delivers a receipt via
`complete_handoff.py`, and `/clear`s its context. The operator watches
the memory iTerm window and reports back to the ancestor when memory
confirms `machine/ KB ready` or equivalent.

Ancestor blocks here. **Do not poll memory directly** — the sync is
operator-visual + operator-verbal.

**Halt condition**: operator does not report within a reasonable window
(5 minutes) → USER_DECISION_NEEDED: memory did not respond. Check the
memory iTerm for errors.

### Step 1.5 — Verify KB landed

After the operator reports, ancestor verifies:

```sh
for f in credentials network openclaw github current_context; do
  test -f ~/.agents/memory/machine/${f}.json && echo "machine/${f}.json ok"
done

ls ~/.agents/tasks/${PROJECT}/MEMORY-SCAN-001/ 2>/dev/null \
  | grep -E 'ack|receipt|done' || echo "WARN: no ACK receipt yet"
```

**Halt condition**: any `machine/*.json` missing → the scan did not
complete. Re-send the LEARNING REQUEST or consult the memory iTerm.

---

## Phase 2 — Query memory → operator picks target agent

### Step 2.1 — Ask memory for the OpenClaw agent list

```sh
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
  --memory-dir ~/.agents/memory --search agents
```

Or a reasoning query:

```sh
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
  --memory-dir ~/.agents/memory \
  --ask "Which OpenClaw agents exist on this host? List with workspace paths."
```

### Step 2.2 — Present candidates, wait for operator to choose

Ancestor shows the operator the full list + any contextual notes
(existing skills overlay, active state, group memberships). **Do not
auto-pick** — agent selection is a user decision even if only one
candidate exists.

**Halt condition**: memory returns no agents → OpenClaw isn't installed
or `~/.openclaw/workspace-*` dirs are empty. Block and ask operator.

---

## Phase 3 — Koder overlay + external confirmations

### Step 3.1 — Install koder overlay

```sh
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_koder_overlay.py" \
  --agent <CHOSEN_AGENT>
```

Adds ClawSeat skill symlinks under
`~/.openclaw/workspace-<CHOSEN_AGENT>/skills/`.

**Verify**: `ls ~/.openclaw/workspace-<CHOSEN_AGENT>/skills/ | wc -l` ≥ 6

### Step 3.2 — Finalize koder scaffold

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/init_koder.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --on-conflict backup
```

Generates `TOOLS/` and `WORKSPACE_CONTRACT.toml` inside the agent's
workspace. Existing non-ClawSeat files are moved to `.backup-<ts>/`.

### Step 3.3 — Auto-configure Feishu no-mention (F10)

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/configure_koder_feishu.py" \
  --agent <CHOSEN_AGENT>
```

Sets `channels.feishu.accounts.<agent>.requireMention=false` in
`~/.openclaw/openclaw.json`. After changing, restart the gateway:
`exec "pnpm --dir ~/.openclaw/apps/gateway openclaw gateway restart"`.

### Step 3.4 — (USER ACTION) Verify koder identity in OpenClaw

> **Note**: `requireMention=false` is already set — operator can chat
> with `<CHOSEN_AGENT>` directly without @mention.

Tell the operator:

> Please open OpenClaw and send `/new` to the `<CHOSEN_AGENT>` agent.
> It should respond as **koder** with the ClawSeat frontstage skill loaded.
> Come back and confirm.

**Halt condition**: operator reports `<CHOSEN_AGENT>` still behaves as
the pre-overlay agent → overlay did not take effect. Re-run
`refresh_workspaces.py` and P3.1-3.3.

### Step 3.5 — (USER ACTION) Create Feishu group for koder

Tell the operator:

> Please create a Feishu group named e.g. "koder-<project>". Add the
> OpenClaw Feishu bot to the group. Give me the group ID
> (format: `oc_<alnum>`).

The operator creates the group and provides the `oc_xxx` id.

**Halt condition**: operator can't create group (bot missing / scope not
enabled) → escalate to [`feishu-bridge-setup.md`](feishu-bridge-setup.md).

---

## Phase 4 — Planner + Feishu smoke (end-to-end bridge test)

### Step 4.1 — Start planner seat

```sh
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --seat planner --confirm-start
```

(USER ACTION) Operator completes planner TUI onboarding in iTerm
(same 4-key sequence as memory in P1.2).

### Step 4.2 — Bind project to Feishu group

```sh
python3 - <<PY
import sys; sys.path.insert(0, "$CLAWSEAT_ROOT")
from core.skills.clawseat_install.scripts.bind_project import bind_project_to_group
bind_project_to_group(
    project="$PROJECT",
    group_id="<GROUP_ID from P3.5>",
    bound_by="operator",
    authorized=True,
)
PY
```

Writes `~/.agents/projects/$PROJECT/BRIDGE.toml`.

Apply group-level `requireMention=false` (F10):

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/configure_koder_feishu.py" \
  --agent <CHOSEN_AGENT> --group-id "<GROUP_ID from P3.5>"
```

### Step 4.3 — Dispatch smoke task to planner

Ancestor delegates the smoke send to planner (not to itself) — that
exercises the real ancestor → planner → Feishu → koder chain:

```sh
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/dispatch_task.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --source ancestor --target planner \
  --task-id BRIDGE-SMOKE-001 \
  --title "Feishu bridge smoke" \
  --objective "Send OC_DELEGATION_REPORT_V1 to the project group to prove the bridge works. Use --chat-id <GROUP_ID>." \
  --intent ship --reply-to ancestor
```

Planner picks this up from `TODO.md`, runs
`send_delegation_report.py --chat-id <GROUP_ID> ...`, and posts the
smoke message to the Feishu group.

### Step 4.4 — (USER ACTION) Confirm koder receives the smoke

Tell the operator:

> Check the Feishu group. You should see an `OC_DELEGATION_REPORT_V1`
> envelope arrive, and koder (`<CHOSEN_AGENT>` in OpenClaw) should react
> to it. Come back and confirm koder saw the smoke.

**Halt condition**: smoke sent but koder did not react → Feishu event
scope is missing (`im:message.group_msg:receive`) OR `requireMention` is
still `true` on the project group. See
[`feishu-bridge-setup.md`](feishu-bridge-setup.md) steps 5.2-5.5.

---

## Phase 5 — Handoff

Once the smoke succeeds, the install is complete. Ancestor steps back:

- From now on, the **operator talks to koder directly** (via OpenClaw or
  Feishu). Koder drives normal task execution.
- **Ancestor goes standby**. The operator re-engages the ancestor only
  to debug install failures, rerun Phase 0-4 on a new agent, or
  regenerate scaffolding.
- `planner`, `builder-*`, `reviewer-*`, `qa-*`, `designer-*` seats are
  brought up **lazily** by koder when a task chain needs them — not by
  ancestor eagerly.

No further ancestor action is required unless the operator asks.

---

## Interaction Mode Summary

- The ancestor auto-runs deterministic plumbing (P0.1-0.2, P0.4-0.6,
  P1.1/1.3/1.5, P2.1, P3.1-3.3, P4.1-4.3).
- The ancestor pauses at **operator-decision gates**: P0.3 provider
  pick, P1.4 memory-scan-complete signal, P2.2 target agent pick, P3.4
  koder identity verification, P3.5 Feishu group creation, P4.4 smoke
  confirmation.
- The ancestor keeps the operator informed of which phase is live and
  which seats are running.
- The ancestor must not silently launch `planner` or specialist seats
  — always confirm before `start_seat` on a non-memory seat.

## Common Failures

| Symptom | Meaning | Action |
|---|---|---|
| `Device not configured` | Host PTY/tmux limitation | Tell the operator to run in a real terminal session |
| `CLAWSEAT_ROOT` missing | Environment not initialized | Export the repo root and rerun preflight |
| `dynamic profile not found` | Project profile missing | For `install` project, the profile auto-seeds; otherwise create `/tmp/{project}-profile-dynamic.toml` |
| `tmux server` absent | tmux not running | Start a tmux server, then rerun preflight |
| `memory.env is empty` | P0.3 credential seed didn't run before bootstrap | Run P0.3, or manually write `~/.agents/secrets/claude/minimax/memory.env` then re-run P0.5 |
| memory seat never shows `machine/ KB ready` | P1.3 didn't reach memory, or memory crashed | Check `~/.agents/tasks/${PROJECT}/MEMORY-SCAN-001/` and the memory iTerm scrollback |
| `install_koder_overlay` exit 3 | Target agent workspace does not exist | Verify the OpenClaw agent was created first, or consult memory again for the canonical list |
| Koder in OpenClaw still old identity after overlay | `refresh_workspaces.py` didn't copy templates | Re-run P0.6 then P3.1-3.3 |
| Feishu smoke sent but koder silent | Platform scope or requireMention wrong | Enable `im:message.group_msg:receive` + publish new app version; set project group `requireMention=false` |
| `group_not_found` from lark-cli / send_delegation_report | group ID invalid OR bot not in the group | Verify `oc_<alnum>` format; ensure the OpenClaw bot is a member of the target Feishu group |
| `auth_expired` or `auth_needs_refresh` from send_delegation_report | lark-cli OAuth token stale | Operator: `lark-cli auth login` in a terminal with browser access |
