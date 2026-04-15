# ClawSeat OpenClaw Plugin

OpenClaw distribution shell for ClawSeat control plane integration.

## Overview

This plugin provides the canonical OpenClaw entry point for running ClawSeat
inside the OpenClaw runtime environment. It bridges the ClawSeat core
framework with OpenClaw's agent scope and session management capabilities.

For OpenClaw and Feishu users, this plugin is the preferred product-shaped
entrypoint. They should install/load ClawSeat as a skill/plugin and let the
runtime start the bootstrap/configure/verify flow automatically, rather than
requiring them to know `/cs`.

## Structure

```
openclaw-plugin/
├── plugin.toml          # Plugin manifest and metadata
├── __init__.py          # Entry module with adapter registration
├── adapter_shim.py      # Bootstrap wiring and adapter fallback logic
└── README.md            # This file
```

## Dependencies

- **clawseat_core**: Framework-agnostic core (task contracts, seat protocol, patrol)
- **openclaw_harness_adapter**: OpenClaw-specific harness adapter (stub, not yet implemented)
- **tmux-cli_harness_adapter**: Fallback harness adapter when OpenClaw adapter is unavailable

## Adapter Resolution

The plugin resolves the harness adapter in the following order:

1. **OpenClaw adapter** (if `core/adapters/harness/openclaw/` is implemented)
2. **tmux-cli adapter** (fallback when OpenClaw adapter is a stub)

When the OpenClaw adapter is not yet implemented, the plugin gracefully falls back to the tmux-cli adapter for session management.

## Usage

This plugin is loaded by the ClawSeat runtime when the `tool` field in a seat
profile is set to `openclaw`.

```toml
# Example seat profile
[seat]
tool = "openclaw"
role = "koder"
```

## Environment Variables

- `CLAWSEAT_ROOT`: Path to the ClawSeat repository root (derived automatically if not set)

## Notes

- Business protocol logic (planner/koder/handoff semantics) lives in `core/`, not in this shell.
- This shell contains only bootstrap wiring, adapter registration, and metadata.
- The OpenClaw harness adapter (`core/adapters/harness/openclaw/`) is currently a placeholder/stub.
- The local `/cs` command remains only a convenience alias for Claude/Codex
  runtimes after their local entry skills are installed.
