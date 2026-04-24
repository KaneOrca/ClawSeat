# ClawSeat v0.7 Install Playbook

> Target executor: Claude Code (agent, not human).
> This file is the install SSOT. `scripts/install.sh` owns host bootstrap and
> runtime startup; once ancestor is prompt-ready, ancestor owns Phase-A.
> Post-install extensions (koder overlay, new projects) are covered in §4–§5.

## Overview

| Step | Executor | What happens |
|------|---------|--------------|
| 0 Agent kickoff | operator | paste the kickoff prompt (§0) into a fresh Claude Code / Codex / Gemini session |
| 1 Prerequisites | operator | `git clone` + `cd ~/ClawSeat` |
| 2 `install.sh` | script (auto) | host deps, env scan, provider pick, six-pane grid, memory window, bypass flush |
| 3 Phase-A | ancestor CLI | B0–B7 interactive bootstrap |
| 4 (optional) Koder overlay | ancestor or operator | `scripts/apply-koder-overlay.sh` — pick an OpenClaw agent to become the Feishu reverse-channel koder |
| 5 (optional) Additional projects | operator | `bash scripts/install.sh --project <name>` |

> **Why `install.sh` instead of `agent_admin` or `agent-launcher.sh` directly?**
> `install.sh` is the L1 user-facing entry for fresh-machine bootstrap
> (host deps + scan + provider pick + 6 sessions + memory window + brief render).
> For per-seat operations on an existing project, use `agent_admin session
> start-engineer`. For executing a single seat process with sandbox HOME,
> the system internally calls `agent-launcher.sh` (you do not). See
> [docs/ARCHITECTURE.md §3z](ARCHITECTURE.md#seat-lifecycle-entry-points-v07-pyramid)
> for the full layering.

## 0. Agent kickoff prompt

Paste the prompt below into a fresh Claude Code / Codex / Gemini session to
kick off a ClawSeat install. The prompt is intentionally minimal — it tells
the agent *where* to find the playbook and *which preferences to surface*,
not how to execute each step. Every step belongs to this document
(`docs/INSTALL.md`), not the prompt.

~~~text
ClawSeat install — Agent kickoff prompt

You are invoked to install ClawSeat on this machine.

1. Read <CLAWSEAT_ROOT>/docs/INSTALL.md (default: ~/ClawSeat/docs/INSTALL.md) and
   execute it end-to-end.

2. Install preferences (operator fills these in before running):
   - Project name:           <PROJECT_NAME>       (e.g. "install" for first-time setup)
   - Repo root for seat cwd: <REPO_ROOT>          (default: CLAWSEAT_ROOT)
   - Seat harness:           <HARNESS_PREF>       (e.g. "default", "all seats claude+api+minimax")
   - Feishu mode:            <FEISHU_MODE>        ("enabled" | "disabled via CLAWSEAT_FEISHU_ENABLED=0")
   - Koder overlay:          <KODER_OVERLAY>      ("skip" | "apply tenant=<name>")

3. Consent & capability disclosure. The install playbook reads sensitive local
   state: shell environment, credential files (~/.claude/*, ~/.codex/*, macOS
   keychain entries, lark-cli session), provider API keys, and writes host
   artifacts under ~/.agents and ~/.openclaw. You are explicitly authorized to
   use platform capabilities — Bash, file Read/Write, `request_access`,
   `WebFetch`, MCP servers — as the playbook requires. Before first invoking
   each *new category* of access (first shell command, first credential read,
   first network fetch, first MCP/app grant), tell the operator in one short
   line what you are about to access and why. If the operator declines, stop
   and ask for an alternative path — do not skip silently.

4. Stop and ask the operator whenever a step is unclear, a prompt looks
   unfamiliar, or a command fails. Do NOT silently work around undocumented
   edge cases — every friction point is a signal the playbook must improve.

5. After install.sh exits, DO NOT end your session. Hand off Phase-A manually:

   (a) RELAY THE BANNER. install.sh ends with a "ClawSeat install complete"
       banner. Copy it verbatim to the operator. install.sh's zero exit code is
       NOT the final completion signal — the banner is. Never skip this.

   (b) READ THE OPERATOR GUIDE the banner points to:
           cat ~/.agents/tasks/<PROJECT_NAME>/OPERATOR-START-HERE.md
       If the operator reads Chinese, relay its Chinese instructions directly.

   (c) CAPTURE the ancestor pane and classify its state:
           tmux capture-pane -t '<PROJECT_NAME>-ancestor' -p | tail -15

       Three possible states — classify before doing anything:

       State A — PHASE-A ALREADY RUNNING or KICKOFF IN-FLIGHT
       (Step 9.5 auto-send succeeded):

         A1. Phase-A has produced visible reply content:
               - "B0" / "已读取 brief" / env_scan output
             (Ancestor consumed the brief and started Phase-A steps.)

         A2. Claude Code is actively processing the just-delivered kickoff
             (matches `ancestor_pane_shows_active_response()` at
             install.sh:1150 — this is the runtime-detector's exact set):
               - "Thinking..." / "Shell awaiting input"
               - spinner glyphs:  ✶  ✻  ✢  ✳  ✽  ⏺
               - "Read N file" / "Read N files"
             (Kickoff delivered; response in progress. Don't double-send.)

         If ANY of A1 or A2 is visible, DO NOT paste again — pasting
         duplicates the kickoff and creates double-input. SKIP step (d),
         go to (e).

       State B — BLOCKED ON A CONFIRMATION SCREEN (pane NOT ready; auto-send
       was intentionally skipped by `ancestor_pane_waiting_on_operator` detector):
         Pane shows any of —
         - "WARNING: Claude Code running in Bypass Permissions mode"
             → operator presses Enter to select "2. Yes, I accept"
         - "Do you trust the files in this folder" / "Trust folder"
             → operator selects Yes
         - "Browser didn't open? Use the url below to sign in" / "Paste code here"
             → operator completes OAuth in browser
         - "OAuth error:" / "Login successful. Press Enter to continue"
             → operator presses Enter
         - "Accessing workspace:" / "Quick safety check:"
             → operator presses Enter / confirms per the Claude Code prompt
         After clearing, re-capture and re-classify.

       State C — IDLE INPUT PROMPT (`> ` or `❯ ` with no recent activity):
         Pane is ready but kickoff was not delivered (auto-send failure).
         Proceed to step (d) to paste manually.

   (d) PASTE MANUALLY (only if step (c) classified as State C):
       Operator must paste the Phase-A kickoff prompt (shown at the bottom of
       the banner) into the ancestor pane. Walk them through copy-paste — don't
       assume. After paste + Enter, re-capture the pane to confirm Phase-A has
       started (look for "B0" / "已读取 brief" in the output).

   (e) VERIFY Phase-A is observably running (works for all three states):
       tmux capture-pane -t '<PROJECT_NAME>-ancestor' -p | tail -10 should show
       ancestor actively processing B0 (env scan / overrides read / provider
       table). Only then proceed to optional steps (koder overlay, additional
       projects) or the final report.

6. On completion (Phase-A observably running), report to the operator:
   - install.sh exit status
   - tmux session count (expect 7 for full grid: ancestor + 6 seats + monitor)
   - ancestor seat cwd (should equal <REPO_ROOT>)
   - ancestor pane confirmed ready + Phase-A kickoff confirmed received
   - koder overlay outcome (if requested)
   - every friction point encountered, with exact command + stderr + the
     ambiguous doc line
~~~

### Why consent-first

ClawSeat reads credentials, API keys, and the shell environment to pick the
right provider and render the ancestor brief. It also writes persistent host
state under `~/.agents/` (project profiles, sandbox HOMEs, identity tokens),
touches `~/.openclaw/` (for koder overlay), and optionally installs a macOS
LaunchAgent for ancestor patrol. An operator installing ClawSeat should see
*what is scanned* and *what is persisted* before it happens. Consent-first is
the contract, not an afterthought — every new category of access is declared
up front, and silent access to credentials or the network is a playbook bug.

### Why manual Phase-A handoff (step 5)

`install.sh` intentionally does not auto-paste the Phase-A kickoff prompt.
Claude Code v2.1.118+ surfaces a Bypass Permissions confirmation screen, Trust
Folder prompt, or OAuth flow on first boot — `install.sh` detects these
(`ancestor_pane_waiting_on_operator`), skips auto-send, and expects the invoking
agent to walk the operator through the manual handoff. Treating `install.sh`'s
exit as "done" drops the ancestor on the floor at the Bypass screen and
Phase-A never starts — the #1 reported install failure mode. Step 5 is
non-negotiable.

### Why minimal

Every step-by-step detail baked into the prompt is a step the agent stops
reading in the playbook. A terse kickoff prompt forces the agent to treat
`docs/INSTALL.md` as the source of truth — which is also the only way surfaces
like "undocumented friction" and "stale doc line X" can be detected and fixed.
If the playbook is missing a step that seems essential, that is a doc issue,
not a prompt issue.

## Broadcast model (seat-by-seat)

Hook / CLI-first, Feishu is **write-only async notification**. ClawSeat does not subscribe to Feishu.

| Seat | Hook policy | Output channel |
|------|-------------|----------------|
| planner | Stop-hook every turn → `lark-cli msg send` | structured summary to Feishu group (≤500 chars; never raw transcript) |
| ancestor | skill-driven | ancestor decides when to broadcast via a memory-oracle or lark-cli skill |
| memory | Stop-hook (self `/clear` + auto-deliver) | no Feishu broadcast; writes via `memory_deliver.py` when `[DELIVER:seat=<X>]` marker present |
| builder / reviewer / qa / designer | none | CLI only, visible in their pane |

The `koder` overlay (§4) is the inbound channel: operator messages on Feishu → OpenClaw-side koder → `tmux send-keys` into a ClawSeat seat.

---

## 1. Prerequisites

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

## 2. Run `install.sh` (automatic bootstrap)

```bash
cd "$CLAWSEAT_ROOT"
bash scripts/install.sh
```

Dry-run preflight:

```bash
bash scripts/install.sh --dry-run
```

Non-interactive provider shortcuts:

```bash
bash scripts/install.sh --provider minimax
bash scripts/install.sh --provider minimax --api-key sk-cp-...
bash scripts/install.sh --provider anthropic_console --api-key sk-ant-...
bash scripts/install.sh --base-url https://api.example.invalid --api-key sk-test --model claude-sonnet
```

Additional flags:

```bash
# Install for a different project's repo (cartooner, etc.)
bash scripts/install.sh --project cartooner --repo-root /path/to/cartooner

# Disable Feishu notifications (no lark-cli required)
CLAWSEAT_FEISHU_ENABLED=0 bash scripts/install.sh --project myproj

# Forget remembered per-seat harness choices from a previous run
bash scripts/install.sh --reset-harness-memory
```

Security note: `--api-key` is visible in `ps` output and shell history. Prefer:

```bash
export ANTHROPIC_BASE_URL=https://api.example.invalid
export ANTHROPIC_API_KEY=sk-test
bash scripts/install.sh --provider custom_api
```

Use `--base-url + --api-key` only for CI / agent automation / no-env / no-tty cases.

What `install.sh` does in order:

1. Detect host OS and install / verify `tmux`, `iTerm2` (macOS), Python ≥3.11, `claude` binary.
2. Run `core/skills/memory-oracle/scripts/scan_environment.py --output ~/.agents/memory/`
   → produces `machine/{credentials,network,openclaw,github,current_context}.json`.
3. Pick ancestor provider from `credentials.json` by heuristic unless explicit
   `--base-url + --api-key` already short-circuited detection:
   Minimax → DashScope → Anthropic → prompt operator for `base_url + api_key`.
4. Write provider env to `~/.agents/tasks/install/ancestor-provider.env`.
5. Render `core/templates/ancestor-brief.template.md` into
   `~/.agents/tasks/install/patrol/handoffs/ancestor-bootstrap.md` (substitute `${PROJECT_NAME}`, `${CLAWSEAT_ROOT}`).
6. Launch only `install-ancestor` via `core/launchers/agent-launcher.sh`
   with sandbox HOME isolation.
7. Bootstrap the project roster via `agent_admin project bootstrap`:
   write project / engineer / session records for
   `ancestor, planner, builder, reviewer, qa, designer`, but do **not** start
   their tmux seats yet.
8. Launch the six-pane monitor window via `core/scripts/iterm_panes_driver.py`
   (iTerm2 native panes — **not** nested tmux): the ancestor pane attaches
   immediately; the other five panes run `scripts/wait-for-seat.sh` and will
   auto-attach after ancestor later spawns each seat in B3.5.
9. Launch `machine-memory-claude` through `core/launchers/agent-launcher.sh`,
   then open a second iTerm window for it.
10. Focus the ancestor pane and emit 3-Enter flush so the operator visually sees bypass activate.
11. Print the ancestor-prompt stub for the operator to copy and paste.

Verify:

```bash
test -f ~/.agents/tasks/install/ancestor-provider.env
test -f ~/.agents/tasks/install/patrol/handoffs/ancestor-bootstrap.md
for f in credentials network openclaw github current_context; do
  test -f ~/.agents/memory/machine/$f.json || echo "MISSING $f"
done
for s in install-ancestor machine-memory-claude; do
  tmux has-session -t "$s" || echo "MISSING $s"
done
for s in install-planner install-builder install-reviewer install-qa install-designer; do
  tmux has-session -t "$s" 2>/dev/null && echo "UNEXPECTED $s"
done
```

Failure codes:

```text
PREREQ_MISSING: <tmux|iterm2|python311|claude>
ENV_SCAN_FAILED: expected ~/.agents/memory/machine/*.json missing
PROVIDER_NO_KEY: no usable provider key and operator did not supply one
GRID_LAUNCH_FAILED: ancestor / memory session or lazy grid failed to appear
ITERM_DRIVER_FAIL: iTerm pane driver failed to open the grid or memory window
```

`install.sh` ends by printing:

```text
ClawSeat install: ancestor is prompt-ready.
Paste the prompt shown above into the ancestor pane.
Six-pane window: clawseat-install
Memory window: machine-memory-claude
```

---

## 3. Operator pastes prompt; ancestor runs Phase-A

Paste (exact text from `install.sh` output):

```text
读 $CLAWSEAT_ANCESTOR_BRIEF，开始 Phase-A。每步向我确认或报告。
```

Ancestor executes Phase-A in order:

| Token | Action | Success criterion |
|-------|--------|-------------------|
| B0-env-scan-analysis | Read `~/.agents/memory/machine/*.json`. Summarize which harnesses (claude-code / codex / gemini / minimax / dashscope) are usable and recommend the cheapest viable provider mix. Explain the rationale. | User confirms or supplies custom plan; ancestor writes `~/.agents/tasks/install/ancestor-provider-decision.md` |
| B1-read-brief | Parse the rendered ancestor brief. | Brief understood with no missing variables. |
| B2-verify-memory | `tmux has-session -t machine-memory-claude`; relaunch once if dead. | Memory seat alive. |
| B2.5-bootstrap-tenants | `python3 core/scripts/bootstrap_machine_tenants.py ~/.agents/memory/` — populates `~/.clawseat/machine.toml [openclaw_tenants.*]` from `machine/openclaw.json.agents`. | `list_openclaw_tenants()` returns non-empty (if OpenClaw installed). |
| B3-verify-openclaw-binding | Read `~/.openclaw/workspace.toml` if present. | Project field matches or step is skipped with warning. |
| B3.5-launch-engineers | **Interactive, one-by-one**. For each seat in `planner, builder, reviewer, qa, designer`: ask operator for provider (default: claude-code + MiniMax), optionally `session switch-harness`, then `session start-engineer`, wait ≤15s for `tmux has-session`, and confirm the waiting pane auto-attached before moving on. | Each `install-<seat>` is alive and attached. |
| B5-verify-feishu-binding | Read `~/.agents/tasks/install/PROJECT_BINDING.toml`. | `feishu_group_id` present *or* operator explicitly skips (CLI-only mode). |
| B6-smoke | If `feishu_group_id` set, ancestor triggers planner to do one broadcast turn → `lark-cli` broadcasts a structured summary to the group. If skipped, ancestor runs CLI-only smoke (writes a test file, verifies via grep). | Smoke result recorded in `STATUS.md`. |
| B7-write-status-ready | Write `~/.agents/tasks/install/STATUS.md`. | `phase=ready`, `providers=<ancestor + 5 seats + memory>`. |

If the provider menu appears in smoke / CI / sandbox runs, use `--provider 1` or `CLAWSEAT_INSTALL_PROVIDER=1` to select the first detected candidate without a tty. `--provider minimax|ark|anthropic_console|custom_api` still forces a specific mode when you already know the answer.

Rules for ancestor:

- Do not rewrite the machine scan artifacts or the tmux/iTerm layout that Step 2 created.
- B3.5 is strictly serial — no fan-out.
- On any blocking B-step: print `PHASE_A_FAILED: <token>`, write `phase=blocked` to `STATUS.md`, stop.
- operator ↔ ancestor is CLI direct; never route through Feishu.

Verify:

```bash
grep -q '^phase=ready$' ~/.agents/tasks/install/STATUS.md
grep -q '^providers=' ~/.agents/tasks/install/STATUS.md
for s in install-ancestor install-planner install-builder install-reviewer install-qa install-designer machine-memory-claude; do
  tmux has-session -t "$s" || echo "MISSING $s"
done
```

If `~/.agents/tasks/<project>/STATUS.md` already contains `phase=ready`, `scripts/install.sh` exits 0 instead of rebuilding. Pass `--reinstall` (alias `--force`) only when you intentionally want a rebuild.

Sandbox/headless installs:

- `scripts/install.sh` still writes project state under `real_user_home()`, not the caller's sandbox `HOME`.
- If the caller started install from a seat sandbox or another headless runtime, the Step 7/8 iTerm open is now best-effort: macOS / `iterm2` import / driver bootstrap failures emit `WARN:` and continue.
- `ITERM_LAYOUT_FAILED` remains a hard failure. If the driver already started returning a non-`ok` layout payload, that is treated as a real GUI problem, not a sandbox skip.
- Recovering or reopening the window after a sandbox install still goes through the canonical path: `agent_admin window open-grid <project> [--recover] [--open-memory]`.

Project tool isolation:

- `agent_admin project init-tools <project> --from real-home|empty [--source-project <project>] [--tools ...]` creates or refreshes `~/.agent-runtime/projects/<project>/...`.
- `agent_admin project switch-identity <project> --tool feishu|gemini|codex --identity ...` only updates `PROJECT_BINDING.toml` and reseeds existing seat sandboxes.
- `switch-identity` does not call native login CLIs and does not migrate credential payloads such as `~/.agent-runtime/projects/<project>/.gemini/oauth_creds.json` or `.codex/auth.json`.
- Recommended workflow:
  1. `agent_admin project init-tools <project> --from real-home` or `--source-project <other-project>`
  2. Manually place or verify the desired credential inside `~/.agent-runtime/projects/<project>/...`
  3. Run `agent_admin project switch-identity ...`

Failure:

```text
B2-memory-dead: memory seat still dead after one retry
B2.5-bootstrap-failed: machine.toml tenant population failed
B3-binding-mismatch: OpenClaw binding points at wrong project
B3.5_TIMEOUT: target seat did not come up in 15s
B5-feishu-binding-missing: no feishu_group_id and operator did not skip
B6-smoke-failed: smoke dispatch or CLI smoke failed
B7-status-write-failed: STATUS.md could not be written
```

---

## 4. (Optional) Apply koder overlay — Feishu reverse channel

Koder is an **OpenClaw-side agent** that subscribes to Feishu messages and forwards them via `tmux send-keys` into a ClawSeat seat. ClawSeat does not ship koder as a seat — it ships a **destructive overlay** that converts an existing OpenClaw agent into koder.

When you want remote access (phone → Feishu → koder → ClawSeat seat):

```bash
bash scripts/apply-koder-overlay.sh "$PROJECT_NAME"
```

Flow:

1. Script lists all registered OpenClaw tenants (from `~/.clawseat/machine.toml`).
2. Operator picks one by number.
3. Script prints a destructive-confirmation: the chosen agent's `IDENTITY.md`, `SOUL.md`, `TOOLS.md + TOOLS/*`, `MEMORY.md`, `AGENTS.md`, `WORKSPACE_CONTRACT.toml` will be **overwritten** with koder templates (backups auto-taken via `--on-conflict backup`).
4. On confirmation: runs `init_koder.py` → `agent_admin project koder-bind` → `configure_koder_feishu.py`.

Verify:

```bash
python3 -c "from core.lib.machine_config import load_machine; m=load_machine(); print(m.tenants.get('<chosen-agent>'))"
```

Failure:

```text
ERR_NO_OPENCLAW_AGENTS: ~/.clawseat/machine.toml has no tenants (run B2.5 first)
ERR_BAD_PICK: selection out of range
ERR_INIT_KODER_FAILED: init_koder.py non-zero
```

Reversing the overlay: restore from backups in `<workspace>/.backup-koder-overlay-<ts>/`.

---

## 5. (Optional) Launch additional projects

ClawSeat supports multiple concurrent projects (sessions prefixed `<project>-<seat>`).

### Create a new project

```bash
bash scripts/install.sh --project <new-name>
bash scripts/install.sh --project <new-name> --provider minimax
bash scripts/install.sh --project <new-name> --base-url https://api.example.invalid --api-key sk-test --model claude-sonnet
```

`install.sh --project` already wires `agent_admin project bootstrap` under the
hood, so the same lazy-spawn install flow works for additional projects too.

### Switch context

```bash
agent_admin project use <new-name>
```

### Retire the install project and move to `foo`

```bash
INSTALL=install
FOO=foo
agent_admin project use "$FOO"
for seat in $(agent_admin session list --project "$INSTALL" 2>/dev/null | awk '/^running/{print $2}'); do
  agent_admin session stop-engineer "$seat" --project "$INSTALL" 2>/dev/null || true
done
tmux kill-session -t "project-${INSTALL}-monitor" 2>/dev/null || true
agent_admin session start-project "$FOO" --reset
# agent_admin project delete "$INSTALL"   # only if you want to wipe state
```

`project use` switches context without killing sessions; the seat-stop loop + monitor kill is what "retires" the install grid.

---

## Failure modes (consolidated)

| Code | Symptom | Recovery |
|------|---------|----------|
| `INSTALL_BROKEN` | repo missing or `scripts/install.sh` absent | reclone or restore install entrypoint |
| `PREREQ_MISSING` | tmux / iTerm2 / Python 3.11 / claude missing | install the dep, rerun Step 2 |
| `ENV_SCAN_FAILED` | machine JSON files missing | rerun Step 2; debug `scan_environment.py` if repeatable |
| `PROVIDER_NO_KEY` | no provider key, operator skipped prompt | supply a valid key, rerun Step 2 |
| `GRID_LAUNCH_FAILED` | install-* sessions missing | rerun Step 2 |
| `ITERM_DRIVER_FAIL` | pane driver error | verify iTerm2 + Python SDK, rerun Step 2 |
| `B2-memory-dead` | memory seat dead | ancestor halts, reports |
| `B2.5-bootstrap-failed` | machine.toml tenant write failed | check `~/.clawseat/` permissions |
| `B3-binding-mismatch` | openclaw binding project mismatch | fix binding, retry Phase-A |
| `B3.5_TIMEOUT` | seat did not come up | retry that seat only |
| `B5-feishu-binding-missing` | no feishu_group_id | operator may skip → CLI-only mode |
| `B6-smoke-failed` | smoke failed | keep `phase=blocked`, inspect logs |
| `B7-status-write-failed` | STATUS.md cannot be written | diagnose disk / permissions |
| `ACCEPTANCE_FAILED` | final state mismatched | inspect `STATUS.md`, tmux sessions |
| `ERR_NO_OPENCLAW_AGENTS` | koder overlay: no tenants registered | run B2.5 first or `agent_admin tenant register` manually |

---

## Resume

To rerun bootstrap safely (idempotent):

```bash
bash scripts/install.sh
```

To resume from a blocked Phase-A step:

```bash
tmux attach -t install-ancestor
```

Then tell ancestor to continue from the blocked token after fixing the underlying issue.

**Hard rule**: do not invent steps outside this file. If a required action is not
covered here, stop and surface the gap instead of improvising.
