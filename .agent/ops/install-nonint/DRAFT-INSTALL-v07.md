# ClawSeat v0.7 Install Playbook

> Target executor: Claude Code (agent, not human).
> This file is the install SSOT for the invoking agent.
> `scripts/install.sh` owns host setup and runtime bootstrap; once ancestor is prompt-ready, ancestor owns Phase-A.

## Prerequisites

0. Clone the repo and set the default project name.
```bash
git clone <repo-url> "$HOME/ClawSeat"
cd "$HOME/ClawSeat"
export CLAWSEAT_ROOT="$PWD"
export PROJECT_NAME=install
```
Verify:
```bash
test -d "$CLAWSEAT_ROOT/.git" && test -f "$CLAWSEAT_ROOT/scripts/install.sh"
```
Failure:
```text
INSTALL_BROKEN: repository missing or scripts/install.sh not found
```

---

## Step 1: Run `install.sh` (automatic bootstrap)

```bash
cd "$CLAWSEAT_ROOT"
bash scripts/install.sh
```

Optional preflight:
```bash
cd "$CLAWSEAT_ROOT"
bash scripts/install.sh --dry-run
```

What `install.sh` must do:
- Detect host OS and install/check `tmux`, `iTerm2` on macOS, Python 3.11+, and the `claude` binary.
- Run `python3 core/skills/memory-oracle/scripts/scan_environment.py --output ~/.agents/memory/`.
- Confirm these files exist under `~/.agents/memory/machine/`:
  `credentials.json`, `network.json`, `openclaw.json`, `github.json`, `current_context.json`.
- Choose the ancestor provider from `credentials.json` by heuristic:
  Minimax first, then DashScope, then Anthropic; otherwise prompt the operator for a key.
- Write the chosen provider env to `~/.agents/tasks/install/ancestor-provider.env`.
- Render `core/templates/ancestor-brief.template.md` into
  `~/.agents/tasks/install/patrol/handoffs/ancestor-bootstrap.md`.
- Create tmux sessions `install-ancestor`, `install-planner`, `install-builder`,
  `install-reviewer`, `install-qa`, `install-designer`.
- Launch the six-pane monitor window through `core/scripts/iterm_panes_driver.py`.
- Launch a separate `machine-memory-claude` tmux session in its own iTerm window with the same provider env.
- Focus the ancestor pane, send the 3-Enter bypass flush, and print the prompt stub for the operator.

Verify:
```bash
test -f ~/.agents/tasks/install/ancestor-provider.env
test -f ~/.agents/tasks/install/patrol/handoffs/ancestor-bootstrap.md
test -f ~/.agents/memory/machine/credentials.json
test -f ~/.agents/memory/machine/network.json
test -f ~/.agents/memory/machine/openclaw.json
test -f ~/.agents/memory/machine/github.json
test -f ~/.agents/memory/machine/current_context.json
tmux has-session -t install-ancestor
tmux has-session -t install-planner
tmux has-session -t install-builder
tmux has-session -t install-reviewer
tmux has-session -t install-qa
tmux has-session -t install-designer
tmux has-session -t machine-memory-claude
```
Failure:
```text
PREREQ_MISSING: <tmux|iterm2|python311|claude>
ENV_SCAN_FAILED: expected ~/.agents/memory/machine/*.json missing
PROVIDER_NO_KEY: no usable provider key and operator did not supply one
GRID_LAUNCH_FAILED: install-* tmux sessions missing after bootstrap
ITERM_DRIVER_FAIL: iTerm pane driver failed to open grid or memory window
```

Tell the operator:
```text
ClawSeat install: ancestor is prompt-ready.
Paste the prompt shown by install.sh into the ancestor pane.
Six-pane window: clawseat-install
Memory window: machine-memory-claude
```

---

## Step 2: Operator pastes the prompt; ancestor takes over

Paste exactly what `install.sh` prints:
```text
读 $CLAWSEAT_ANCESTOR_BRIEF，开始 Phase-A。每步向我确认或报告。
```

Ancestor then runs Phase-A in order:

| Token | Action | Success Criterion |
|-------|--------|-------------------|
| B0-env-scan-analysis | Read `credentials.json`, `network.json`, `openclaw.json`; summarize available harnesses and recommend the cheapest viable provider mix | `ancestor-provider-decision.md` written after user confirmation |
| B1-read-brief | Parse the rendered ancestor brief | Brief understood with no missing variables |
| B2-verify-memory | `tmux has-session -t machine-memory-claude` or relaunch once | memory seat alive |
| B3-verify-openclaw-binding | Read `~/.openclaw/workspace.toml` if present | project field matches or step is skipped with warning |
| B3.5-launch-engineers | Ask provider choice for planner, builder, reviewer, qa, designer one by one; write profile and launch each seat | each `install-<seat>` session is alive and visibly attached within 15s |
| B5-verify-feishu-binding | Read `~/.agents/tasks/install/PROJECT_BINDING.toml` | `feishu_group_id` present or user explicitly skips |
| B6-smoke-dispatch | Send `OC_DELEGATION_REPORT_V1` to Feishu, or run CLI-only smoke if Feishu is skipped | smoke result recorded |
| B7-write-status-ready | Write `~/.agents/tasks/install/STATUS.md` | `phase=ready` and provider summary recorded |

Verify:
```bash
test -f ~/.agents/tasks/install/ancestor-provider-decision.md
tmux has-session -t machine-memory-claude
tmux has-session -t install-planner
tmux has-session -t install-builder
tmux has-session -t install-reviewer
tmux has-session -t install-qa
tmux has-session -t install-designer
```
Failure:
```text
B2-memory-dead: memory seat still not alive after one retry
B3-binding-mismatch: OpenClaw binding points at the wrong project
B3.5_TIMEOUT: target engineer seat not alive or not visible within 15s
B5-feishu-binding-missing: PROJECT_BINDING.toml missing feishu_group_id and user did not provide one
B6-smoke-failed: Feishu or CLI smoke failed
```

Rules for ancestor:
- Do not rewrite the machine scan artifacts or the tmux/iTerm layout that Step 1 already created.
- B3.5 is strictly serial. Do not fan out seat launches.
- Stop on any blocking B-step, print `PHASE_A_FAILED: <step>`, and write `phase=blocked` to `STATUS.md`.

---

## Step 3: Acceptance

```bash
grep -q '^phase=ready$' ~/.agents/tasks/install/STATUS.md
grep -q '^providers=' ~/.agents/tasks/install/STATUS.md
tmux has-session -t install-ancestor
tmux has-session -t machine-memory-claude
```
Failure:
```text
ACCEPTANCE_FAILED: STATUS.md phase!=ready or required sessions are gone
```

On success, ClawSeat is operational:
- ancestor = frontstage CLI owner for the install project
- memory = dedicated machine context window on the same provider
- six-pane monitor grid = live workspace for planner, builder, reviewer, qa, designer

---

## Failure Modes

| Code | Symptom | Recovery |
|------|---------|----------|
| `INSTALL_BROKEN` | repo missing or `scripts/install.sh` absent | reclone or restore the install entrypoint |
| `PREREQ_MISSING` | tmux / iTerm2 / Python 3.11 / `claude` missing | install the missing dependency, then rerun Step 1 |
| `ENV_SCAN_FAILED` | one or more machine JSON files missing after scan | rerun Step 1; if repeatable, debug `scan_environment.py` |
| `PROVIDER_NO_KEY` | no supported provider key found and operator refused to supply one | collect a valid key, update `credentials.json`, rerun Step 1 |
| `GRID_LAUNCH_FAILED` | one or more `install-*` tmux sessions missing | rerun Step 1; inspect tmux stderr if the failure repeats |
| `ITERM_DRIVER_FAIL` | iTerm panes driver could not open the grid or memory window | verify iTerm2 + Python SDK, then rerun Step 1 |
| `B2-memory-dead` | `machine-memory-claude` is still dead after one retry | ancestor halts and reports the seat-launch failure |
| `B3-binding-mismatch` | OpenClaw binding points at the wrong project | stop Phase-A and correct the binding before retry |
| `B3.5_TIMEOUT` | a seat did not come up within 15s or is not visible in the pane | retry that seat only; do not continue to the next seat |
| `B5-feishu-binding-missing` | Feishu group binding unavailable | prompt once; if skipped, document CLI-only mode |
| `B6-smoke-failed` | smoke dispatch or CLI smoke failed | record the failure and keep `phase=blocked` until rechecked |
| `B7-status-write-failed` | `STATUS.md` could not be written | hard fail; diagnose disk or permission issues |
| `ACCEPTANCE_FAILED` | final status or sessions do not match the ready state | inspect `STATUS.md`, ancestor log, and live tmux sessions |

---

## Resume

To rerun the bootstrap safely:
```bash
cd "$CLAWSEAT_ROOT"
bash scripts/install.sh
```

To resume from a blocked Phase-A step:
```bash
tmux attach -t install-ancestor
```
Then tell ancestor to continue from the blocked token after fixing the underlying issue.

Hard rule: do not invent steps outside this file. If a required action is not covered here, stop and surface the gap instead of improvising.
