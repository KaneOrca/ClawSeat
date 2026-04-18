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
git clone https://github.com/garrytan/gstack.git ~/.gstack/repos/gstack
cd ~/.gstack/repos/gstack && ./setup
```

## Quick Install

```bash
# Clone to any user-level directory (NOT inside ~/.openclaw/)
git clone https://github.com/KaneOrca/ClawSeat.git
export CLAWSEAT_ROOT="$(pwd)/ClawSeat"

# Install skill symlinks into OpenClaw
python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_openclaw_bundle.py"
```

After install, say "启动 ClawSeat" in OpenClaw/Feishu, or run `/cs` in Claude Code.

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
