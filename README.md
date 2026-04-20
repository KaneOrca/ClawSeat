# ClawSeat

ClawSeat is an independent skill-first multi-agent control plane.

It is not `cartooner`, `openclaw`, or `arena-pretext-ui`.
Those projects can adapt to ClawSeat, but they are not part of ClawSeat's core source tree.

## Profile Selection

| Profile | Seats | Requires gstack? | Use when |
|---|---|---|---|
| `starter.toml` | koder | No | Experimenting, no specialist seats needed |
| `install.toml` | koder + planner + builder-1 + reviewer-1 | **Yes** | Canonical `/cs` install flow |
| `full-team.toml` | 6 seats | **Yes** | Full-roster projects |

All profiles live in `examples/starter/profiles/`. To install gstack (required for `install.toml` and `full-team.toml`):

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.gstack/repos/gstack
cd ~/.gstack/repos/gstack && ./setup
```

> ⚠️  First run can take 10+ minutes — `./setup` calls `brew` which may trigger `brew update` with no progress output. Do not cancel.

### Gstack at a non-canonical location

If you already have gstack cloned somewhere other than `~/.gstack/repos/gstack/`, export:

```bash
export GSTACK_SKILLS_ROOT=/absolute/path/to/your/gstack/.agents/skills
```

ClawSeat's preflight, `install_bundled_skills.py`, `skill_registry`, and `dispatch_task.py` all honor this env var — you do not need to re-clone.

## Install

**ClawSeat install is an interactive 6-phase flow, not a single script.**
It is driven by an **ancestor agent** (a Claude Code session the user has
open) that walks the install step-by-step and halts at user-decision points
(target OpenClaw agent, seat auth/provider, Feishu group ID).

### Step 1 — Clone and set `CLAWSEAT_ROOT`

```bash
# Clone to any user-level directory (NOT inside ~/.openclaw/)
git clone https://github.com/KaneOrca/ClawSeat.git
export CLAWSEAT_ROOT="$(pwd)/ClawSeat"
```

### Step 2 — Ancestor agent reads the runbook and walks the flow

The canonical SOP lives at:
[`core/skills/clawseat-install/references/ancestor-runbook.md`](core/skills/clawseat-install/references/ancestor-runbook.md)

The flow, at a glance:

| Phase | What happens | User interaction |
|---|---|---|
| P0 | `install_bundled_skills.py` (symlinks) + `bootstrap_harness.py` (workspace + `session.toml`) | Confirm project name |
| P1 | `start_seat.py --seat memory` + `notify_seat.py --target memory --kind learning` → memory builds machine/ KB | Trust-folder + /theme on first memory seat launch |
| P2 | `query_memory.py --search agents` → **ask user which OpenClaw agent** | **Pick target agent** (do not auto-pick) |
| P3 | `install_koder_overlay.py --agent <NAME>` + `init_koder.py` | — |
| P4 | Per-seat config: tool / auth_mode / provider / API key | OAuth login / API key entry |
| P5 | Feishu bridge 7-step: `send_delegation_report.py --check-auth` → platform scopes → group ID → bind → smoke | `lark-cli auth login` + Feishu platform scope + group ID |

### Do NOT run individual scripts out of order

Running `install_bundled_skills.py` alone gets you Phase 0 only, with no
memory seat, no agent selection, and no koder overlay. The runbook's halt
conditions and verification checks exist so partial installs fail loudly
instead of leaving a half-wired system.

### After install

Say "启动 ClawSeat" in OpenClaw/Feishu, or run `/cs` in a local Claude Code
session. The `clawseat` skill (loaded via P0.1 symlinks) takes over from
there.

### Starting over / fresh-machine simulation

If you want to re-run the install from a clean baseline — testing the git
install on the same machine, uninstalling ClawSeat, or setting up a CI
smoke fixture — use [`scripts/clean-slate.sh`](scripts/clean-slate.sh):

```bash
bash scripts/clean-slate.sh         # dry-run: shows what would be deleted
bash scripts/clean-slate.sh --yes   # actually delete
```

The script preserves your OpenClaw account (`~/.openclaw/agents/`,
`openclaw.json`), API secrets (`~/.agent-runtime/secrets/`), gstack, and
lark-cli OAuth. It deletes `/tmp/ClawSeat`, ClawSeat-installed skill
symlinks, `~/.agents/`, and sandbox residue. See the script header for the
full preserve/delete list.

> **Reminder**: canonical install profiles (`install.toml`,
> `install-with-memory.toml`, `full-team.toml`) require `gstack` for
> specialist seats — see the `./setup` command in the Profile Selection
> block above if you have not installed it yet.

## Positioning

Externally, ClawSeat should be understood as an installable skill/plugin
product:

- in OpenClaw or Feishu environments, let the runtime load the `clawseat`
  skill/plugin and start the full ClawSeat flow automatically
- in Claude Code or Codex, install the ClawSeat entry skills on the local
  runtime
- treat `/cs` only as a local convenience alias after the install path is in
  place
- the resulting agent becomes the frontstage `koder`
- `koder` clarifies the request, recommends the team, and then instantiates
  seats

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

For new projects, the default seat naming model is role-first:

- `koder`
- `planner`
- `builder-1`
- `reviewer-1`

New dynamic-roster projects should bootstrap only `koder` first. Legacy
`engineer-*` seats remain available through `compat_legacy_seats = true` for
migrated projects.

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
- `arena-pretext-ui`

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
- the `arena-pretext-ui` sample app repo

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

Packaging/export details live in [docs/PACKAGING.md](docs/PACKAGING.md).
