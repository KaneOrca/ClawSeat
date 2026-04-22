# ClawSeat

ClawSeat is an independent skill-first multi-agent control plane.

It is not `cartooner`, `openclaw`, or any consumer project checkout.
Those projects can adapt to ClawSeat, but they are not part of ClawSeat's core source tree.

## Install

v0.5 install is agent-driven. The single source of truth is
[`docs/INSTALL.md`](docs/INSTALL.md). There is no separate TUI bootstrap
binary to memorize.

### Step 1 — Clone and set `CLAWSEAT_ROOT`

```bash
git clone https://github.com/KaneOrca/ClawSeat.git "$HOME/ClawSeat"
export CLAWSEAT_ROOT="$HOME/ClawSeat"
```

> Clone to a user-level directory (NOT inside `~/.openclaw/`). ClawSeat is a
> standalone project, not an OpenClaw internal component.

### Step 2 — Run the playbook

Tell the invoking runtime (Claude Code, Codex, or OpenClaw) to read
[`docs/INSTALL.md`](docs/INSTALL.md) and execute it end-to-end. The playbook:

1. scans the machine and credential state
2. records the runtime selection the user wants
3. materializes validated project/profile/binding state
4. launches the ancestor via [`scripts/launch_ancestor.sh`](scripts/launch_ancestor.sh)
5. hands control to ancestor for seat bring-up and patrol

### Resume / re-entry

Re-run [`docs/INSTALL.md`](docs/INSTALL.md) and follow its `Resume / Re-entry`
section. `/cs` is only a local shorthand for that re-entry contract; it is not
a fresh-install path.

### Starting over / fresh-machine simulation

Reset to a clean baseline (testing the git install on the same machine,
uninstalling ClawSeat, preparing a CI smoke fixture):

```bash
bash scripts/clean-slate.sh         # dry-run: shows what would be deleted
bash scripts/clean-slate.sh --yes   # actually delete
```

The script preserves OpenClaw account data (`~/.openclaw/agents/`, `openclaw.json`),
API secrets (`~/.agent-runtime/secrets/`), gstack, and lark-cli OAuth. It
deletes ClawSeat-installed skill symlinks, `~/.agents/`, and sandbox residue.
See the script header for the full preserve/delete list.

### Legacy profiles (pre-v0.5)

The old v1 profile templates are no longer shipped in-tree. New installs should
follow [`docs/INSTALL.md`](docs/INSTALL.md) and write validated v2 profiles
instead. If you need to migrate an existing v1 profile, use:

```bash
python3 core/scripts/migrate_profile_to_v2.py apply --project <name>
```

## Positioning

Externally, ClawSeat should be understood as an installable skill/plugin
product:

- in OpenClaw or Feishu environments, let the runtime load the `clawseat`
  skill/plugin and route into the same v0.5 install playbook
- in Claude Code or Codex, install the ClawSeat entry skills locally and treat
  `clawseat` as the fresh-install entry
- treat `/cs` only as a local re-entry shorthand after install state already
  exists
- fresh install writes validated state, launches `ancestor`, and hands project
  runtime ownership to `ancestor`
- `koder` is the tenant-side Feishu/OpenClaw frontstage when bound; it is not
  the local install frontstage and not a tmux seat

For OpenClaw, the repo root is now also a marketplace source. That means
OpenClaw can install ClawSeat directly from the repo URL as a Claude-compatible
bundle, without asking end users to understand `/cs`, local skill symlinks, or
the internal repo layout.

Internally, ClawSeat is more than a single skill. It is the framework and
control plane behind that product-shaped skill/plugin entrypoint.

ClawSeat provides:

- control plane for projects, seats, sessions, runtime, and windows
- shared runtime contracts for handoff, ACK, closeout, and patrol
- skill loading and harness orchestration
- transport helpers for seat-to-seat notification
- adapters for consumer projects

For v0.5, the default visible project roster is the fixed six-pane monitor:

- `ancestor`
- `planner`
- `builder`
- `reviewer`
- `qa`
- `designer`

The machine-level `memory` singleton stays off-grid. `koder` also stays
off-grid as the tenant frontstage. Extra numbered sessions such as `builder-1`
or `reviewer-1` are explicit fan-out or compatibility paths, not the default
v0.5 story. Fresh installs bootstrap `ancestor` first; ancestor then brings up
the rest of the monitor and patrol flow. Legacy `engineer-*` seats remain
available through `compat_legacy_seats = true` for migrated projects.

## Boundaries

ClawSeat core should contain only framework concerns:

- `core/scripts/`
- `core/skills/`
- `core/templates/`
- `core/shell-scripts/`
- `core/harness_adapter.py`
- `docs/`
- `adapters/`
- `shells/`
- `examples/`

Consumer projects stay separate:

- `cartooner`
- `openclaw`

## Structure

```text
ClawSeat/
├── core/                    # framework-agnostic control plane/runtime code
│   ├── scripts/             # agent_admin / agentctl Python entrypoints
│   ├── skills/              # reusable framework skills
│   ├── templates/           # project / seat template sources
│   ├── shell-scripts/       # transport/status shell wrappers
│   └── harness_adapter.py   # adapter interface definition
├── adapters/                # harness + consumer adapters
│   ├── harness/
│   └── projects/
├── shells/                  # reserved for future shell implementations
├── examples/                # sample projects / smoke fixtures
└── docs/                    # architecture and migration docs
```

## Current State

Already migrated into ClawSeat:

1. control plane: `core/scripts/agent_admin*`
2. core harness: `core/skills/gstack-harness`
3. shared transport: `core/shell-scripts/send-and-verify.sh` and related helpers
4. adapter interface + tmux harness adapter: `core/harness_adapter.py`, `adapters/harness/tmux-cli/`
5. Cartooner adapter: `adapters/projects/cartooner/`

Still intentionally external:

- the `cartooner` product repo
- the `openclaw` product repo

## Hand-edited profile fields

If you hand-edit a field in the preservation allowlist (e.g.
`heartbeat_transport`, `seats`, `seat_overrides`, `seat_roles`,
`dynamic_roster`), you own it. Bootstrap and reconfigure will preserve
your value and emit a warning to stderr so you can see what was kept.

Fields in the allowlist are never silently overwritten. If you want to
fully reset to the factory template, delete the profile file first, then
run `cs init --refresh-profile`.

## Path Templates

Profile files in this repo may use two portable path forms:

- `{CLAWSEAT_ROOT}` means the absolute filesystem path to the ClawSeat repo root
- `~` means the current user's home directory

Runtime contract:

- export `CLAWSEAT_ROOT=/path/to/ClawSeat` before running ClawSeat helpers on a new machine
- `~` is expanded by Python `Path.expanduser()`
- `{CLAWSEAT_ROOT}` is expanded by the profile loader in
  `core/skills/gstack-harness/scripts/_common.py`

Setup details and examples live in `docs/INSTALL.md`.

## Activating heartbeat for a project

The heartbeat cron wakes koder via Feishu on a launchd schedule.

1. Configure the heartbeat:
   ```bash
   cs heartbeat config set --project install --cadence 10min
   ```
2. Render the launchd plist:
   ```bash
   cs heartbeat render-plist --project install \
     --output ~/Library/LaunchAgents/com.clawseat.heartbeat.install.plist
   ```
3. Load the launchd agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.clawseat.heartbeat.install.plist
   ```
4. Verify:
   ```bash
   tail -f ~/.agents/heartbeat/install.log
   ```

To disable without unloading: `cs heartbeat config set --project install --enabled false`.

## Activating modal detector

The modal detector watches tmux panes for Claude Code numbered-choice
modals and emits `seat.blocked_on_modal` events (picked up by the Feishu
announcer).

```bash
# Install the launchd agent (writes plist, does NOT load it):
python3 core/scripts/modal_detector.py --install-launchd

# Load it:
launchctl load ~/Library/LaunchAgents/com.clawseat.modal-detector.plist

# Verify:
tail -f ~/.agents/logs/modal-detector.log

# One-shot test (dry-run, no DB writes):
python3 core/scripts/modal_detector.py --once --dry-run
```
