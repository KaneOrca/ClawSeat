# ClawSeat v0.6 Install Playbook (Simplified)

> Target executor: Claude Code (agent, not human).
> This file is the install SSOT. The invoking agent reads this file end-to-end
> and drives the install. Once ancestor is prompt-ready, ancestor owns the runtime.

## Prerequisites

0. Clone the repo.
```bash
git clone <repo-url> "$HOME/ClawSeat"
cd "$HOME/ClawSeat"
export CLAWSEAT_ROOT="$PWD"
```
Verify:
```bash
test -d "$CLAWSEAT_ROOT" && test -f "$CLAWSEAT_ROOT/docs/INSTALL.md"
```
Failure:
```text
INSTALL_BROKEN: repository missing or docs/INSTALL.md not found
```

1. Auto-detect and install missing host dependencies.
```bash
# macOS
command -v tmux >/dev/null || brew install tmux
command -v iTerm2 >/dev/null || brew install --cask iterm2

# Debian/Ubuntu
command -v tmux >/dev/null || sudo apt-get update && sudo apt-get install -y tmux

# Python 3.11+
python3 - <<'PY'
import sys
assert sys.version_info >= (3, 11), f"Python {sys.version_info.major}.{sys.version_info.minor} < 3.11"
print(sys.version.split()[0])
PY
```
Verify: `tmux` resolves; on macOS `iTerm2` resolves; Python prints `3.11+`.
Failure:
```text
PREREQ_MISSING: <tmux|iterm2|python311>
```
Recovery:
```bash
# macOS
brew install git tmux
brew install --cask iterm2
# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y git python3.11 tmux
```

2. Confirm runtime binary exists (prompt user to install if missing — do not auto-install).
```bash
command -v claude || { echo "PREREQ_MISSING: claude binary not found — install from https://claude.ai/code"; exit 1; }
```
Failure:
```text
PREREQ_MISSING: claude binary not found
```
Recovery: Instruct operator to install Claude Code from https://claude.ai/code, then re-run.

3. Verify `scripts/launch-grid.sh` exists.
```bash
test -f "$CLAWSEAT_ROOT/scripts/launch-grid.sh"
```
Failure:
```text
INSTALL_STATE_ERROR: scripts/launch-grid.sh missing (build step not yet run)
```

---

## Step 1: Pull Up Six-Pane Grid

```bash
cd "$CLAWSEAT_ROOT"
export CLAWSEAT_ROOT="$PWD"
bash scripts/launch-grid.sh
```
What happens:
- Creates 6 tmux sessions (ancestor, planner, builder, reviewer, qa, designer) in a monitor grid.
- In the ancestor pane, `claude --dangerously-skip-permissions` auto-starts in bypass mode.
- Prompt is injected via the 3-Enter flush contract.

Verify:
```bash
tmux list-sessions 2>/dev/null | grep -c "clawseat"
# Expect: 6
```
Failure:
```text
GRID_LAUNCH_FAILED: fewer than 6 sessions found
```
Resume: re-run `bash scripts/launch-grid.sh`.

Tell operator:
```text
Grid is up. Attach with: tmux attach -t clawseat-monitor
Or open iTerm2 and connect to the clawseat-monitor session.
```

---

## Step 2: Operator Attaches to Ancestor

Operator (human or upstream agent) attaches to the ancestor pane and confirms readiness.
Ancestor auto-reads `$CLAWSEAT_ANCESTOR_BRIEF` (default `~/.agents/tasks/<project>/patrol/handoffs/ancestor-bootstrap.md`).

Ancestor runs Phase-A checklist (in order):

| Token | Action | Success Criterion |
|-------|--------|-------------------|
| B1-read-brief | Parse ancestor-bootstrap.md YAML | YAML parses without error |
| B2-verify-or-launch-memory | `tmux has-session -t machine-memory-claude` or launch via `agent-launcher.sh --headless` | memory seat alive (rc=0) |
| B3-verify-openclaw-binding | Check WORKSPACE_CONTRACT.toml project field | matches brief project |
| B4-launch-pending-seats | Fan-out `agent-launcher.sh --headless` for each seat in sessions[] | each session alive within 30s |
| B5-verify-feishu-group-binding | Read `~/.agents/tasks/<project>/PROJECT_BINDING.toml.feishu_group_id` | non-empty |
| B6-smoke-dispatch | Send `OC_DELEGATION_REPORT_V1` (smoke) to Feishu group | receipt confirmed |
| B7-write-status-ready | Write `~/.agents/tasks/<project>/STATUS.md` phase=ready | file written |

Verify: operator runs `cat ~/.agents/tasks/<project>/STATUS.md | grep phase=ready`.
Failure: see Failure Modes below.

---

## Step 3: Acceptance

Ancestor sends smoke report to Feishu (via koder) and writes `STATUS.md phase=ready`.

```bash
test "$(cat ~/.agents/tasks/$PROJECT/STATUS.md)" = "phase=ready"
```
Failure:
```text
ACCEPTANCE_FAILED: STATUS.md phase!=ready
```

On success, ClawSeat is operational:
- ancestor = frontstage (CLI)
- memory = machine singleton (off-grid)
- six-pane monitor grid = runtime workspace

---

## Failure Modes

| Code | Symptom | Recovery |
|------|---------|----------|
| `GRID_LAUNCH_FAILED` | fewer than 6 tmux sessions | Re-run `bash scripts/launch-grid.sh` |
| `PREREQ_MISSING` | tmux / iTerm2 / claude / Python311 missing | Install missing tool, re-run from Step 1 |
| `B2-memory-dead` | memory seat not alive after 30s | Ancestor retries once; if still dead, logs and continues Phase-A |
| `B3-binding-mismatch` | WORKSPACE_CONTRACT project mismatch | Halt Phase-A; Feishu alert to operator |
| `B5-feishu-binding-missing` | PROJECT_BINDING.toml.feishu_group_id empty | Halt Phase-A; error to operator |
| `B6-smoke-failed` | Feishu smoke dispatch fails 3x | Log failure; continue Phase-A |
| `B7-status-write-failed` | Cannot write STATUS.md | Hard fail; operator must diagnose disk |

---

## Resume

To resume after a partial failure:

```bash
# Full grid restart (wipes existing sessions — confirm no active work first)
bash "$CLAWSEAT_ROOT/scripts/launch-grid.sh"

# Or resume from Phase-A (if ancestor session is still alive)
tmux attach -t <project>-ancestor-claude
# ancestor will re-read brief and continue from B1
```

Hard rule: do not invent steps outside this file. If the playbook does not cover
a required action, stop and surface the gap instead of improvising.
