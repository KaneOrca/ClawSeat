# ClawSeat

ClawSeat is an independent skill-first multi-agent control plane.

It is not `cartooner`, `openclaw`, or `arena-pretext-ui`.
Those projects can adapt to ClawSeat, but they are not part of ClawSeat's core source tree.

## Positioning

Externally, ClawSeat can be understood as a heavy skill:

- install the ClawSeat entry skill on an agent
- that agent becomes the frontstage `koder`
- `koder` clarifies the request, recommends the team, and then instantiates seats

Internally, ClawSeat is more than a single skill. It is the framework and
control plane behind that skill-first entrypoint.

ClawSeat provides:

- control plane for projects, seats, sessions, runtime, and windows
- shared runtime contracts for handoff, ACK, closeout, and patrol
- skill loading and harness orchestration
- transport helpers for seat-to-seat notification
- adapters for consumer projects

## Boundaries

ClawSeat core should contain only framework concerns:

- `.agent/`
- `.agents/skills/`
- `.scripts/`
- `docs/`
- `adapters/`
- `examples/`

Consumer projects stay separate:

- `cartooner`
- `openclaw`
- `arena-pretext-ui`

## Structure

```text
ClawSeat/
├── .agent/                  # control plane scripts, templates, rules
├── .agents/skills/          # core framework skills
├── .scripts/                # transport helpers
├── adapters/                # consumer adapters (cartooner/openclaw)
├── examples/                # sample projects / smoke fixtures
└── docs/                    # architecture and migration docs
```

## Current State

Already migrated into ClawSeat:

1. control plane: `agent_admin*`
2. core harness: `gstack-harness`
3. shared transport: `send-and-verify.sh` and related helpers
4. Cartooner adapter: profile, wrapper skill, and patrol scripts

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
  `.agents/skills/gstack-harness/scripts/_common.py`

Setup details and examples live in `docs/INSTALL.md`.
