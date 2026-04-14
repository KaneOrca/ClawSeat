# KODER.md Deprecation Notice

`KODER.md` is deprecated for the rebuilt `cartooner` frontstage model.

## New Entry Surface

- seat contract:
  - `/Users/ywf/.agents/workspaces/cartooner/koder/WORKSPACE_CONTRACT.toml`
- runtime bootstrap shim:
  - `/Users/ywf/.agents/workspaces/cartooner/koder/CLAUDE.md`
- reusable frontstage protocol:
  - `/Users/ywf/coding/ClawSeat/core/skills/clawseat-koder-frontstage/SKILL.md`
- adapter:
  - `/Users/ywf/coding/ClawSeat/core/adapter/clawseat_adapter.py`
- repo project knowledge:
  - `/Users/ywf/coding/cartooner/CLAUDE.md`

## What Moved

- frontstage disposition rules moved to the wrapper skill
- transport/dispatch/complete/brief/session behavior moved to the adapter
- cartooner architecture and product constraints stay in repo `CLAUDE.md`
- migration compatibility is declared in the new contract overlay

## Status

Keep the old `KODER.md` only as historical context during Phase 3 migration.
Do not extend it with new protocol behavior.
