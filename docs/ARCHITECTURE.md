# ClawSeat Architecture

> See also: [CANONICAL-FLOW.md](CANONICAL-FLOW.md) for the runtime protocol
> (dispatch / completion / ACK), [PACKAGING.md](PACKAGING.md) for what ships
> in the product bundle, [RUNTIME_ENV.md](RUNTIME_ENV.md) for env vars and
> directory contracts.

## Goal

ClawSeat is a reusable skill-first multi-agent control plane for running
project-scoped AI teams with durable task state.

## Mental Model

The preferred external mental model is:

- ClawSeat behaves like a heavy skill that can be installed onto an agent
- once loaded, that agent becomes the frontstage `koder`
- `koder` uses the framework to recommend seats, materialize project-scoped
  workspaces, and launch the team

The implementation model is:

- the skill is only the entrypoint
- the real system also includes the control plane, runtime contracts, transport
  helpers, adapters, and project fixtures

Its core abstractions are:

- `project`
- `seat`
- `session`
- `workspace`
- `runtime`
- `handoff`

## Layers

### 1. Control Plane

Owns:

- project creation/bootstrap
- seat/session lifecycle
- auth/runtime switching
- tmux/iTerm window layout
- workspace contract rendering

Primary home:

- `core/scripts/agent_admin*.py`

### 2. Runtime Contract Layer

Owns:

- seat contract
- workspace contract
- heartbeat manifest / receipt
- dispatch / completion / ACK model

Primary home:

- `core/harness_adapter.py`
- `core/templates/`
- `core/skills/gstack-harness/`

### 3. Skill Layer

Owns:

- dispatch helper
- completion helper
- patrol / console
- seat launch protocol

Primary home:

- `core/skills/gstack-harness/`

### 4. Adapter Layer

Owns:

- project-specific seat rules
- project-specific handoff conventions
- project-specific startup notes

Examples:

- `adapters/projects/openclaw/`

### 5. Sample / Fixture Layer

Owns:

- smoke-test projects
- example profiles
- migration fixtures

Examples:

- `examples/arena-pretext-ui/`

## Component Inventory

Inside ClawSeat (this repo):

- control plane — `core/scripts/agent_admin*.py`
- core harness — `core/skills/gstack-harness/`
- shared transport helpers — `core/shell-scripts/`
- harness adapter interface + tmux-cli implementation — `core/harness_adapter.py`, `adapters/harness/tmux-cli/`
- OpenClaw project adapter — `adapters/projects/openclaw/`
- OpenClaw plugin shell — `shells/openclaw-plugin/`

Outside ClawSeat by design:

- the full `cartooner` product source tree (separate repo)
- the full `openclaw` product source tree (separate repo — ClawSeat only ships the plugin bridge)

## Non-Goals

ClawSeat should not contain the product source trees of its consumers.

These stay out of the framework repo:

- full `cartooner` app source
- full `openclaw` source
- unrelated workspace artifacts
