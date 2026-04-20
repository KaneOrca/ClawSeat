# ClawSeat Ancestor Runbook (canonical SOP for bootstrap agent)

## Role & Scope

The ancestor Claude Code agent drives a full ClawSeat overlay install onto
an existing OpenClaw agent. It owns the install chain end-to-end until
the Feishu bridge smoke succeeds, then hands off to koder.

**In scope**: P0 preflight → P4 Feishu smoke → P5 handoff.

**Not in scope**: ongoing task execution, reviewer/qa chains, OpenClaw
source edits. Those belong to koder after handoff.

**Canonical backstop docs** (read before each phase):
- [`install-flow.md`](install-flow.md) — authoritative phase ordering
- [`feishu-bridge-setup.md`](feishu-bridge-setup.md) — Feishu 7-step detail
- [`memory-query-protocol.md`](memory-query-protocol.md) — memory query contract

## Prerequisites

Before running Phase 0:

1. `CLAWSEAT_ROOT` must be set:
   ```bash
   export CLAWSEAT_ROOT=/path/to/ClawSeat
   ```
   **Verify**: `ls "$CLAWSEAT_ROOT/core/scripts"` → exit 0

2. An OpenClaw install exists on this host (`~/.openclaw/agents/`,
   `openclaw.json`) with at least one agent workspace
   (`~/.openclaw/workspace-<name>/`) that you want to promote to koder.

3. A Claude-compatible API key (MiniMax recommended for cost) OR an
   Anthropic OAuth session. The ancestor's Phase 0.6 will auto-discover
   candidates.

**Halt condition**: if `CLAWSEAT_ROOT` is unset or no OpenClaw install is
present → `USER_DECISION_NEEDED: prerequisites missing`. Do not attempt
to create OpenClaw from scratch — that's outside ClawSeat's scope.

---

## Phase 0 — Preflight + Bootstrap + credential seed

Prepare all workspace scaffolding and seed memory's auth so Phase 1 can
start cleanly.

### Step 0.1 — Install bundled OpenClaw skills (G1)

```bash
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_bundled_skills.py"
```

Creates `~/.openclaw/skills/{clawseat,clawseat-install,gstack-harness,…}`
symlinks (10 skills). Idempotent.

**Halt condition**: exit 2 → external dependency missing (gstack / lark-cli).

### Step 0.2 — Install entry skills (G4)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"
```

Makes `/clawseat` and `/cs` invocable from any local Claude or Codex on
this host.

### Step 0.3 — Generate project profile (B2)

```bash
PROJECT=install
cp "$CLAWSEAT_ROOT/examples/starter/profiles/install-with-memory.toml" \
   "/tmp/${PROJECT}-profile-dynamic.toml"

python3 - <<PY
from pathlib import Path
import re
p = Path(f"/tmp/{'${PROJECT}'}-profile-dynamic.toml")
txt = p.read_text()
txt = txt.replace('project_name = "install"', 'project_name = "${PROJECT}"')
txt = re.sub(
    r'(tasks_root\s*=\s*["\']?)~/.agents/tasks/install',
    rf'\g<1>~/.agents/tasks/{"${PROJECT}"}',
    txt,
)
p.write_text(txt)
PY
```

**B2 caution**: `tasks_root = "~/.agents/tasks/install"` is quoted; a
naive `sed 's/install/<new>/'` misses the quote boundary. Use the Python
snippet above.

**Verify**: `grep "project_name" /tmp/${PROJECT}-profile-dynamic.toml`
shows the correct name.

### Step 0.4 — Bootstrap workspace (no `--start`)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --project-name "$PROJECT"
```

**Do NOT pass `--start` in overlay mode.** `--start` auto-launches the
profile's `heartbeat_owner` (koder) as a tmux seat, which is incorrect
when koder will be an OpenClaw agent (Phase 3). You'll get a zombie
`install-koder-claude` tmux session that has to be killed.

**Verify** (hard precondition for P1):

```bash
test -f "$HOME/.agents/sessions/${PROJECT}/memory/session.toml" && echo "bootstrap_ok"
```

### Step 0.5 — Refresh workspaces (G11)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml"
```

Syncs ClawSeat templates into each seat workspace.

### Step 0.6 — Discover credentials + seed memory.env

Ancestor runs a **narrow** scan to locate the Claude-compatible API key
needed for memory to authenticate:

```bash
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/scan_environment.py" \
  --only credentials --output /tmp/ancestor-precheck
cat /tmp/ancestor-precheck/machine/credentials.json | head -40
```

**This does NOT populate `~/.agents/memory/machine/`** — that KB is
memory's output, not ancestor's. P0.6 is just ancestor finding its own
bootstrap credential.

Present the candidates to the operator. **Recommend MiniMax API** (cheap
per-turn cost via `api.minimaxi.com/anthropic`). Accept: MiniMax API,
xcode-best API, or Anthropic OAuth.

Seed `.env.global` + memory's secret file:

```bash
mkdir -p ~/.agents
cat > ~/.agents/.env.global <<EOF
MINIMAX_API_KEY=<value discovered above>
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
EOF
chmod 600 ~/.agents/.env.global

# seed_empty_secret_from_peer will read .env.global on the next seat
# start. For robustness also write memory.env directly:
mkdir -p ~/.agents/secrets/claude/minimax
cat > ~/.agents/secrets/claude/minimax/memory.env <<EOF
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_AUTH_TOKEN=<value from credentials>
ANTHROPIC_MODEL=MiniMax-M2.7-highspeed
EOF
chmod 600 ~/.agents/secrets/claude/minimax/memory.env
```

**Halt condition**: no credentials discoverable and operator can't
supply → `USER_DECISION_NEEDED: no provider`. Do not fabricate.

---

## Phase 1 — Memory seat online + system scan

### Step 1.1 — Start memory seat

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --seat memory --confirm-start
```

**Verify**: `tmux has-session -t ${PROJECT}-memory-claude` → 0

### Step 1.2 — Attach iTerm + operator completes TUI onboarding (USER ACTION)

`start_seat` creates the tmux session but does not open a terminal
window. Ancestor opens one:

```bash
osascript <<'APPLESCRIPT'
tell application "iTerm"
  activate
  set w to (create window with default profile)
  tell current session of w
    set name to "install-memory-claude (memory seat)"
    write text "tmux attach -t install-memory-claude"
  end tell
end tell
APPLESCRIPT
```

Tell the operator:

> **Memory seat iTerm window is open. Please complete the first-launch
> onboarding**:
> 1. Theme picker (1-7) → press `1` + Enter
> 2. Security notes → press Enter
> 3. Trust this folder → press `1` + Enter
> 4. Login method → press `2` + Enter (Anthropic Console account · API
>    usage billing)
>
> After step 4, the TUI should land on `❯` with
> `MiniMax-M2.7-highspeed · API Usage Billing` in the banner. Come back
> and confirm.

**Halt condition**: TUI shows `Claude account with subscription` (OAuth
mode) → credentials didn't load. Go back to P0.6.

### Step 1.3 — Dispatch the system-scan LEARNING REQUEST (G2)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/notify_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --source ancestor --target memory \
  --task-id MEMORY-SCAN-001 --kind learning \
  --message "LEARNING REQUEST: Run scan_environment.py --output ~/.agents/memory. Focus on openclaw (OpenClaw agent list, workspace directories, feishu group bindings). Confirm 5 machine/*.json files are written."
```

> **Why notify_seat, not dispatch_task**: the T22 guard
> (`assert_target_not_memory`) blocks `dispatch_task.py --target memory`
> with exit 2 because memory does not read `TODO.md`. See
> [`test_memory_target_guard.py`](../../../../tests/test_memory_target_guard.py)
> and [`TOOLS/memory.md`](../../../templates/shared/TOOLS/memory.md).

### Step 1.4 — Wait for operator to report scan complete (USER SYNC POINT)

Memory's TUI will run `scan_environment.py`, write 5 files under
`~/.agents/memory/machine/`, deliver a receipt via `complete_handoff.py`,
and `/clear` its context.

Tell the operator:

> **Please watch the memory seat iTerm window. It's running a system
> scan. When memory reports the scan is complete (you'll see
> `complete_handoff` success or a cleared context with 5 files confirmed),
> come back and tell me "memory scanned".**

Ancestor **blocks here**. Do not poll memory directly — the sync is
operator-visual + operator-verbal.

**Halt condition**: operator does not report within ~5 minutes →
`USER_DECISION_NEEDED: memory scan did not complete`. Check memory iTerm
scrollback for errors.

### Step 1.5 — Verify KB landed (G2, G15)

```bash
for f in credentials network openclaw github current_context; do
  test -f ~/.agents/memory/machine/${f}.json && echo "machine/${f}.json ok"
done
ls ~/.agents/tasks/${PROJECT}/MEMORY-SCAN-001/ 2>/dev/null \
  | grep -E 'ack|receipt|done' || echo "WARN: no ACK receipt yet"
```

**Halt condition**: any `machine/*.json` missing → re-send the LEARNING
REQUEST or consult memory's iTerm.

---

## Phase 2 — Query memory, operator picks target agent (G3, G15)

### Step 2.1 — Ask memory for the OpenClaw agent list

```bash
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
  --memory-dir ~/.agents/memory --search agents
```

Or reasoning query:

```bash
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
  --memory-dir ~/.agents/memory \
  --ask "Which OpenClaw agents exist on this host? List with workspace paths and any existing ClawSeat overlay markers."
```

**G15 caution**: use `--memory-dir <abs-path> --key <key>` or
`--search <term>`. Do NOT use `--file --section` (mutually exclusive).

### Step 2.2 — Present candidates, operator chooses (USER ACTION)

Tell the operator the full candidate list. **Do not auto-pick** even if
only one candidate exists — agent selection is a user decision.

Wait for operator response.

**Halt condition**: memory returns no agents → OpenClaw setup is
incomplete. Block and escalate.

---

## Phase 3 — Koder overlay + external confirmations (G3)

### Step 3.1 — Install koder overlay

```bash
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_koder_overlay.py" \
  --agent <CHOSEN_AGENT>
```

**Verify**:

```bash
ls ~/.openclaw/workspace-<CHOSEN_AGENT>/skills/ | wc -l   # expect ≥ 6
```

**Halt condition**: exit 3 → agent workspace not found; exit 2 →
`--agent` missing. Both need operator decision.

### Step 3.2 — Finalize koder scaffold (B1)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/init_koder.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --on-conflict backup
```

Generates `TOOLS/` and `WORKSPACE_CONTRACT.toml` in the agent's
workspace. Existing non-ClawSeat files moved to `.backup-<ts>/`.

### Step 3.3 — Verify koder identity via /new (USER ACTION)

Tell the operator:

> **Please open OpenClaw. Send `/new` to the `<CHOSEN_AGENT>` agent.**
> It should respond as **koder** (ClawSeat frontstage skill loaded).
> Come back and tell me "koder identity confirmed" or report what it
> says instead.

**Halt condition**: `<CHOSEN_AGENT>` still behaves as the pre-overlay
agent → re-run `refresh_workspaces.py` and P3.1-3.2; escalate if still
wrong.

### Step 3.4 — Create Feishu group for koder (USER ACTION)

Tell the operator:

> **Please create a Feishu group named e.g. "koder-${PROJECT}" and add
> the OpenClaw bot to it. Give me the group ID in `oc_<alnum>` form.**

Wait for the group ID.

**Halt condition**: operator can't create group (bot missing or event
scope not published) → escalate to
[`feishu-bridge-setup.md`](feishu-bridge-setup.md) platform setup.

---

## Phase 4 — Planner + Feishu bridge smoke (G6, G7, G8, G14)

### Step 4.1 — Start planner seat

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --seat planner --confirm-start
```

Open iTerm attached (same pattern as P1.2). Operator completes planner's
onboarding (same 4-key sequence).

**AGENT_HOME note (G12)**: lark-cli reads from real user HOME. The
`start_seat.py` harness injects `AGENT_HOME` automatically; no manual
export needed.

### Step 4.2 — Verify lark-cli auth + bind project to group (G7, G8)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py" \
  --check-auth
```

Expected: `"status": "ok"`.

**Halt condition**: `auth_needs_refresh` → operator runs `lark-cli auth login`
in a terminal with browser access.

Bind:

```bash
python3 - <<PY
import sys; sys.path.insert(0, "$CLAWSEAT_ROOT")
from core.skills.clawseat_install.scripts.bind_project import bind_project_to_group
bind_project_to_group(
    project="$PROJECT",
    group_id="<GROUP_ID from P3.4>",
    bound_by="operator",
    authorized=True,
)
PY
```

Writes `~/.agents/projects/$PROJECT/BRIDGE.toml`.

### Step 4.3 — Dispatch Feishu smoke to planner (not ancestor direct)

Ancestor delegates the smoke send to planner. This exercises the real
chain ancestor → planner → Feishu → koder:

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/dispatch_task.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --source ancestor --target planner \
  --task-id BRIDGE-SMOKE-001 \
  --title "Feishu bridge smoke" \
  --objective "Send OC_DELEGATION_REPORT_V1 to the project group to prove the bridge works. Use --chat-id <GROUP_ID>." \
  --intent ship --reply-to ancestor
```

Planner picks this up from its `TODO.md` and runs
`send_delegation_report.py --chat-id <GROUP_ID> ...`.

### Step 4.4 — Operator confirms koder received smoke (USER ACTION)

Tell the operator:

> **Please check the Feishu group.** You should see an
> `OC_DELEGATION_REPORT_V1` envelope arrive, and koder (`<CHOSEN_AGENT>`
> in OpenClaw) should react to it. Come back and confirm "koder saw the
> smoke" or report what happened.

**Halt condition**: smoke sent but koder silent → check
`im:message.group_msg:receive` event scope is enabled on Feishu Open
Platform AND project group's `requireMention=false`. See
[`feishu-bridge-setup.md`](feishu-bridge-setup.md) §5.2-5.5.

---

## Phase 5 — Handoff

Once the operator confirms P4.4, install is complete.

### Step 5.1 — Notify operator of handoff

Tell the operator:

> **Install complete.** From now on you talk to koder directly (via
> OpenClaw or Feishu group). Koder will drive normal task execution.
>
> I (the ancestor) go standby. Re-engage me only to:
> - debug install failures
> - overlay ClawSeat onto another OpenClaw agent (rerun P3 with a new
>   `--agent`)
> - regenerate scaffolding after an upstream template change
>
> `planner`, `builder-*`, `reviewer-*`, `qa-*`, `designer-*` seats are
> brought up **lazily by koder** when a task chain needs them — not by
> me.

### Step 5.2 — Ancestor enters standby

No further ancestor action. The ancestor process stays running so the
operator can re-engage, but takes no autonomous action.

---

## Phase 6 — TUI Decode Table (appendix)

When observing Claude Code TUI in tmux, decode the status bar correctly:

| Status bar text | Meaning | Action |
|---|---|---|
| `⏵⏵ bypass on` | Bypass IS ON (permission granted) | Safe to send-keys commands |
| `(shift+tab to cycle)` | UI navigation hint, not a state | No action required — continue |
| `Select login method 1/2/3` | OAuth is blocked waiting for selection | USER_DECISION_NEEDED: relay to operator, do NOT send-keys |
| `Do you trust this folder? 1/2` | First-launch trust prompt | Ancestor CAN send `1` safely — deterministic |
| `Cooked for Xs` / `Thinking...` | Model is thinking | DO NOT send-keys; wait for prompt to return |

**Feishu / lark-cli specific**:

| Status or log text | Meaning | Action |
|---|---|---|
| `---WAIT---` in lark-cli output | Device flow polling — waiting for user browser approval | Not a block; wait for approval or prompt operator. Do NOT kill the process. |
| `auth_needs_refresh` in send result | User OAuth token expired | USER_DECISION_NEEDED: operator runs `lark-cli auth login` in terminal, then retry |

**Sandbox HOME errors**:

| Error pattern | Meaning | Action |
|---|---|---|
| Path contains `/.agents/runtime/identities/` in error message | Script resolved paths against sandbox HOME instead of real user HOME | Script should auto-detect via `_resolve_effective_home()`. If not, set `CLAWSEAT_REAL_HOME=/Users/<operator>` or check that `AGENT_HOME` is exported in the seat environment. |
| `~/.agents/runtime/identities/.../home/.openclaw` not found | Sandbox `.openclaw` checked — no real resources there | Ensure `agent_admin_config.HOME` resolves via `_resolve_effective_home()`, not raw `Path.home()`. |

**Rule**: Never send-keys when the TUI is waiting for user OAuth input
or when the model is actively thinking.

---

## Phase 7 — Alarm Discipline (appendix)

**Principle**: Before raising an alarm about a transient failure (pytest
FAIL, file not found, seat stale), run the verification trifecta —
`git log -5 --oneline` + `git status` + targeted `pytest`. Many alerts
are cache/lock/transient and resolve on retry. Only escalate if the
failure reproduces deterministically.

```bash
git -C "$CLAWSEAT_ROOT" log -5 --oneline
git -C "$CLAWSEAT_ROOT" status
python3 -m pytest tests/ -q --tb=short -x 2>&1 | tail -10
```

**Alarm transport**: Use `OC_DELEGATION_REPORT_V1` via `user_gate` →
koder (not tmux send-keys direct) so the alarm is auditable and routable.

---

## Checklist: G1-G15 + B1-B6

Each item maps to a Phase anchor and is checked by `install_complete.py`.

| ID | Description | Phase | install_complete check |
|----|-------------|-------|----------------------|
| G1 | install_bundled_skills.py run | Phase 0.1 | `~/.openclaw/skills/` symlinks present |
| G2 | Memory seat started + MEMORY-SCAN-001 notified + machine/ KB populated | Phase 1 | all 5 `~/.agents/memory/machine/*.json` present |
| G3 | Memory queried for target agent before overlay | Phase 2.1 | memory log contains agent query |
| G4 | install_entry_skills.py run | Phase 0.2 | `.entry_skills_installed` marker or skill paths |
| G5 | Canonical phase ordering followed (no `--start` in P0.4) | Phase 0 | advisory check only |
| G6 | Feishu bridge end-to-end smoke delivered via planner | Phase 4 | `BRIDGE.toml` present + koder receipt |
| G7 | Project-group binding confirmed with operator | Phase 3.4 | BRIDGE.toml bound_by field |
| G8 | bind_project_to_group() called → BRIDGE.toml | Phase 4.2 | `BRIDGE.toml` exists |
| G9 | Planner introduced AFTER koder overlay (not before) | Phase 4 | advisory |
| G10 | Per-seat operator confirmation (no auto-defaults) | Phase 1.2 / 4.1 | advisory |
| G11 | refresh_workspaces.py run | Phase 0.5 | `.last_refresh` or WORKSPACE_CONTRACT last_refresh |
| G12 | AGENT_HOME auto-injected in tmux seats | Phase 4.1 | install-flow.md AGENT_HOME section |
| G13 | lark-cli auth via canonical device flow | Phase 4.2 | advisory |
| G14 | Feishu platform scopes verified pre-install | Phase 3.4 | lark-cli permissions list |
| G15 | Memory query uses correct --memory-dir --key syntax | Phase 2.1 | code check in brief |
| B1 | init_koder --on-conflict=backup (non-interactive) | Phase 3.2 | default backup in init_koder.py |
| B2 | Profile tasks_root sed handles quoted strings | Phase 0.3 | Python re.sub pattern |
| B3 | Tool swap = delete + recreate (not rebind) | docs/AGENT_ADMIN.md | advisory |
| B4 | USER_DECISION_NEEDED halting points explicit | This runbook | each Phase halt condition |
| B5 | FRICTION_LOG appends to status file | operator preference | advisory |
| B6 | batch-start-engineer with --window-mode | Phase 4.1 | advisory |
