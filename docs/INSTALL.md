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

## Expansion Rules

- `{CLAWSEAT_ROOT}` is expanded by the profile loader in
  `.agents/skills/gstack-harness/scripts/_common.py`
- `~` is expanded through Python `Path.expanduser()`
- If `CLAWSEAT_ROOT` is not exported, the loader falls back to the current
  repository root when it is executing inside this checkout

This contract lets shipped `profile.toml` files stay portable across machines
without reintroducing hardcoded developer-home paths.
