# Legacy v1 profile templates

> **Status**: Archived. v0.3-era. **Do NOT import** for new projects.

These five TOML templates were the canonical install/starter profiles in
ClawSeat ≤ v0.3. They are kept here for two reasons only:

1. `core/scripts/migrate_profile_to_v2.py` may reference them as test
   fixtures when validating the v1→v2 migration path.
2. Operators who still have v1 profiles on disk can compare their files
   against these to understand what migration removes.

## Why they're not in `examples/starter/profiles/` anymore

v0.4 ([docs/schemas/v0.4-layered-model.md](../../../../docs/schemas/v0.4-layered-model.md))
made these templates structurally illegal:

- `version = 1` — v0.4 requires v2 (validator hard-rejects)
- `seats = ["memory", "koder", "planner", "builder-1", ...]` — v0.4 forbids
  `memory` and `koder` as project seats (memory = machine singleton,
  koder = OpenClaw tenant agent), and builder-N / qa-N expand from a
  single role via `parallel_instances`.
- `heartbeat_owner = "koder"` / `heartbeat_seats = ["koder"]` — v0.4
  removed the heartbeat field family entirely (validator rejects).
- No `machine_services` / `openclaw_frontstage_agent` fields — v0.4 requires both.

## What to use instead

For a fresh v0.4 install, run:

```bash
python3 -m core.tui.install_entrypoint --project <name>
```

Or generate a v2 profile directly via the wizard:

```bash
python3 -m core.tui.install_wizard --project <name> --accept-defaults
```

The wizard produces a v2-shaped TOML at
`~/.agents/profiles/<name>-profile-dynamic.toml` and writes the matching
`PROJECT_BINDING.toml`. See `docs/schemas/v0.4-layered-model.md §4` for
the canonical example.

## To migrate an existing v1 profile in place

```bash
python3 core/scripts/migrate_profile_to_v2.py apply --project <name>
```

This emits a `*.bak.v1.<ts>` backup before rewriting.

## File index

| File | Original purpose |
|------|------------------|
| `install.toml` | Minimal v1 install profile (no memory) |
| `install-with-memory.toml` | v1 install with memory seat — was the `/cs` default |
| `install-openclaw.toml` | v1 install variant for OpenClaw heartbeat transport |
| `full-team.toml` | v1 7-seat starter for projects with full team |
| `starter.toml` | v1 minimal starter |

None of these are valid v2 inputs.
