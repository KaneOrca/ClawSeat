# ClawSeat Architecture

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

Primary home — **split into focused modules (2026-04 refactor, commit `0e8999c`)**:

- `core/scripts/agent_admin.py` — dispatcher + top-level main; wires the hook dataclasses
- `core/scripts/agent_admin_config.py` — paths, `SUPPORTED_RUNTIME_MATRIX`, `CodexProviderConfig` schema, backend CLI binary resolution
- `core/scripts/agent_admin_runtime.py` — env/secret/identity helpers, codex `config.toml` renderer
- `core/scripts/agent_admin_store.py` — project/engineer/session TOML I/O
- `core/scripts/agent_admin_crud.py` — engineer create / rebind / delete
- `core/scripts/agent_admin_session.py` — seat start/stop lifecycle
- `core/scripts/agent_admin_switch.py` — harness/auth switch-in-place
- `core/scripts/agent_admin_resolve.py` — seat resolution + provider seed
- `core/scripts/agent_admin_template.py` — template rendering (workspace contracts)
- `core/scripts/agent_admin_workspace.py` — workspace-guide / role / skill-catalog fragments
- `core/scripts/agent_admin_window.py` — iTerm / tmux window layouts
- `core/scripts/agent_admin_heartbeat.py` — heartbeat provision + receipt
- `core/scripts/agent_admin_commands.py` — top-level CLI command handlers
- `core/scripts/agent_admin_info.py` — engineer/session summary formatters
- `core/scripts/agent_admin_parser.py` — argparse wiring
- `core/scripts/agent_admin_legacy.py` — **imported lazily** from `agent_admin.py` only when a migration operation runs (audit H8); archive_if_exists is inlined on the hot path
- `core/scripts/agent_admin_tui.py` — optional Textual UI

### 2. Runtime Contract Layer

Owns:

- seat contract
- workspace contract
- heartbeat manifest / receipt
- dispatch / completion / ACK model
- seat transport routing (tmux / OpenClaw-Feishu / file-only)

Primary home:

- `core/harness_adapter.py` — abstract HarnessAdapter Protocol
- `core/templates/` — role template TOMLs
- `core/skills/gstack-harness/` — canonical runtime skill (see §3)
- `core/transport/transport_router.py` — **single entry point for dispatch/notify/complete/render-console** (audit H1). Routes to either `core/migration/*_dynamic.py` (dynamic-roster profiles) or `core/skills/gstack-harness/scripts/*.py` (legacy profiles) based on `[dynamic_roster].enabled`. Do not import the underlying scripts directly.
- `core/migration/` — dynamic-roster siblings for `dispatch_task` / `notify_seat` / `complete_handoff` / `render_console`. Share `_task_io.build_notify_payload` and other helpers via `dynamic_common.BASE_COMMON` (audit H2). Anti-drift is enforced by `tests/test_transport_router.py::test_shared_task_io_helpers_do_not_fork` over the full list in `SHARED_TASK_IO_HELPERS` — if you fork a helper into `dynamic_common.py` instead of re-exporting, that test fails.
- `core/lib/seat_resolver.py` — tmux vs openclaw vs file-only routing hook used by notify_seat + complete_handoff (upstream T19)
- `core/engine/instantiate_seat.py` — seat materialization: workspace + symlinks + session records + tmux config

#### Heartbeat transport vs runtime seats

Two profile fields control how the frontstage seat is represented at runtime:
`heartbeat_transport` says whether the `heartbeat_owner` is a tmux seat or an
OpenClaw-frontstage agent, while `runtime_seats` says which seats should
receive runtime/session records for that profile.

| Mode | Canonical profile | `heartbeat_transport` | `runtime_seats` effect |
|---|---|---|---|
| Local `/cs` | `install-with-memory.toml` | `tmux` | `koder` remains a tmux seat alongside `memory` and backend seats |
| OpenClaw overlay | `install-openclaw.toml` | `openclaw` | `koder` stays frontstage and is excluded from tmux runtime records; `memory` and backend seats still run in tmux |

### 3. Skill Layer

Owns:

- dispatch helper
- completion helper
- patrol / console
- seat launch protocol

Primary home:

- `core/skills/gstack-harness/`

#### Entry-point skill boundaries

Four ClawSeat-owned entry-point skills share the `clawseat*` / `cs` namespace.
Their responsibilities are deliberately non-overlapping — if you are unsure
which one to edit, use this table before you touch either:

| Skill | Role | Invoked by | Writes |
|---|---|---|---|
| `clawseat` | Product façade. One-liner that loads the install runbook and hands off. | OpenClaw / Feishu / Claude Code / Codex when the user says "启动 ClawSeat" | Nothing directly; delegates to `clawseat-install` |
| `clawseat-install` | 6-phase install SOP (`core/skills/clawseat-install/scripts/*.py`). Phases P0–P5 in `references/ancestor-runbook.md`. | Ancestor agent, step-by-step per user confirmation | `~/.openclaw/skills/*`, `~/.agents/profiles/*.toml`, `~/.claude/skills/*`, Feishu bridge config |
| `clawseat-koder-frontstage` | Runtime wrapper for the user-visible `koder` seat (reads `PLANNER_BRIEF`, enforces transport via router). Not an installer. | The `koder` seat itself after install | Never writes workspaces; only reads + dispatches |
| `cs` | Local `/cs` convenience alias (**post-install only**). Resumes or creates the canonical `install` project and starts `planner`. | User in a local Claude Code / Codex session after `clawseat-install` has completed P0–P5 | Minimal — resumes existing `~/.agents/projects/install` state |

Invariant — do not cross the boundaries:

- `clawseat` must not write install state (no `~/.agents/*` writes; delegate to `clawseat-install`)
- `clawseat-install` must not read from `PLANNER_BRIEF` (it runs before seats exist)
- `clawseat-koder-frontstage` must not call `install_*` scripts (install is ancestor-owned)
- `cs` must fail fast if `~/.agents/projects/install/session.toml` is missing (it is post-install only; guard with `install_entry_skills.py` check)

### 4. Adapter Layer

Owns:

- project-specific seat rules
- project-specific handoff conventions
- project-specific startup notes

Examples:

- `adapters/projects/cartooner/`
- `adapters/projects/openclaw/`

### 5. Sample / Fixture Layer

Owns:

- smoke-test projects
- example profiles
- migration fixtures

Examples:

- `examples/arena-pretext-ui/`

## Current Migration Status

Already inside ClawSeat:

- control plane (`core/scripts/agent_admin*.py`, split into 15 focused modules as of 2026-04)
- core harness (`core/skills/gstack-harness/` runtime + `core/migration/` dynamic-roster siblings)
- canonical transport router (`core/transport/transport_router.py`; dead `core/transport.py` removed in audit H1)
- shared transport helpers (`core/shell-scripts/`, with input validation on `send-and-verify.sh` — audit H3)
- harness adapter interface + tmux-cli implementation (`core/harness_adapter.py`, `adapters/harness/tmux-cli/`)
- shared shell shim base (`shells/_shim_base.py`; each bundle under `shells/*/adapter_shim.py` is a thin wrapper — audit M1)
- memory-oracle skill (`core/skills/memory-oracle/`, introduced in upstream T7/T22)
- Cartooner adapter (`adapters/projects/cartooner/`)

Recent structural changes:

- **2026-04 — agent_admin split (commit `0e8999c`)** — monolith → 15 focused modules.
- **2026-04 — gstack-harness runtime embedded (commit `b35bfc0`)** — `core/skills/gstack-harness/scripts/` now carries the runtime scripts once shared with an external gstack checkout.
- **2026-04 — core/migration/ layer** — houses `*_dynamic.py` scripts that replace the legacy harness scripts for profiles with `[dynamic_roster].enabled = true`. Traffic flows through `core/transport/transport_router.py` so callers never pick the wrong path by hand.
- **2026-04 — transport/payload consolidation (audit P0/P1)** — `build_notify_payload` extracted into `_task_io.py`, rendering/validation for codex provider config moved into a typed `CodexProviderConfig` dataclass, shells/*/adapter_shim.py collapsed onto `_shim_base.py`.

Still outside ClawSeat by design:

- the full `cartooner` product source tree
- the full `openclaw` product source tree

## §3b — state.db: Single-Source-of-Truth Ledger (C8)

### Why state.db

Prior to C8, answering "where is seat X and what is it doing?" required grepping
six separate artefacts: `session.toml`, `WORKSPACE_CONTRACT.toml`,
`PROJECT_BINDING.toml`, `patrol/handoffs/*.json`, `openclaw.json`, and
`~/.agents/sessions/…`. Four concrete pain points drove the consolidation:

1. **Dispatcher blindness** — `dispatch_task.py` hardcodes `builder-1`; other
   builder seats idle because no index exists of live seats and their load.
2. **Silent chain stalls** — Feishu closeouts depend on planner remembering to
   call `send_delegation_report.py`; a missed call stalls the chain silently.
3. **Scattered state** — Six files, none authoritative, each requiring custom
   regex to reconstruct seat status.
4. **Manual deploy sync** — `~/.clawseat/` is an independent git clone; code
   changes require a manual `git pull` on both sides to stay in sync.

`state.db` is a single SQLite file at `~/.agents/state.db` that provides a
derived, queryable view over all six artefacts. In C8 it is **read-only** from
production paths; existing artefacts remain authoritative.

### Schema (ER summary)

```
projects ──< seats ─< tasks
                            \
                             events (append-only log)

projects  : name (PK), feishu_group_id, feishu_bot_account, repo_root,
            heartbeat_owner, active_loop_owner, bound_at
seats     : (project, seat_id) PK, role, tool, auth_mode, provider,
            status, last_heartbeat, session_name, workspace
tasks     : id PK, project, source, target, role_hint, status,
            title, correlation_id, opened_at, closed_at, disposition
events    : id AUTOINCREMENT, ts, type, project, payload_json
```

Indexes: `idx_seats_status(project, role, status)`,
`idx_tasks_open(project, target, status)`, `idx_events_ts(ts)`.

### Read/write flow

```
operator / C9 dispatcher
        │
        ▼
core/lib/state.py  (stdlib sqlite3 — no ORM, no external deps)
        │
        ▼
~/.agents/state.db  (WAL mode, foreign_keys=ON)
```

All public API functions accept a `conn: sqlite3.Connection` as their first
argument for testability. `open_db(db_path=None)` auto-applies the schema on
first call via `CREATE TABLE IF NOT EXISTS`; re-opening is a no-op.

`seed_from_filesystem(home, *, conn)` reads the six legacy artefacts and
populates the DB idempotently. It is safe to re-run at any time: `upsert_*`
uses `INSERT … ON CONFLICT DO UPDATE`; `record_task_dispatched` uses
`INSERT OR IGNORE` so completed tasks never lose their `disposition`.

The operator CLI is `core/scripts/state_admin.py`:

```bash
state-admin seed                          # populate from filesystem
state-admin show-seats [--project X]      # list seats
state-admin show-tasks [--project X] [--status open]
state-admin pick --project X --role builder
state-admin recent-events [--limit 20]
```

### Forward roadmap

- **C9** — dispatcher adds `--target-role` mode, uses `pick_least_busy_seat`
  to route to the least-loaded live builder instead of hardcoding `builder-1`.
- **C10** — events table gains a watcher that materialises closeouts and
  notifications from events rather than ad-hoc writes.
- **C11** — `feishu-announcer` subscribes to events, replaces manual
  `send_delegation_report.py` calls.

`pick_least_busy_seat` is already in the C8 API and covered by tests so that
C9 can integrate it on day one with full test coverage in place.

---

## Non-Goals

ClawSeat should not contain the product source trees of its consumers.

These stay out of the framework repo:

- full `cartooner` app source
- full `openclaw` source
- unrelated workspace artifacts
