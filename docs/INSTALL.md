# ClawSeat Install Notes

## Path Contract

ClawSeat profile files may contain portable placeholders instead of host-local
absolute paths.

Supported forms:

- `{CLAWSEAT_ROOT}`: absolute path to the ClawSeat repository root
- `~`: the current user's home directory

## Required Environment

Before running profile-driven helpers, export the ClawSeat root:

```sh
export CLAWSEAT_ROOT=/path/to/ClawSeat
```

Typical example:

```sh
export CLAWSEAT_ROOT="$HOME/coding/ClawSeat"
```

## Role-First Bootstrap

New projects should default to role-first seat ids such as `planner`,
`builder-1`, and `reviewer-1`.

Shipped starter profiles now come in three tiers:

- `examples/starter/profiles/starter.toml`
  - frontstage-only bootstrap
  - creates a minimal `koder` entrypoint first
- `examples/starter/profiles/install.toml`
  - canonical `/cs` bootstrap profile
  - creates `koder`, `planner`, `builder-1`, and `reviewer-1`
  - intended for the first post-install `install` project
- `examples/starter/profiles/full-team.toml`
  - predeclares `koder`, `planner`, `builder-1`, `reviewer-1`, `qa-1`, and `designer-1`
  - creates all six personal workspaces during bootstrap
  - still defaults to `koder` as the only auto-start seat

Recommended first-run path:

1. In OpenClaw or Feishu-facing runtimes, load the `clawseat` skill/plugin and
   let it route through the OpenClaw bootstrap path.
   The canonical `install` bootstrap now auto-seeds
   `/tmp/install-profile-dynamic.toml` from the shipped `install.toml` profile
   when the machine is starting from a blank state.
2. In Claude Code or Codex local runtimes, install the entry skills with
   `python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"`
3. Only in those local runtimes, use `/cs` as the convenience alias that
   creates or resumes the canonical `install` project and starts `planner`

For dynamic-roster profiles, keep bootstrap minimal:

```toml
[dynamic_roster]
enabled = true
bootstrap_seats = ["koder"]
default_start_seats = ["koder"]
compat_legacy_seats = true
```

This makes fresh bootstraps frontstage-only while preserving legacy
`engineer-*` seats for migrated projects.

## Expansion Rules

- `{CLAWSEAT_ROOT}` is expanded by the profile loader in
  `core/skills/gstack-harness/scripts/_common.py`
- `~` is expanded through Python `Path.expanduser()`
- If `CLAWSEAT_ROOT` is not exported, the loader falls back to the current
  repository root when it is executing inside this checkout

This contract lets shipped `profile.toml` files stay portable across machines
without reintroducing hardcoded developer-home paths.
