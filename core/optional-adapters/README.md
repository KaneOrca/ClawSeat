# Optional Adapters Inventory

> **Status (2026-05-19)** — manifest-only marker, no physical relocation yet.
>
> Per [`docs/architecture/openclaw-decoupling-map-20260518.md`](../../docs/architecture/openclaw-decoupling-map-20260518.md)
> slice S5, the files listed below are **optional adapters**: ClawSeat
> installs and runs without them, and they are loaded only when the matching
> external runtime (OpenClaw / Feishu / Lark / koder) is bound. The
> physical `git mv` into this directory is deferred to a later slice that
> owns the import-path migration; this README marks the inventory so callers
> and reviewers can already treat them as adapter code today.

## Inventory

### Koder bridge skill (OpenClaw reverse channel)

- `core/skills/clawseat-koder/` — payload translator, Feishu card renderer,
  timeout watchdog. Used only when the koder overlay is applied.

### Lark / Feishu CLI skills

- `core/skills/lark-shared/` — shared Lark CLI helpers.
- `core/skills/lark-im/` — Lark IM message / chat / reaction helpers
  (12 reference files).

### OpenClaw installer helpers (run only when overlay opted-in)

- `core/skills/clawseat-install/scripts/init_koder.py`
- `core/skills/clawseat-install/scripts/configure_koder_feishu.py`
- `core/skills/clawseat-install/scripts/find_feishu_group_ids.py`
- `core/skills/clawseat-install/scripts/prune_koder_todo_history.py`

### Koder workspace overlay templates

- `core/templates/koder-workspace-tools/` — dispatch / index / seat / project
  templates rendered by `init_koder.py`.

### Feishu broadcasters

- `core/scripts/feishu_announcer.py` — C11 state.db subscriber. Already
  short-circuits when no project is bound to a Feishu group (S2).
- `core/scripts/heartbeat_beacon.sh` — `lark-cli` heartbeat sender. Install
  the launchd plist only when Feishu is enabled.

### Gstack-harness Feishu helpers

- `core/skills/gstack-harness/scripts/_feishu.py` — Feishu sender used by
  delegation-report announcers. Side-effect free unless invoked.
- `core/skills/gstack-harness/scripts/send_delegation_report.py` — calls
  `_feishu` when a Feishu envelope is requested.

### Reference docs (adapter contract)

- `core/references/feishu-message-marker.md` — Feishu wire-format markers.
- `core/skills/clawseat-install/references/feishu-bridge-setup.md`
- `core/skills/clawseat-install/references/feishu-group-no-mention.md`
- `core/skills/gstack-harness/references/feishu-delegation-report.md`

## Why no `git mv` yet

The decoupling map proposes a single relocation slice that re-homes every
inventory entry under `core/optional-adapters/`. That slice has two
downstream impacts which deserve their own commit:

1. **Import paths**: every caller of `core.scripts.feishu_announcer`,
   `_feishu`, `clawseat-koder` SKILL references, etc., must update. The
   move alone is a ~30-file diff.
2. **Test fixture moves**: ~25 adapter-coverage tests assert against the
   current paths and must move in lockstep with the source.

Doing both in the same commit as the inventory marker would mask the
adapter-isolation intent of S5 in a churn of mechanical renames. The
marker (this file plus the in-source notes) lets reviewers and operators
treat the inventory as adapter code today, while the physical move can
land as a self-contained follow-up.
