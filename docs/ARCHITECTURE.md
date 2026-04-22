# ClawSeat Architecture

## Goal

ClawSeat is a reusable skill-first multi-agent control plane for running
project-scoped AI teams with durable task state.

## Mental Model

The preferred external mental model is:

- ClawSeat behaves like an installable product skill/plugin that routes the
  host runtime into the v0.5 install playbook
- fresh install writes validated state, launches `ancestor`, and then hands
  project runtime ownership to `ancestor`
- when a Feishu/OpenClaw tenant is bound, `koder` remains the tenant
  frontstage; it does not replace `ancestor` as the project runtime owner
- `/cs` is only the local shorthand for the playbook's `Resume / Re-entry`
  contract after install state already exists

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

#### Layered runtime model (v0.5 semantics)

The v2 profile validator still enforces the layered split introduced in v0.4,
but the operational story in v0.5 is the install playbook in
[`docs/INSTALL.md`](INSTALL.md): write validated state, launch `ancestor`, then
let `ancestor` finish Phase-A. See
[`schemas/v0.4-layered-model.md`](schemas/v0.4-layered-model.md) for the schema
background.

| Layer | Seat(s) | Runtime |
|---|---|---|
| Machine | `memory` (one per host) | tmux `machine-memory-<tool>`; verified or launched by ancestor B2; stays off-grid |
| Tenant | `koder` (one per OpenClaw/Feishu tenant) | tenant frontstage; never a tmux seat; stays off-grid from the six-pane monitor |
| Project | `ancestor`, `planner`, `builder`, `reviewer`, `qa`, `designer` | tmux `<project>-<seat>-<tool>`; fixed six-pane monitor; ancestor owns lifecycle; numbered/fan-out sessions are optional extensions |

v1 profile templates (`install-with-memory.toml`, `install-openclaw.toml`, …)
are archived under `examples/starter/profiles/legacy/` — they declare
`heartbeat_*` fields the v2 validator rejects. Current v0.5 install is
agent-driven: `clawseat-install` plus [`docs/INSTALL.md`](INSTALL.md) write the
validated v2 profile and bootstrap `ancestor` first. There is no separate
install wizard or `/cs` bootstrap path.

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
| `clawseat` | Product entrypoint. Detects runtime, routes fresh installs to the v0.5 playbook, and keeps frontstage semantics straight. | OpenClaw / Feishu / Claude Code / Codex when the user says "启动 ClawSeat" or "install ClawSeat" | Nothing directly; delegates to `clawseat-install` |
| `clawseat-install` | v0.5 agent-driven install playbook. The invoking runtime reads `docs/INSTALL.md`, materializes validated state, launches ancestor via `scripts/launch_ancestor.sh`, and stops once ancestor is prompt-ready. | Claude Code / Codex / OpenClaw runtimes when the user asks to install ClawSeat | `~/.agents/profiles/*.toml`, `~/.agents/tasks/<project>/PROJECT_BINDING.toml`, install artifacts under `~/.agents/tasks/<project>/install/`, entry-skill symlinks in `~/.claude/skills/` and `~/.codex/skills/` |
| `clawseat-koder-frontstage` | Runtime wrapper for the bound Feishu/OpenClaw `koder` frontstage (reads `PLANNER_BRIEF`, handles router/heartbeat duties). Not an installer. | The tenant-facing `koder` frontstage after binding exists | Never writes workspaces; only reads + dispatches |
| `cs` | Local `/cs` convenience alias (**post-install only**). Re-entry shorthand for the `docs/INSTALL.md` `Resume / Re-entry` section; reuses existing install state and relaunches ancestor if needed. | User in a local Claude Code / Codex session after install state already exists | Minimal — may relaunch ancestor/session state, but must not create project/profile/binding from scratch |

The default v0.5 project-grid story is `ancestor` / `planner` / `builder` /
`reviewer` / `qa` / `designer`. Numbered seats such as `builder-1` belong to
fan-out or migration examples, not the top-level narrative.

Invariant — do not cross the boundaries:

- `clawseat` must not write install state (no `~/.agents/*` writes; delegate to `clawseat-install`)
- `clawseat-install` must not read from `PLANNER_BRIEF` (it runs before seats exist)
- `clawseat-koder-frontstage` must not call `install_*` scripts (install is ancestor-owned)
- `cs` must fail fast if the `install` project state is missing or invalid; it may relaunch ancestor, but it must not create the canonical install project, synthesize profile/binding state, or start planner directly

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

### C9: dispatcher wired to state.db (landed)

`dispatch_task.py` (and its dynamic variant `dispatch_task_dynamic.py`) now
accept a `--target-role ROLE` flag as a mutually-exclusive alternative to
`--target SEAT_ID`. When `--target-role` is used:

1. The profile is loaded to get `project_name`.
2. `pick_least_busy_seat(conn, project, role)` is called against state.db.
3. If no live seat matches, the process exits with **rc=3** (`seat_needed`).
4. Otherwise, the resolved `seat_id` is used for the rest of the dispatch.

Both dispatch and completion write to state.db in a **defensive try/except**:
DB failures emit a `warn:` to stderr but never fail the primary dispatch or
handoff. The ledger is still supplementary in C9.

`complete_handoff.py` (and `complete_handoff_dynamic.py`) call
`mark_task_completed` + record a `task.completed` event on every successful
completion, same defensive posture.

The `CLAWSEAT_STATE_DB` env var overrides the default `~/.agents/state.db`
path in `open_db()` — used by all tests for isolation.

### Forward roadmap

- **C10** — events table gains a watcher that materialises closeouts and
  notifications from events rather than ad-hoc writes. ✅ see §3c.
- **C11** — `feishu-announcer` subscribes to events, replaces manual
  `send_delegation_report.py` calls.

---

## §3c — Events Watcher: Subscription Seed (C10)

C8 built the events table. C9 wired `dispatch_task.py` and
`complete_handoff.py` to write events directly from their own code paths.
C10 adds a **passive watcher** (`core/scripts/events_watcher.py`) that
re-derives events from the handoff JSONs on disk — decoupling event
emission from the scripts that write handoffs.

### Why redundant coverage matters

- Legacy code paths (`notify_seat.py`, shell-based dispatches, third-party
  scripts) don't know about state.db — but they all still write handoff
  JSONs under `~/.agents/tasks/<project>/patrol/handoffs/`. Without a
  watcher, their activity is invisible in the events table.
- Defensive retries: if state.db was unavailable when dispatch_task.py
  ran (C9's try/except fallback), the event was lost. The watcher picks
  it up on the next cycle.
- C11 foundation: `feishu-announcer` subscribes to the events stream; a
  richer stream (including legacy tools) makes the subscriber more useful.

### Fingerprint-based deduplication

Each handoff JSON produces a 16-char sha1 fingerprint from
`project|task_id|kind|source|target`. The watcher uses
`record_event_if_new(fingerprint=…)` — a new helper in `state.py` — which
only inserts if no existing row carries that fingerprint. The events
table gains a `fingerprint TEXT` column + index for the lookup; rows
written by C9's direct `record_event()` calls leave fingerprint NULL and
never collide (they're distinct rows by design).

Schema migration for pre-C10 installs: `open_db()` runs
`ALTER TABLE events ADD COLUMN fingerprint TEXT` wrapped in try/except
so re-open is still a no-op.

### Operator mental model

- `--once` — one-shot sweep, suitable for cron or manual use.
- `--watch --interval 30` — daemon mode, SIGINT-clean, polling (no
  inotify/launchd in v1).
- `--dry-run` — preview plan without DB writes.
- `--project install` — scope to a single project directory.

Direct `record_event()` calls in dispatch/completion remain in place —
watcher is **redundant coverage, not replacement**. Deprecation of the
direct writes is a C11 follow-up.

### Event derivation rules

| handoff `kind`               | event `type`        |
| ---------------------------- | ------------------- |
| `dispatch`                   | `task.dispatched`   |
| `completion`                 | `task.completed`    |
| `learning`                   | `patrol.learning`   |
| `notice`/`reminder`/`unblock` | `seat.notified`    |
| anything else                 | `handoff.unknown` (+ stderr warning) |

---

## §3d — Feishu Announcer: First Event-Bus Subscriber (C11)

### Closing the C8 → C9 → C10 → C11 loop

C8 built the `events` table. C9 wired `dispatch_task.py` and
`complete_handoff.py` to write events directly. C10 added a passive watcher
that re-ingests handoff JSONs via fingerprint deduplication. C11 closes the
loop: `core/scripts/feishu_announcer.py` is the **first real subscriber** —
it reads events and sends Feishu delegation-report envelopes automatically.

Before C11, the planner was responsible for remembering to call
`send_delegation_report.py` on every completion. That obligation caused two
silent chain stalls (C8 and C9 closeouts were missed). C11 makes the
notification path **event-driven**: any event of type `task.completed` or
`chain.closeout` is picked up and announced, regardless of which code path
wrote it.

### feishu_sent column and retry semantics

The `events` table gains a `feishu_sent TEXT` column (ISO8601 timestamp).

| Value | Meaning |
|---|---|
| `NULL` | Pending — not yet sent, or send failed, will be retried |
| ISO8601 string | Sent successfully at that UTC time |

`open_db()` applies the migration (`ALTER TABLE events ADD COLUMN feishu_sent
TEXT`) wrapped in `try/except` so re-opening is a no-op. A partial index
`idx_events_feishu_pending ON events(type, feishu_sent) WHERE feishu_sent IS
NULL` keeps the `SELECT` fast even as the events table grows.

Key helpers in `core/lib/state.py`:
- `list_unsent_feishu_events(conn, *, event_types, limit, project)` — returns
  events ordered by `ts ASC` where `feishu_sent IS NULL` and `type IN (…)`.
- `mark_feishu_sent(conn, event_id, ts)` — sets `feishu_sent` on success.

### Announcer modes

```
feishu_announcer.py --once                    # process all pending, exit
feishu_announcer.py --watch [--interval 60]   # loop until SIGINT
feishu_announcer.py --dry-run                 # print envelopes, do not send
feishu_announcer.py --project install         # scope to one project
feishu_announcer.py --types task.completed,chain.closeout
```

On each cycle the announcer calls `_feishu.send_feishu_user_message` and:
- On `status=sent` → calls `mark_feishu_sent`, increments sent count.
- On `status=failed` or any exception → leaves `feishu_sent=NULL`, logs to
  stderr, increments retrying count. The event will be retried on the next
  cycle. The loop never crashes mid-batch.

`SIGINT` is handled cleanly in `--watch` mode: the loop stops after the
current cycle and prints a final tally.

### Why direct send_delegation_report.py calls are NOT yet removed

`dispatch_task.py` and `complete_handoff.py` still contain
`_try_announce_planner_event()` helpers that call `send_delegation_report.py`
directly. These are **not removed in C11** — the announcer needs to prove
itself in the field first. Once C11 is stable and lark-cli auth is refreshed,
those helpers will be removed in C11-v2. Until then, the direct calls act as a
fallback and may produce duplicate Feishu messages (which is preferable to
silent stalls).

---

## §3e — Heartbeat cron (C12)

### Problem

OpenClaw frontstage (koder) is dormant unless the user types. In long-running
projects, koder can sit idle for hours without performing patrol. C12 adds an
automatic wake-up mechanism using launchd + Feishu.

### Design

```
planner-host (operator's laptop)
  └── launchd timer (every N minutes)
        └── core/scripts/heartbeat_beacon.sh <project>
              └── reads ~/.agents/heartbeat/<project>.toml
              └── lark-cli im +messages-send --as user --chat-id <group> --text "[HEARTBEAT_TICK ...]"
                    └── OpenClaw Feishu bridge picks up the message
                          └── pipes into koder's agent input
                                └── koder-frontstage skill recognizes [HEARTBEAT_TICK] header
                                      └── runs patrol: events_watcher, drift scan, STATUS.md refresh
```

The beacon script is purely bash + lark-cli — it does not call Python or pull
in any ClawSeat dependencies. It runs in the operator's laptop launchd
environment, not inside a seat workspace.

### Config schema

`~/.agents/heartbeat/<project>.toml`:

```toml
version = 1
project = "install"
enabled = true
cadence = "10min"         # 5min / 30m / 1h / raw integer seconds
feishu_group_id = "oc_..."
message_template = "[HEARTBEAT_TICK project={project} ts={ts}] koder: run patrol, report drift, update STATUS.md if changed."
created_at = "..."
updated_at = "..."
```

### CLI: `heartbeat_config.py`

Manages the config and renders the launchd plist:

```
heartbeat_config.py set --project X [--cadence 10min] [--template "..."] [--enabled true|false]
heartbeat_config.py show --project X
heartbeat_config.py list
heartbeat_config.py render-plist --project X [--output ~/Library/LaunchAgents/com.clawseat.heartbeat.X.plist]
heartbeat_config.py validate --project X
```

`set` without `--feishu-group-id` auto-pulls from `PROJECT_BINDING.toml`.
`set` warns (to stderr) when the bound group has `feishu_external = true`.

### launchd plist

Generated by `render-plist` from `scripts/launchd/com.clawseat.heartbeat.plist.template`.
The operator runs `launchctl load` manually — C12 never does this itself.

### koder-frontstage integration

The `SKILL.md` Heartbeat reception section describes:
1. Parse `[HEARTBEAT_TICK project=X ts=T]` header.
2. Read recent state.db events.
3. Run drift scan (STATUS.md mtime, in-flight tasks).
4. Post `[HEARTBEAT_ACK ...]` reply.
5. If drift: surface to user + create planner handoff.

### Why not a Python subscriber?

`heartbeat_beacon.sh` runs on the operator's laptop in a launchd context where
pulling Python + ClawSeat libs would require a venv on the host machine. Bash +
lark-cli is sufficient for a one-line message send. The Python tooling
(`heartbeat_config.py`) is only used interactively for config management.

---

## §3f — Profile regeneration discipline (C14)

### Problem

Bootstrap and reconfigure paths write the profile TOML from a hardcoded
template. Any field the operator hand-edited is silently overwritten on
the next regeneration — no warning, no diff, no preserve. This burned us
twice: `feishu_group_id` (fixed in C2 by moving to `PROJECT_BINDING.toml`)
and `heartbeat_transport = "openclaw"` (clobbered back to `"tmux"`,
triggering a phantom tmux session the operator had to manually kill).

### Solution

`render_profile_preserving_operator_edits(target_path, fresh_payload, ...)` in
`core/scripts/agent_admin_workspace.py` reads the existing profile (if any),
and for every field in `PRESERVE_FIELDS` that the operator has set, uses the
existing value instead of the fresh template value. It emits one `stderr`
warning line per divergent field so the operator can see what was preserved.

All profile write paths now go through this helper instead of a direct
`write_text(template_text)`.

### Preservation allowlist

```python
PRESERVE_FIELDS = (
    "heartbeat_transport",  # "tmux" / "openclaw" — the regression source
    "heartbeat_owner",
    "seats",
    "heartbeat_seats",
    "default_start_seats",
    "materialized_seats",
    "runtime_seats",
    "bootstrap_seats",
    "active_loop_owner",
    "default_notify_target",
    "feishu_group_id",     # pre-C2 profiles only
    "seat_roles",          # entire sub-dict
    "seat_overrides",      # each nested sub-dict
    "dynamic_roster",
    "patrol",
    "observability",
)
```

Extra fields in the existing file (not known to the template) are also
carried forward so future schema extensions don't silently disappear.

### Escape hatch

If an operator truly wants to reset to factory defaults: delete the profile
file first, then run `cs init --refresh-profile`. With no existing file,
the fresh template is written verbatim.

### TOML serialization

`_serialize_profile_toml(data)` provides a minimal stdlib-only TOML
serializer for the profile schema (scalars, lists, nested tables up to two
levels deep). Comments from the template are not preserved on re-write —
this is an accepted trade-off since the runtime behavior is unchanged.

---

## §3g — Modal detector: closing the seat-observability gap (C10.5)

### The problem

The C8–C14 event bus knew when tasks were dispatched, completed, or had
Feishu closeouts. What it couldn't see: a seat silently frozen on a
Claude Code numbered-choice modal. No heartbeat divergence. No event row.
Just a frozen pane the operator had to manually discover.

### Design

```
modal_detector (launchd timer, every 60 s)
  └── tmux capture-pane for every live session
        └── _detect_modal() — regex on "Do you want to proceed?" + numbered list
              └── record_event_if_new('seat.blocked_on_modal', fingerprint=…)
                    └── feishu_announcer picks it up on next cycle
                          └── Feishu ping: "install/builder-2 blocked on modal"
```

`modal_detector.py` is a read-only observer. It never clicks, never sends
key input to the pane. Auto-click is deferred to C18 with a strict
allow-list.

### Pattern

The CC v2.x modal looks like:

```
Do you want to proceed?
❯ 1. Yes
  2. Yes, and allow hooks/ access
  3. No
```

`MODAL_PATTERN` matches: `"Do you want to proceed?" line` followed by
`2+ lines of the form [❯] <N>. <text>`. The `❯` marker (cursor position)
is optional — CC sometimes omits it.

### Fingerprint dedup

`_fingerprint(session, question, options)` → `sha1[:16]`. The same stuck
modal scanned every 60 s produces the same fingerprint, so
`record_event_if_new` inserts exactly one `seat.blocked_on_modal` event
per unique modal instance. When the operator resolves it and a new modal
appears, the new text generates a new fingerprint → new event.

### feishu_announcer integration

`_DEFAULT_EVENT_TYPES` in `feishu_announcer.py` was extended to include
`"seat.blocked_on_modal"`. No other changes to the announcer or state.py.

---

## §3h — Dispatch notify: default-ON (C15)

### Problem

`dispatch_task.py` had `--skip-notify` as an opt-out flag, but several
call paths silently suppressed notification even when the flag was absent
(driven by `profile.heartbeat_transport` branch conditions and other logic).
The result: planners routinely dispatched without notifying the target, which
then sat idle until a human manually nudged it.

### Design

Notify is default-ON. Callers opt **out** with `--no-notify`. A deprecated
`--skip-notify` alias is kept for backwards compatibility and emits a
deprecation warning on stderr when used.

```
--notify         # explicit (same as default)
--no-notify      # opt-out
--skip-notify    # [deprecated] use --no-notify
```

`add_notify_args(parser)` and `resolve_notify(args)` are shared helpers
in `_common.py` and re-exported via `dynamic_common.py` so both static
scripts (`dispatch_task.py`, `complete_handoff.py`) and dynamic variants
(`dispatch_task_dynamic.py`, `complete_handoff_dynamic.py`) share a single
implementation — preventing the drift that caused the original bug.

### Invariant

When `do_notify=True`, the notify call is **always** made regardless of
`profile.heartbeat_transport`. The transport affects the delivery mechanism
(tmux vs OpenClaw), not whether notification happens. The `notified_at`
field in the receipt JSON is the observable indicator.

---

## §3i — Seat context-usage watermark (C16)

### Problem

When a seat accumulates ~478k tokens mid-task (as happened with builder-2
during C10), the session becomes too full to process further tasks, but no
patrol alert fires and no Feishu ping is sent. The operator only notices when
manually checking why a task chain has stalled.

### Design

C16 embeds a **token_usage_pct** measurement in every HEARTBEAT_RECEIPT.toml.
When the patrol supervisor reads a receipt with `pct >= 0.80`, it emits a
`seat.context_near_limit` event into state.db. feishu_announcer picks it up
and sends a Feishu alert.

**Receipt schema v2:**
```toml
version = 2                          # bumped from v1
token_usage_pct = 0.37               # 0..1; absent = unknown
token_usage_source = "session_jsonl_size"  # cc_env | session_jsonl_size | unknown
token_usage_measured_at = "..."      # ISO8601
```

Pre-C16 receipts (version=1) missing these fields are read as
`token_usage_pct = None` → no alert fired. Backwards-compatible.

### Measurement heuristic

Sources tried in order:
1. **`CC_CONTEXT_USAGE_PCT` env var** — forward-compat hook for if CC ever
   exposes context usage natively.
2. **session.jsonl file size** — Claude Code logs each turn to a `.jsonl`
   file under `<runtime_dir>/home/.claude/projects/-hash-/session.jsonl`.
   `approx_tokens = size_bytes / 8` (1 token ≈ 8 bytes including JSON
   overhead; safe upper bound). `pct = min(1.0, approx_tokens / max_tokens)`.
   `max_tokens` defaults to 200k (sonnet/opus); 1M for Opus 1M variants.
3. **Fallback** — `(None, "unknown")` if no file found or any error occurs.

~30% error bar. Intended to catch egregious cases (75%+), not pixel-accurate.

### Escalation chain

```
patrol_supervisor.py reads receipt
  → pct >= 0.80
  → state.record_event("seat.context_near_limit", ...)
  → events_watcher.py ingests
  → feishu_announcer.py relays to Feishu group
```

### Threshold

Hardcoded at `0.80` in `patrol_supervisor._CONTEXT_THRESHOLD`. Not
configurable in C16 — a follow-up (C19 candidate) can add per-seat overrides
and an auto-clear path at 0.95.

---

## §3j — Auth-mode operational migration (A1)

Six Claude seats inherited `auth_mode=oauth` from the initial install.
The per-seat sandbox HOME means each seat has its own Keychain slot; an
expired Anthropic OAuth session blocks that seat with an interactive popup
that automation cannot dismiss (upstream issue
[anthropics/claude-code#8938](https://github.com/anthropics/claude-code/issues/8938)).

### Target mapping

| Project | Seat | auth_mode | provider |
|---------|------|-----------|----------|
| install | koder | oauth_token | anthropic |
| install | planner | oauth_token | anthropic |
| install | builder-1 | oauth_token | anthropic |
| install | builder-2 | api | anthropic-console |
| cartooner | planner | oauth_token | anthropic |
| audit | builder-1 | api | anthropic-console |

`oauth_token` uses a 1-year Keychain-free token from `claude setup-token`
(set via `CLAUDE_CODE_OAUTH_TOKEN`). `api/anthropic-console` uses a
Claude Code scoped `ANTHROPIC_API_KEY` from Anthropic Console (no
browser popup, no expiry).

### New provider: `anthropic-console`

Added to `SUPPORTED_RUNTIME_MATRIX["claude"]["api"]` in
`agent_admin_config.py`. Wired in `agent_admin_resolve.build_runtime`:
reads `ANTHROPIC_API_KEY` from the seat's secret file, sets it in the
env, and defensively unsets `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`,
`CLAUDE_CODE_OAUTH_TOKEN`. Uses default `api.anthropic.com` endpoint
(no base-URL override).

### Migration script

`core/scripts/migrate_seat_auth.py` — operator-run one-shot script:

```
migrate-seat-auth plan               # print current → proposed mapping
migrate-seat-auth apply --dry-run    # show agent-admin commands, no changes
migrate-seat-auth apply              # execute migration
```

Preflight checks:
- `CLAUDE_CODE_OAUTH_TOKEN` present in `~/.agents/.env.global` (or `koder.env`)
- `ANTHROPIC_API_KEY` present in `~/.agents/secrets/claude/anthropic-console.env`

Both missing → exit 2 with operator-facing instructions.

Apply is idempotent: seats already at target state are skipped.
After apply, operator restarts affected tmux sessions; the new env takes
effect on the next seat launch.

---

## §3k — P1 layered-engine implementation notes (v0.4)

Binding spec: `docs/schemas/v0.4-layered-model.md`. Phase 1 delivered the
**engine** — parsers, validator, migration tool, and operator-facing
`agent-admin` commands — without touching any on-disk profile. Phase 2
runs the migration when the operator is ready.

### Module map

| Code path | Owns | Schema ref |
|---|---|---|
| `core/lib/machine_config.py` | `MachineConfig` dataclass, load/write, auto-discovery of tenant workspaces, `validate_tenant` | §3 |
| `core/lib/profile_validator.py` | `ValidationResult`, `validate_profile_v2`, `validate_machine_config`, `write_validated` (raises `ProfileValidationError`) | §7 |
| `core/scripts/migrate_profile_to_v2.py` | `plan` / `apply` / `apply-all` / `rollback` with `.bak.v1.<ts>` backups; idempotent on v2 | §6 |
| `core/scripts/agent_admin_layered.py` | Four new subcommands (below) | §3 / §4 / §5 |

### `agent-admin` subcommands added in P1

| Command | Validates | Writes |
|---|---|---|
| `project koder-bind --project X --tenant Y` | tenant ∈ machine.toml openclaw_tenants; tenant workspace exists with `WORKSPACE_CONTRACT.toml` | `workspace-Y/WORKSPACE_CONTRACT.toml .project = X` **and** `PROJECT_BINDING.toml extras.openclaw_frontstage_tenant = Y` — atomic-ish (contract rolls back on binding-write failure) |
| `machine memory show` | — | — (read-only: prints memory service + tmux runtime probe) |
| `project seat list --project X` | — | — (reads v2 profile, expands `parallel_instances` per §8 → `{role}` singleton or `{role}_{n}` fan-out) |
| `project validate --project X` | `validate_profile_v2` over the project's profile | — (rc=0 ok, rc=1 errors) |

### Seat expansion rule (§8)

`parallel_instances = N` on `builder` / `reviewer` / `qa` materialises
tmux seats `{role}_{1..N}` (1-indexed). `N == 1` keeps the bare role
name — matches today's per-role-single topology so existing
`dispatch_task.py --target-role <role>` behavior is preserved without
change (state.db's `pick_least_busy_seat` handles the fan-out
transparently).

### Backup & rollback contract (§6)

`migrate_profile_to_v2 apply` writes a backup
`<profile>.bak.v1.YYYYMMDD-HHMMSS` before calling
`profile_validator.write_validated`. On validation failure the backup is
restored and rc=2 is emitted. `rollback --profile <path>` picks the
latest `.bak.v1.*` and `shutil.copy2`'s it back. Re-applying on an
already-v2 profile is a no-op (prints "already v2" + rc=0) — safe to
automate in CI or scheduled sweeps once Phase 2 operator-commits.

### Parallel-development seam (Phase 1)

`migrate_profile_to_v2` and `agent_admin_layered` import the machine +
validator layers **defensively** — each carries an `_AVAILABLE` flag
with a small stub fallback. When both layers land, the flags flip
`True` and the full validation path activates. This keeps builder-1's
and builder-2's halves shippable on sibling branches without import
failures; see the "parallel-dev fallback" comments at the top of each
module.

### Cross-validation gate

Opening a v2 profile cross-validates three things (§4/§5):

1. `profile.openclaw_frontstage_agent` is a key in
   `machine.toml [openclaw_tenants.*]`.
2. `workspace-<agent>/WORKSPACE_CONTRACT.toml .project` equals
   `profile.project_name`.
3. `PROJECT_BINDING.toml extras.openclaw_frontstage_tenant` (if set)
   matches the profile's agent.

Any mismatch is a hard validation error. The error message includes the
exact fix: `agent-admin project koder-bind --project X --tenant Y`.

### Out of scope (deferred to Phase 2)

- Migrating the real `install` / `cartooner` / `audit` profiles.
- Creating `~/.clawseat/machine.toml` on operator machines (still
  auto-discovered + written on first load by `machine_config.load_machine`).
- TUI / interactive wizard — consumes the validator seam per §9.
- Subagent fan-out docs (Phase 4).

## Non-Goals

ClawSeat should not contain the product source trees of its consumers.

These stay out of the framework repo:

- full `cartooner` app source
- full `openclaw` source
- unrelated workspace artifacts
