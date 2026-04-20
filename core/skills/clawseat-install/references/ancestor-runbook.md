# ClawSeat Ancestor Runbook (canonical SOP for bootstrap agent)

## Role & Scope

The ancestor Claude Code agent drives a full ClawSeat bootstrap for a new project group. It operates inside a tmux session, owns the install chain, and delegates ongoing work to planner once the bridge is live.

**Not in scope**: ongoing task execution, reviewer/qa chains, openclaw source edits.

**Canonical backstop docs** (read before each phase):
- `references/install-flow.md` — authoritative phase ordering
- `references/feishu-bridge-setup.md` — 7-step Feishu bridge canonical
- `references/memory-query-protocol.md` — memory query/escalation contract

---

## Prerequisites

Before running Phase 0:

1. `CLAWSEAT_ROOT` must be set:
   ```bash
   export CLAWSEAT_ROOT=/path/to/clawseat
   ```
   **Verify**: `ls "$CLAWSEAT_ROOT/core/scripts"` → exit 0

2. Memory query for all environment facts BEFORE hardcoding values:
   ```bash
   python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
     --memory-dir ~/.agents/memory --key credentials.keys.MINIMAX_API_KEY
   ```
   **Rule**: Never guess API keys, agent names, group IDs, or provider config. Always query memory first.

3. Confirm the OpenClaw agent target is known:
   ```bash
   python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
     --memory-dir ~/.agents/memory --search agents
   ```

**Halt condition**: If `CLAWSEAT_ROOT` is unset or memory is unreachable → write `USER_DECISION_NEEDED: missing prerequisites` to status file and halt.

---

## Phase 0 — Pre-flight Skill Install

### Step 0.1 — Install bundled skills (G1)

Creates agent-neutral shared skills in `~/.openclaw/skills/`. MUST run before any per-agent overlay.

```bash
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_bundled_skills.py"
```

**Verify**:
```bash
ls ~/.openclaw/skills/ | grep -E 'clawseat|gstack|memory'
echo "exit $?"
```
Expected: at least 4 skill symlinks (clawseat, clawseat-install, gstack-harness, memory-oracle). Exit 0.

**Halt condition**: exit 2 from `install_bundled_skills.py` → external dependency missing (gstack/lark-cli). Write `USER_DECISION_NEEDED: bundled skill install failed` and halt.

### Step 0.2 — Install entry skills (G4)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"
```

**Verify**: `ls ~/.openclaw/workspace-<agent>/` shows skill directories.

**Halt condition**: script exits non-zero → USER_DECISION_NEEDED.

### Step 0.3 — OpenClaw first install (G5)

For a fresh OpenClaw + Feishu install, prefer the one-shot installer:

```bash
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/openclaw_first_install.py"
```

*Trade-off*: The one-shot installer handles dependency ordering. Individual scripts (`install_koder_overlay` → `init_koder` → `bootstrap_harness`) are still valid for partial reinstall or repair, but require correct ordering. If the project already exists, skip to Phase 1.

---

## Phase 1 — Memory Seat Start + Scan (G2)

Memory seat is the authoritative oracle. Start it BEFORE any per-agent queries.

### Step 1.1 — Start memory seat

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/start_seat.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --seat memory \
  --confirm-start
```

**Verify**: `tmux has-session -t install-memory-claude 2>/dev/null && echo OK`

**Halt condition**: memory seat not running after start → USER_DECISION_NEEDED: memory seat failed to start.

### Step 1.2 — Dispatch MEMORY-SCAN-001

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/dispatch_task.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --source koder \
  --target memory \
  --task-id MEMORY-SCAN-001 \
  --title 'Initial environment scan' \
  --objective 'Scan openclaw.json, gstack config, credentials, and list all known agents' \
  --intent ship \
  --reply-to koder
```

### Step 1.3 — Wait for memory index

```bash
# Poll up to 60 seconds
for i in $(seq 1 12); do
  test -f ~/.agents/memory/index.json && echo "MEMORY_READY" && break
  sleep 5
done
```

**Verify**: `~/.agents/memory/index.json` exists. Exit 0.

**Halt condition**: index.json missing after 60s → USER_DECISION_NEEDED: memory scan did not complete.

---

## Phase 2 — Target Agent Query & Overlay (G3, G15)

### Step 2.1 — Query memory for agent (G3, G15)

Use the canonical query syntax with `--memory-dir` (NOT `--file`):

```bash
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
  --memory-dir ~/.agents/memory \
  --search agents
```

Or ask for specific agent:

```bash
python3 "$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/query_memory.py" \
  --memory-dir ~/.agents/memory \
  --ask "which OpenClaw agent should receive the koder overlay for project ${PROJECT}?"
```

**G15 caution**: Do NOT use `--file openclaw --section feishu` — those flags are mutually exclusive. Always use `--memory-dir <absolute-path> --key <key>` or `--search <term>`.

**Verify**: query returns a non-empty agent name. If "not found" → escalate to memory per protocol.

**Halt condition**: memory returns no result → USER_DECISION_NEEDED: cannot determine target agent.

### Step 2.2 — Install koder overlay

```bash
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_koder_overlay.py" \
  --agent <AGENT_NAME>
```

**Verify**:
```bash
ls ~/.openclaw/workspace-<AGENT_NAME>/skills/ | wc -l
```
Expected: ≥6 skill symlinks.

**Halt condition**: exit 3 → agent workspace does not exist; exit 2 → `--agent` missing. USER_DECISION_NEEDED in both cases.

### Step 2.3 — Run init_koder (B1)

Use `--on-conflict=backup` to avoid interactive prompt in automated context:

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/init_koder.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --on-conflict backup
```

**Verify**: `ls ~/.openclaw/workspace-<AGENT_NAME>/TOOLS/` → should include `koder-hygiene.md`

---

## Phase 3 — Profile + Bootstrap (B2)

### Step 3.1 — Generate profile

```bash
cp "$CLAWSEAT_ROOT/examples/starter/profiles/install-with-memory.toml" \
   "/tmp/${PROJECT}-profile-dynamic.toml"
```

**Profile substitution (B2 — handle quoted strings)**:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path(f"/tmp/{project}-profile-dynamic.toml")
txt = p.read_text()
# Replace project_name
txt = txt.replace('project_name = "install"', f'project_name = "{project}"')
# Replace tasks_root — handle both quoted and unquoted
import re
txt = re.sub(
    r'(tasks_root\s*=\s*["\']?)~/.agents/tasks/install',
    rf'\g<1>~/.agents/tasks/{project}',
    txt
)
# Replace workspace_root
txt = re.sub(
    r'(workspace_root\s*=\s*["\']?)~/coding/install',
    rf'\g<1>~/coding/{project}',
    txt
)
p.write_text(txt)
print("profile written")
PY
```

**B2 caution**: `tasks_root = "~/.agents/tasks/install"` — the value is quoted. A simple `sed 's/install/hardening-b/'` will miss the quotes boundary. Use the Python snippet above.

**Verify**: `grep "project_name" /tmp/${PROJECT}-profile-dynamic.toml` → shows correct project name.

### Step 3.2 — Bootstrap harness

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --project-name "$PROJECT" \
  --start
```

**Verify**:
```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/render_console.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml"
```

### Step 3.3 — Refresh workspaces (G11)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/refresh_workspaces.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml"
```

**Verify**: `.last_refresh` marker created in project workspace, or `last_refresh` field present in `WORKSPACE_CONTRACT.toml`.

**Halt condition**: script exits non-zero → USER_DECISION_NEEDED.

---

## Phase 4 — Configuration Phase (G9, G10)

This phase is SEPARATE from task execution. Do not collapse config entry and validation.

### Step 4.1 — Per-seat user confirmation (G10)

For each backend seat declared in the profile, ask the user:

```
USER ACTION REQUIRED: Confirm seat configuration for <SEAT_ID>
  - tool: [claude / codex]
  - auth_mode: [oauth / api]
  - provider: [anthropic / minimax / bedrock]
  - API key or OAuth flow required?
```

**Never auto-proceed with defaults without explicit user confirmation.**

### Step 4.2 — Apply seat configuration

For each confirmed seat:

```bash
python3 "$CLAWSEAT_ROOT/core/scripts/agentctl.py" session start-engineer <SEAT_ID> \
  --project "$PROJECT"
```

### Step 4.3 — Configuration verification (G9)

After all seats configured, verify connectivity (not just startup) before entering task execution.

**Halt condition**: any seat fails OAuth or API auth → USER_DECISION_NEEDED: seat auth blocked.

---

## Phase 5 — Feishu Bridge Setup (G6, G7, G8, G14)

Follow the 7-step canonical process from `references/feishu-bridge-setup.md`.

### Step 5.1 — Verify lark-cli auth (G6 step 1)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py" \
  --check-auth
```

**Verify**: `"status": "ok"` in output.

**AGENT_HOME note (G12)**: lark-cli auth lives under the real user HOME, not sandbox HOME. In tmux seats, ensure `AGENT_HOME` is exported:

```bash
export AGENT_HOME=/Users/<real-user>
```

Without `AGENT_HOME`, lark-cli reads the wrong HOME in tmux seats. Set it before any lark-cli call.

**Halt condition**: auth not ok → USER_DECISION_NEEDED: user must run `lark-cli auth login` in a terminal with browser access.

### Step 5.2 — Verify Feishu platform scopes PRE-INSTALL (G14)

**Do this before smoke test**, not after:

```bash
# Check via lark-cli or Feishu Open Platform UI:
# Required event scopes (Event Subscriptions):
#   im:message
#   im:message.group_msg:receive   ← CRITICAL for no-@mention dispatch
#   im:chat:access
# Required permissions (Permissions & Scopes):
#   im:chat
#   im:chat.members
# App version: 2026.4.9+ must be published
```

**Halt condition**: scopes not enabled → USER_DECISION_NEEDED: enable Feishu scopes and publish new app version before proceeding.

### Step 5.3 — Collect group ID (G6 step 2, G7)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/find_feishu_group_ids.py"
```

**Confirm with user (G7)**:
- Is this group for the current project?
- Or switch to existing project?
- Or create a new project?

One project = one group. USER ACTION REQUIRED before binding.

### Step 5.4 — Bind project to group (G6 step 4, G8)

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, "$CLAWSEAT_ROOT")
from core.skills.clawseat-install.scripts.bind_project import bind_project_to_group
bind_project_to_group(
    project="<PROJECT>",
    group_id="<oc_xxx>",
    account_id="<koder_app_id>",
    session_key="<session_key>",
    bound_by="<user>",
    authorized=True,
)
PY
```

**Verify**: `~/.agents/projects/<PROJECT>/BRIDGE.toml` exists.

### Step 5.5 — Configure requireMention (G6 step 5)

- Main koder-facing group: `requireMention: true` (default)
- Project koder account: `requireMention: false`

See `references/feishu-group-no-mention.md`.

### Step 5.6 — Smoke test (G6 step 6)

```bash
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/send_delegation_report.py" \
  --project "$PROJECT" \
  --lane planning \
  --task-id BRIDGE-SMOKE-001 \
  --report-status done \
  --decision-hint proceed \
  --user-gate none \
  --next-action consume_closeout \
  --summary 'Feishu bridge smoke test' \
  --chat-id <GROUP_ID>
```

### Step 5.7 — Verify koder receives and parses (G6 step 7)

Koder should receive `OC_DELEGATION_REPORT_V1` in the Feishu group and confirm:
- `project=<PROJECT>` matches
- `task_id=BRIDGE-SMOKE-001`
- `report_status=done` + `next_action=consume_closeout` → auto-advance

**Halt condition**: smoke test delivery fails → check G12 (AGENT_HOME), G14 (scopes), lark-cli auth; escalate per error reference in `feishu-bridge-setup.md`.

---

## Phase 6 — TUI Decode Table

When observing Claude Code TUI in tmux, decode status bar correctly:

| Status bar text | Meaning | Action |
|---|---|---|
| `⏵⏵ bypass on` | Bypass IS ON (permission granted) | Safe to send-keys commands |
| `(shift+tab to cycle)` | UI navigation hint, not a state | No action required — continue |
| `Select login method 1/2/3` | OAuth is blocked waiting for selection | USER_DECISION_NEEDED: relay to user, do NOT send-keys |
| `Do you trust this folder? 1/2` | First-launch trust prompt | Ancestor CAN send `1` safely — this is a deterministic response |
| `Cooked for Xs` / `Thinking...` | Model is thinking | DO NOT send-keys; wait for prompt to return |

**Feishu / lark-cli specific**:

| Status or log text | Meaning | Action |
|---|---|---|
| `---WAIT---` in lark-cli output | Device flow polling — lark-cli is waiting for user to approve in browser | Not a block; wait for approval or prompt user. Do NOT kill the process. |
| `auth_needs_refresh` in send result | User OAuth token expired — must be renewed by a human with browser access | USER_DECISION_NEEDED: user runs `lark-cli auth login` in terminal, then retry |

**Sandbox HOME errors**:

| Error pattern | Meaning | Action |
|---|---|---|
| Path contains `/.agents/runtime/identities/` in error message | Script is resolving paths against sandbox HOME instead of real user HOME | The script should auto-detect via `_resolve_effective_home()`. If not, set `CLAWSEAT_REAL_HOME=/Users/<operator>` or check that `AGENT_HOME` is exported in the seat environment. |
| `~/.agents/runtime/identities/.../home/.openclaw` not found | G6/G11/G14 check resolved sandbox `.openclaw` — no real resources there | Ensure `agent_admin_config.HOME` resolves via `_resolve_effective_home()`, not raw `Path.home()`. Run `python3 install_complete.py --project install` after verifying `AGENT_HOME` is set correctly. |

**Rule**: Never send-keys when the TUI is waiting for user OAuth input or when the model is actively thinking.

---

## Phase 7 — Alarm Discipline

**Principle**: Before raising an alarm about a transient failure (e.g. pytest FAIL, file not found, seat stale), run the verification trifecta — `git log -5 --oneline` + `git status` + targeted `pytest`. Many alerts are cache/lock/transient and resolve on retry. Only escalate if the failure reproduces deterministically. This discipline is enforced by the `verify_transient_pytest_alerts` memory (2026-04-20 incident: ancestor CC false-alarm retracted after verification revealed file was out-of-scope).

Before raising an alarm or sending a USER_DECISION_NEEDED escalation, run the verification trifecta:

```bash
# 1. Check recent git state
git -C "$CLAWSEAT_ROOT" log -5 --oneline

# 2. Check working tree
git -C "$CLAWSEAT_ROOT" status

# 3. Run pytest (targeted — not full suite for transient alerts)
python3 -m pytest tests/ -q --tb=short -x 2>&1 | tail -10
```

Only escalate if the failure reproduces after this check. Many pytest alerts are transient (timing, file lock, env var).

**Alarm transport**: Use `OC_DELEGATION_REPORT_V1` via `user_gate` → koder (not tmux send-keys direct) so the alarm is auditable and routable.

---

## Checklist: G1-G15 + B1-B6

Each item maps to a Phase anchor and is checked by `install_complete.py`.

| ID | Description | Phase | install_complete check |
|----|-------------|-------|----------------------|
| G1 | install_bundled_skills.py run | Phase 0.1 | `~/.openclaw/skills/` symlinks present |
| G2 | Memory seat started + MEMORY-SCAN-001 dispatched + index.json exists | Phase 1 | `~/.agents/memory/index.json` mtime |
| G3 | Memory queried for target agent before overlay | Phase 2.1 | memory log contains agent query |
| G4 | install_entry_skills.py run | Phase 0.2 | `.entry_skills_installed` marker or skill paths |
| G5 | openclaw_first_install.py used or equivalent ordering | Phase 0.3 | advisory check only |
| G6 | Feishu 7-step canonical completed | Phase 5 | `BRIDGE.toml` present + lark-cli auth ok |
| G7 | Project-group binding confirmed with user | Phase 5.3 | BRIDGE.toml bound_by field |
| G8 | bind_project_to_group() called → BRIDGE.toml | Phase 5.4 | `BRIDGE.toml` exists |
| G9 | Configuration phase separate from task execution | Phase 4 | advisory |
| G10 | Per-seat user confirmation (no auto-defaults) | Phase 4.1 | advisory |
| G11 | refresh_workspaces.py run | Phase 3.3 | `.last_refresh` or WORKSPACE_CONTRACT last_refresh |
| G12 | AGENT_HOME documented + set in tmux seats | Phase 5.1 | install-flow.md AGENT_HOME section |
| G13 | lark-cli auth via canonical device flow | Phase 5.1 | advisory |
| G14 | Feishu platform scopes verified pre-install | Phase 5.2 | lark-cli permissions list |
| G15 | Memory query uses correct --memory-dir --key syntax | Phase 2.1 | code check in brief |
| B1 | init_koder --on-conflict=backup (non-interactive) | Phase 2.3 | default backup in init_koder.py |
| B2 | Profile tasks_root sed handles quoted strings | Phase 3.1 | Python re.sub pattern |
| B3 | Tool swap = delete + recreate (not rebind) | docs/AGENT_ADMIN.md | advisory |
| B4 | USER_DECISION_NEEDED halting points explicit | This runbook | each Phase halt condition |
| B5 | FRICTION_LOG appends to status file | operator preference | advisory |
| B6 | batch-start-engineer with --window-mode | Phase 4.2 | advisory |
