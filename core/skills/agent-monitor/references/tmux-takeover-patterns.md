# tmux Takeover Patterns

Advanced methodology for diagnosing and recovering stuck ClawSeat seats.
This reference is for **koder** and **planner** — the seats with
`agent-monitor` loaded.

> For basic tmux commands and common pitfalls, see
> `gstack-harness/references/tmux-environment.md` (loaded by all seats).

---

## Interaction layers

A seat running Claude Code / Codex / Gemini inside tmux has multiple
interaction layers. Before sending anything, determine which layer is active.

### Layer 1: Agent chat input

**Signals:**
- `Type your message`, `>`, or similar prompt
- No active shell card or subprocess indicator

**Action:** Send text normally via `send-and-verify.sh`.

### Layer 2: Shell subprocess awaiting input

**Signals:**
- Active shell command card visible
- `Shell awaiting input` or `Do you want to continue? [Y/n]:`
- A subprocess PID is running inside the agent

**Action:**
- Do NOT send text as if it were a chat message
- The inner shell needs direct key input
- Check if a non-interactive flag exists first (see Recovery below)
- If confirmation is needed: send `y` then `Enter` carefully

### Layer 3: Focus mismatch (queued input)

**Signals:**
- `Queued` or `Queued:` appears after sending
- The prompt is still visible after a confirmation attempt
- Text was accepted by the outer TUI but not delivered to the inner shell

**Action:**
- Report as focus mismatch — do NOT claim success
- Avoid repeatedly pushing the same input
- Consider the recovery escalation path below

### Layer 4: Completed / idle

**Signals:**
- Shell command card has disappeared
- Pane is back at normal agent input
- `detect-prompt-state.sh` returns `agent_input`

**Action:** Summarize outcome and proceed to next step.

---

## Quick state detection

```bash
$CLAWSEAT_ROOT/core/shell-scripts/detect-prompt-state.sh <session>
```

Returns one of:
| State | Meaning |
|---|---|
| `agent_input` | Normal prompt, ready for text |
| `agent_running` | Agent is thinking/executing |
| `shell_confirmation` | Inner shell waiting for `[Y/n]` |
| `shell_waiting` | Inner shell waiting for arbitrary input |
| `focus_mismatch_or_queued` | Text queued, not delivered |
| `unknown` | None of the known patterns matched |

---

## Recovery escalation path

When a seat is stuck, escalate through these steps in order.
Stop at the first one that works.

### Step 1: Re-send with delay

```bash
DIR=$CLAWSEAT_ROOT/core/skills/agent-monitor/script
bash $DIR/send-and-verify.sh <session> "message"
```

If that fails, try the delayed variant:

```bash
bash $DIR/tmux-send-delayed.sh <session> "message"
```

### Step 2: Check what the subprocess expects

Before blindly pushing `y` or `Enter`, inspect the command:

```bash
tmux capture-pane -t <session> -p -S -50
```

Look for:
- What command is running?
- What prompt is it showing?
- Is there a `--help` that reveals non-interactive flags?

### Step 3: Find a non-interactive alternative

Common flags that skip interactive prompts:

| Flag | Common in |
|---|---|
| `--yes` / `-y` | npm, apt, pip |
| `--consent` | Claude Code |
| `batch / no-prompt flag` | various CLIs |
| `--force` / `-f` | git, rm |
| `--no-input` | composer, symfony |

If the stuck command has a non-interactive variant, cancel the current
run (`C-c`) and restart with the flag.

### Step 4: Direct key injection

Last resort when no non-interactive path exists:

```bash
# Send confirmation directly to the pane
env -u TMUX tmux send-keys -t <session> "y"
sleep 0.5
env -u TMUX tmux send-keys -t <session> Enter
sleep 2
# Verify
env -u TMUX tmux capture-pane -t <session> -p | tail -10
```

### Step 5: Escalate

If none of the above work:
- koder: notify the user with diagnostic output
- planner: send unblock notice to koder via `scripts/notify_seat.py`

---

## Safe behavior boundaries

**Do:**
- Inspect before acting
- Prefer the smallest effective intervention
- Always verify after sending (re-capture pane)
- Report observed state accurately

**Do NOT:**
- Kill sessions without user permission
- Send destructive commands without permission
- Claim an action succeeded unless pane output confirms it
- Confuse `queued` with `submitted`
- Repeatedly push the same failing input without trying alternatives

---

## Reporting format

When reporting a stuck seat to koder or the user:

```
target:  <session>
state:   <alive | waiting | running | queued | completed | dead>
layer:   <agent-input | shell-prompt | focus-mismatch>
action:  <what was attempted>
result:  <what actually happened>
next:    <recommended next step>
```
