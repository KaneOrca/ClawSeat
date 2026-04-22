# ClawSeat v0.5 Install Playbook
This file is the install SSOT. When a user says "install ClawSeat", the invoking
agent reads this repo-local file and executes it end-to-end. The invoking agent
is only the installer; once ancestor is prompt-ready, ancestor owns the runtime.
Subagent mode: seats are encouraged to spawn subagents for independent subtasks.
Ancestor may parallelize seat startup and monitor checks; planner may fan out
reviews or verification work once the grid is up.
## Layered Runtime
- `ancestor = CLI frontstage`, `koder = Feishu frontstage`.
- `memory` is a machine singleton and stays off the project grid.
- The six-pane monitor is fixed: `ancestor (frontstage), planner, builder, reviewer, qa, designer`.
- The valid v0.5 primitives are:
  - [`core/lib/profile_validator.py`](../core/lib/profile_validator.py)
  - [`core/scripts/agent_admin.py`](../core/scripts/agent_admin.py)
  - [`core/launchers/agent-launcher.sh`](../core/launchers/agent-launcher.sh)
  - [`core/shell-scripts/send-and-verify.sh`](../core/shell-scripts/send-and-verify.sh)
## Prerequisites To Clone
0. If the repo is not yet on disk, clone it to a user-level directory. Do not put the checkout under `~/.openclaw/`.
```bash
git clone <repo-url> "$HOME/ClawSeat"
cd "$HOME/ClawSeat"
```
1. Enter the repo root and export `CLAWSEAT_ROOT`.
```bash
cd /path/to/ClawSeat
export CLAWSEAT_ROOT="$PWD"
```
Verify:
```bash
test -d "$CLAWSEAT_ROOT/core" && test -f "$CLAWSEAT_ROOT/docs/INSTALL.md"
```
Failure:
```text
INSTALL_BROKEN: repository root is wrong; docs/INSTALL.md or core/ missing
```
2. Confirm required host tools.
```bash
command -v git
command -v bash
command -v python3
command -v tmux
python3 - <<'PY'
import sys, tomllib
assert sys.version_info >= (3, 11), sys.version
print(sys.version.split()[0])
PY
```
Verify: all commands resolve and Python prints `3.11+`.
Failure:
```text
PREREQ_MISSING: <tool-or-python311>
```
Recovery:
```bash
# macOS
brew install git python@3.11 tmux
# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y git python3.11 tmux
```
3. Confirm at least one supported runtime binary exists.
```bash
command -v claude || true
command -v codex || true
command -v gemini || true
```
Verify: at least one of `claude`, `codex`, `gemini` resolves.
Failure:
```text
PREREQ_MISSING: no supported runtime binary found (claude/codex/gemini)
```
4. Create the installer scratch directory.
```bash
mkdir -p "$HOME/.agents/install"
test -d "$HOME/.agents/install"
```
Failure:
```text
INSTALL_STATE_ERROR: failed to create ~/.agents/install
```
Hard rule: do not invent steps outside this file. If the playbook does not cover a required action, stop and surface the gap instead of improvising a deprecated installer path.
## Step 1: Scan Environment
Goal: produce one JSON manifest the user and downstream seats can both read.
Command:
```bash
python3 "$CLAWSEAT_ROOT/scripts/env_scan.py" \
  --output "$HOME/.agents/install/env-manifest.json"
cat "$HOME/.agents/install/env-manifest.json"
```
What `scripts/env_scan.py` checks:
- `~/.claude/` Claude OAuth evidence
- `~/.agents/.env.global` / `CLAUDE_CODE_OAUTH_TOKEN`
- `~/.agents/secrets/claude/anthropic-console.env` / `ANTHROPIC_API_KEY`
- `~/.agent-runtime/secrets/claude/minimax.env`
- `~/.agent-runtime/secrets/claude/xcode.env`
- `~/.codex/` Codex OAuth evidence + `~/.agent-runtime/secrets/codex/xcode.env`
- `~/.gemini/` Gemini OAuth evidence + `~/.agent-runtime/secrets/gemini/primary.env`
- Anthropic/OpenAI base-url hints and localhost clues
- runtime binaries `claude`, `codex`, `gemini`
Verify:
```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path.home() / ".agents" / "install" / "env-manifest.json"
data = json.loads(p.read_text())
assert "auth_methods" in data and "runtimes" in data
print(len(data["auth_methods"]))
PY
```
Failure:
```text
ENV_SCAN_FAILED: scripts/env_scan.py did not produce ~/.agents/install/env-manifest.json
```
Stop condition: if `auth_methods` is empty, stop immediately and show:
```text
NO_AUTH_FOUND: configure Claude Code auth first, then re-invoke me
```
Notes:
- This manifest is the installer-facing summary.
- `auth_methods[]` is already normalized to exact runtime-matrix triples such as
  `claude/oauth/anthropic`, `claude/oauth_token/anthropic`,
  `claude/api/anthropic-console`, `claude/api/minimax`,
  `codex/oauth/openai`, `gemini/api/google-api-key`.
- Later, once memory is alive, memory can expand it with the richer
  [`core/skills/memory-oracle/scripts/scan_environment.py`](../core/skills/memory-oracle/scripts/scan_environment.py)
  pass.
## Step 2: User Picks Runtime
Goal: convert the raw scan manifest into a concrete runtime plan.
Input:
- `~/.agents/install/env-manifest.json`
Output:
- `~/.agents/install/runtime-selection.json`
Checklist:
1. Read the manifest and show the discovered options exactly as found.
2. If a layer has exactly one sensible choice, say so and use it.
3. If multiple choices exist, ask the user to choose for:
   - `ancestor`
   - `memory`
   - `planner`
   - `specialists` (`builder`, `reviewer`, `qa`, `designer`)
   - `koder_tenant`
4. If the user wants one runtime everywhere, record that explicitly.
5. Write the normalized selection JSON.
Rule:
- `auth_mode` + `provider` must use the exact runtime-matrix names from
  `auth_methods[]`. Do not invent aliases such as `claude/api/anthropic`.
Recommended shape:
```json
{
  "project": "install",
  "koder_tenant": "yu",
  "layers": {
    "ancestor":    {"tool": "claude", "auth_mode": "oauth", "provider": "anthropic", "model": ""},
    "memory":      {"tool": "claude", "auth_mode": "oauth", "provider": "anthropic"},
    "planner":     {"tool": "claude", "auth_mode": "oauth", "provider": "anthropic"},
    "specialists": {"tool": "claude", "auth_mode": "api",   "provider": "minimax"}
  }
}
```
One direct write path:
```bash
cat > "$HOME/.agents/install/runtime-selection.json" <<'JSON'
{
  "project": "install",
  "koder_tenant": "yu",
  "layers": {
    "ancestor":    {"tool": "claude", "auth_mode": "oauth", "provider": "anthropic", "model": ""},
    "memory":      {"tool": "claude", "auth_mode": "oauth", "provider": "anthropic"},
    "planner":     {"tool": "claude", "auth_mode": "oauth", "provider": "anthropic"},
    "specialists": {"tool": "claude", "auth_mode": "api",   "provider": "minimax"}
  }
}
JSON
```
If the user does not request a fixed model, leave `"model": ""` and let the runtime default apply.
Verify:
```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path.home() / ".agents" / "install" / "runtime-selection.json"
data = json.loads(p.read_text())
for key in ("ancestor", "memory", "planner", "specialists"):
    layer = data["layers"][key]
    assert layer["tool"] and layer["auth_mode"] and layer["provider"]
print("ok")
PY
```
Failure:
```text
RUNTIME_SELECTION_INCOMPLETE: runtime-selection.json is missing layer/tool/auth/provider data
```
If the user will not choose and multiple sensible options exist, stop instead
of guessing.
## Step 3: Build Seat Infrastructure
Goal: materialize project directories, validated profile state, and project
binding using the existing admin + validator primitives.
Inputs:
- `~/.agents/install/env-manifest.json`
- `~/.agents/install/runtime-selection.json`
- user-provided Feishu group id `oc_<...>`
Checklist:
1. Create or verify the project shell.
```bash
export PROJECT=install
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" \
  project create "$PROJECT" "$CLAWSEAT_ROOT" || \
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project show "$PROJECT"
```
2. Copy installer artifacts into the project task tree so ancestor and memory can read them later.
```bash
mkdir -p "$HOME/.agents/tasks/$PROJECT/install"
cp "$HOME/.agents/install/env-manifest.json" \
   "$HOME/.agents/tasks/$PROJECT/install/env-manifest.json"
cp "$HOME/.agents/install/runtime-selection.json" \
   "$HOME/.agents/tasks/$PROJECT/install/runtime-selection.json"
```
3. Write the project profile through
   [`core/lib/profile_validator.py`](../core/lib/profile_validator.py). Do not
   hand-write unchecked TOML.
```bash
python3 - <<'PY'
import json, os
from pathlib import Path
from core.lib.profile_validator import write_validated
project = os.environ.get("PROJECT", "install")
root = Path(os.environ["CLAWSEAT_ROOT"]).resolve()
home = Path.home()
selection = json.loads((home / ".agents" / "install" / "runtime-selection.json").read_text())
tasks_root = home / ".agents" / "tasks" / project
specialists = selection["layers"]["specialists"]
payload = {
    "version": 2,
    "profile_name": project,
    "template_name": "gstack-harness",
    "project_name": project,
    "repo_root": str(root),
    "tasks_root": str(tasks_root),
    "project_doc": str(tasks_root / "PROJECT.md"),
    "tasks_doc": str(tasks_root / "TASKS.md"),
    "status_doc": str(tasks_root / "STATUS.md"),
    "send_script": str(root / "core" / "shell-scripts" / "send-and-verify.sh"),
    "agent_admin": str(root / "core" / "scripts" / "agent_admin.py"),
    "workspace_root": str(home / ".agents" / "workspaces" / project),
    "handoff_dir": str(tasks_root / "patrol" / "handoffs"),
    "machine_services": ["memory"],
    "openclaw_frontstage_agent": selection["koder_tenant"],
    "seats": ["ancestor", "planner", "builder", "reviewer", "qa", "designer"],
    "seat_roles": {"ancestor": "ancestor", "planner": "planner-dispatcher", "builder": "builder", "reviewer": "reviewer", "qa": "qa", "designer": "designer"},
    "seat_overrides": {"ancestor": selection["layers"]["ancestor"], "planner": selection["layers"]["planner"], "builder": specialists, "reviewer": specialists, "qa": specialists, "designer": specialists},
    "dynamic_roster": {"enabled": True, "session_root": str(home / ".agents" / "sessions"), "bootstrap_seats": ["ancestor"], "default_start_seats": ["ancestor", "planner", "builder", "reviewer", "qa", "designer"]},
    "patrol": {"planner_brief_path": str(tasks_root / "planner" / "PLANNER_BRIEF.md"), "cadence_minutes": 30},
    "observability": {"announce_planner_events": True, "announce_event_types": ["task.completed", "chain.closeout"]},
}
write_validated(payload, home / ".agents" / "profiles" / f"{project}-profile-dynamic.toml")
print(project)
PY
```
4. Bind the Feishu group.
```bash
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" \
  project bind --project "$PROJECT" --feishu-group "<oc_group_id>" \
  --feishu-bot-account koder
```
Rules:
- group id must start with `oc_`
- keep install default as non-mention-gated by leaving `--require-mention`
  unset; `koder` is the Feishu frontstage
- if bind reports auth refresh or missing group metadata, repair Feishu auth
  first, then rerun the bind
5. If the user already knows the OpenClaw tenant for koder, bind it now.
```bash
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" \
  project koder-bind --project "$PROJECT" --tenant "<tenant_id>"
```
6. Validate the resulting state.
```bash
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project validate --project "$PROJECT"
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project binding-show "$PROJECT"
```
Verify:
- `~/.agents/profiles/install-profile-dynamic.toml` exists
- project validation exits `0`
- `PROJECT_BINDING.toml` shows non-empty `feishu_group_id`
Failure:
```text
PROJECT_BOOTSTRAP_FAILED: profile/binding creation or validation failed
```
## Step 4: Launch Ancestor
Goal: start the install frontstage once, then hand control over.
Launcher contract:
- [`scripts/launch_ancestor.sh`](../scripts/launch_ancestor.sh)
- It reuses:
  - [`core/scripts/agent_admin.py`](../core/scripts/agent_admin.py)
  - [`core/launchers/agent-launcher.sh`](../core/launchers/agent-launcher.sh)
  - [`core/shell-scripts/send-and-verify.sh`](../core/shell-scripts/send-and-verify.sh)
Interface:
```bash
scripts/launch_ancestor.sh --project <name> \
  --tool claude \
  --auth-mode oauth|oauth_token|api \
  --provider anthropic|anthropic-console|minimax|xcode-best|openai|google|google-api-key \
  [--model <model-id>]
```
Notes:
- `--provider` must stay on the exact runtime-matrix name already recorded in
  `runtime-selection.json`.
- `--model` is optional and currently only applies when `--tool claude`.
Resolve ancestor runtime once:
```bash
eval "$(python3 - <<'PY'
import json
from pathlib import Path
layer = json.loads((Path.home()/'.agents/install/runtime-selection.json').read_text())['layers']['ancestor']
print(f"ANCESTOR_TOOL={layer['tool']}")
print(f"ANCESTOR_AUTH_MODE={layer['auth_mode']}")
print(f"ANCESTOR_PROVIDER={layer['provider']}")
print(f"ANCESTOR_MODEL={layer.get('model','')}")
PY
)"
```
Launch:
```bash
cmd=(
  "$CLAWSEAT_ROOT/scripts/launch_ancestor.sh"
  --project "$PROJECT"
  --tool "$ANCESTOR_TOOL"
  --auth-mode "$ANCESTOR_AUTH_MODE"
  --provider "$ANCESTOR_PROVIDER"
)
[[ -n "${ANCESTOR_MODEL:-}" ]] && cmd+=(--model "$ANCESTOR_MODEL")
"${cmd[@]}"
```
Verify:
```bash
tmux list-sessions | grep "${PROJECT}-ancestor-"
```
Failure:
```text
ANCESTOR_LAUNCH_FAILED: launch_ancestor.sh did not create a prompt-ready ancestor session
```
## Step 5: Hand Off To Ancestor
Once Step 4 succeeds, the invoking agent stops orchestrating.
Before dropping out, confirm these files exist:
- `~/.agents/tasks/install/install/env-manifest.json`
- `~/.agents/tasks/install/install/runtime-selection.json`
- `~/.agents/profiles/install-profile-dynamic.toml`
Then tell the user ancestor is now the install frontstage.
What ancestor is expected to do next:
1. Read `ancestor-bootstrap.md` and execute Phase-A `B1..B7` in order. The runtime brief path is `~/.agents/tasks/<project>/patrol/handoffs/ancestor-bootstrap.md`, exposed to ancestor by `CLAWSEAT_ANCESTOR_BRIEF`.
2. `B2` verifies or launches machine memory from `machine.toml.services.memory`.
3. `B4` launches every pending project seat declared in the brief, including any fan-out `sessions[]`.
4. `B5` verifies `PROJECT_BINDING.toml.feishu_group_id`; `B6` sends the smoke
   report; `B7` writes `STATUS.md phase=ready`.
5. After or alongside that Phase-A path, the usual v0.5 continuation is: memory enriches the environment picture, ancestor reads the result, and the visible monitor uses the fixed role membership:
   - `ancestor (frontstage)`
   - `planner`
   - `builder`
   - `reviewer`
   - `qa`
   - `designer`
Important:
- `memory` runs but stays off-grid.
- `koder` is the Feishu frontstage and is not a tmux pane.
- ancestor includes itself in the grid as the frontstage pane.
Verify handoff:
- ancestor session exists
- `STATUS.md` reaches `phase=ready`
- any B2/B4/B6 degradation is surfaced in `STATUS.md` or alerts
Failure:
```text
HANDOFF_INCOMPLETE: ancestor launched but Phase-A did not reach B7 phase=ready, or halted at B3/B5
```
## Failure Modes
| Failure | Signal | Recovery command |
|---|---|---|
| No auth found | `NO_AUTH_FOUND` | Configure Claude Code auth, then rerun `python3 "$CLAWSEAT_ROOT/scripts/env_scan.py" --output "$HOME/.agents/install/env-manifest.json"` |
| Auth expired / wrong key | missing credential, unsupported combo, or 401-style launcher failure | Refresh the credential, pick a runtime tuple that exactly matches `auth_methods[]`, rerun Step 1, then rerun `"$CLAWSEAT_ROOT/scripts/launch_ancestor.sh" ...` |
| `tmux` missing | `PREREQ_MISSING: tmux` | `brew install tmux` on macOS, then rerun Step 4 |
| Ancestor session conflict | stale session or `session.toml` already exists | `python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" session stop-engineer ancestor --project "$PROJECT"` then rerun Step 4 |
| Binding missing / wrong group | `PROJECT_BOOTSTRAP_FAILED` or binding mismatch | `python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project bind --project "$PROJECT" --feishu-group "<oc_group_id>" --feishu-bot-account koder` |
| Profile invalid | project validate non-zero | Re-run the Step 3 `write_validated(...)` block, then `python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project validate --project "$PROJECT"` |
## Resume / Re-entry
There is no separate resume entrypoint in v0.5. Re-entry means rerunning this
playbook from the top and filling gaps.
Checklist:
1. Re-scan auth and binaries.
```bash
python3 "$CLAWSEAT_ROOT/scripts/env_scan.py" \
  --output "$HOME/.agents/install/env-manifest.json"
```
2. Inspect current project state.
```bash
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project show "$PROJECT"
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project validate --project "$PROJECT"
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project binding-show "$PROJECT"
tmux list-sessions | grep "$PROJECT" || true
```
3. Fill only what is missing.
- If profile or binding is missing, repeat Step 3.
- If ancestor is missing, repeat Step 4.
- If ancestor is alive but the grid is incomplete, let ancestor continue or
  prompt ancestor to fill the missing seats.
- If memory is the only missing piece, let ancestor recover it; memory stays
  off-grid by design.
Success condition for resume:
- ancestor is alive
- project profile validates
- project binding is correct
- the fixed six-pane monitor is open or ancestor confirms it is healthy
If those conditions hold, installation is complete and the invoking agent
stands down.
