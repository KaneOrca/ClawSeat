# ClawSeat OpenClaw / Koder / Feishu / Lark Decoupling Map

- Task: `cf029-clawseat-openclaw-decoupling-map-20260518`
- Authored by: `cartooner-front-builder-2`
- Date: 2026-05-18
- Status: first safe slice — mapping only, no source removal, no PR/push/CI.

## Purpose

Operator direction: Cartooner vends ClawSeat. ClawSeat itself should be
installable and runnable without OpenClaw, Koder, Feishu, or Lark CLI as
mandatory dependencies. Those four remain supported as **optional adapters**
or documentation-only compatibility layers. Before any code is moved or
deleted, this document maps every meaningful coupling under `core/`,
`scripts/`, `docs/`, `templates/`, `tests/`, and `README.md` so subsequent
slices can land safely.

This first slice does not delete or move any adapter code. It produces the
map and the next 3–5 safe follow-up tasks.

## Source Evidence

The classification below is derived from actual `rg` output, not memory-only
recollection. The canonical evidence command, run from `/Users/ywf/coding/ClawSeat`,
is:

```sh
rg -n "OpenClaw|openclaw|Koder|koder|Feishu|feishu|Lark|lark" \
   core scripts docs templates tests README.md
```

Totals as of 2026-05-18:

| Surface         | Files matched |
|-----------------|---------------|
| `core/skills/`  | 76            |
| `core/scripts/` | 26            |
| `core/templates/` | 12          |
| `core/lib/`     | 10            |
| `core/references/` | 3          |
| `core/launchers/` | 3            |
| `core/adapter/` | 3             |
| `core/tui/`     | 2             |
| `core/shell-scripts/` | 2       |
| `core/migration/` | 2            |
| `core/schemas/` | 1             |
| `core/preflight.py`, `core/bootstrap_receipt.py`, `core/skill_registry.py`, `core/skill_registry.toml` | 4 |
| `docs/`         | 17            |
| `scripts/install/` | 3           |
| `scripts/hooks/` | 2            |
| `scripts/apply-koder-overlay.sh`, `scripts/clean-slate.sh` | 2 |
| `templates/`    | 2             |
| `tests/`        | 141           |
| `README.md`     | 1             |
| **Total files** | **312**       |
| **Total line hits** | ~4,012    |

Per-token line counts:

| Token       | Hits  |
|-------------|------:|
| `OpenClaw`  |   271 |
| `openclaw`  |   747 |
| `Koder`     |    67 |
| `koder`     | 1,136 |
| `Feishu`    |   364 |
| `feishu`    | 1,045 |
| `Lark`      |     7 |
| `lark`      |   804 |

The classification below names files and `path:line` source evidence
references for every entry so future slices can re-grep and verify.

## Categories

Each entry is tagged with one of the four required slugs verbatim:
`core-blocking`, `optional-adapter`, `stale-doc`, `test-fixture`.

### core-blocking

These touch ClawSeat install, dispatch, runtime data model, or seat-name
validation. Today, removing them without a refactor would break a default
`clawseat install` even when OpenClaw / Feishu are not desired. Each item
calls out the contract that depends on the coupling.

- `core/lib/state.py` — *source evidence* lines 67–68, 120–121, 205–212,
  320–325, 471–501, 562–563, 692, 707–708. The canonical `state.db` schema
  hard-codes `feishu_group_id`, `feishu_bot_account`, and `feishu_sent`
  columns. `list_unsent_feishu_events` / `mark_feishu_sent` are exported
  on the public surface. Engineer-alias regex maps `koder` →
  `frontstage-supervisor`. Removing requires schema migration and
  rename-aware downstream patches.
- `core/lib/profile_validator.py` — *source evidence* lines 45–48, 88,
  202–238, 279. `_NUMBERED_SEAT_RE` whitelists `koder|builder-N|reviewer-N|patrol-N`,
  so any project profile *must* either name a seat `koder` or be one of
  the numbered roles. `openclaw_frontstage_agent` is a required key when
  `openclaw_tenants` is present; the validator raises with a `koder-bind`
  recovery hint. Today this blocks installs that have no OpenClaw side.
- `core/bootstrap_receipt.py` — *source evidence* lines 40, 47, 49. The
  bootstrap default `heartbeat_owner = "koder"` is the canonical seat that
  receives `[HEARTBEAT_TICK]` ticks. Profiles without OpenClaw still inherit
  this default unless explicitly overridden.
- `core/preflight.py` — *source evidence* lines 4, 550, 801, 811. The
  preflight helper branches on runtime `== "openclaw"` to select
  `install-openclaw.toml` and uses koder vocabulary in module docstring
  ("verifies all prerequisites for a koder seat"). Lark CLI itself is
  already checked via `_check_optional_cli` — that flag is the model that
  should extend to the rest.
- `core/scripts/agent_admin_layered.py` — *source evidence* lines 5,
  123–355. The `agent-admin project koder-bind` subcommand and its
  `KoderBindError`, `do_koder_bind`, `_validate_feishu_group_id`,
  `cmd_project_koder_bind` symbols are part of the public CLI. Recovery
  hints reference `OpenClaw` and `Feishu` directly. The `feishu_group_id`
  format check (`oc_<16+ chars>`) is hard-wired here.
- `core/scripts/agent_admin_parser.py` — *source evidence* lines 78,
  282–401. `parser project bind` exposes `--feishu-group`,
  `--feishu-sender-app-id`, `--feishu-sender-mode`, `--openclaw-koder-agent`,
  `--feishu-bot-account` (deprecated), and the nested `project koder-bind`
  subparser. These are always visible on the CLI regardless of whether
  the operator runs OpenClaw.
- `core/scripts/agent_admin_crud_validation.py`,
  `core/scripts/agent_admin_crud_project.py`,
  `core/scripts/agent_admin_crud_base.py`,
  `core/scripts/agent_admin_crud.py` — *source evidence*
  `agent_admin_crud_validation.py:23–125`,
  `agent_admin_crud_project.py:211–236`,
  `agent_admin_crud_base.py:143–183`,
  `agent_admin_crud.py:91–92`. The CRUD layer wires Feishu identity
  fields into the canonical project record and into seat reseed paths;
  `switch-identity` whitelists `{feishu, gemini, codex}`; lark-cli is a
  default tool seed.
- `core/scripts/agent_admin_session_lifecycle.py`,
  `core/scripts/agent_admin_session_recovery.py`,
  `core/scripts/agent_admin_session_base.py`,
  `core/scripts/agent_admin_window.py`,
  `core/scripts/agent_admin_template.py`,
  `core/scripts/agent_admin_runtime.py`,
  `core/scripts/agent_admin_config.py` — *source evidence*
  `agent_admin_session_lifecycle.py:270–280`,
  `agent_admin_session_recovery.py:29–37`,
  `agent_admin_window.py:242–249, 832, 1184`,
  `agent_admin_template.py:460–629`,
  `agent_admin_runtime.py:169`,
  `agent_admin_config.py:146`. Each module special-cases
  `koder`/`frontstage` identifiers to avoid clobbering an externally
  managed OpenClaw agent (e.g. session recovery skips them; window
  enumeration filters them; template scanner symlinks `openclaw/`).
- `core/scripts/heartbeat_config.py` — *source evidence* lines 35,
  101, 123–143, 178–187, 279–280, 314. The heartbeat config require
  `feishu_group_id` to validate, and CLI exposes `--feishu-group-id`.
  Cross-tenant guard logs warn about Feishu boundary crossing. This is
  a single mandatory binding rather than an opt-in adapter today.
- `core/scripts/migrate_seat_auth.py` — *source evidence* lines 28,
  76–83. The auth-migration matrix hard-codes `("install", "koder")`
  as a known seat mapping and looks up `~/.agents/secrets/claude/koder.env`.
- `core/scripts/migrate_ancestor_paths.py:203` — *source evidence*. Default
  identity substitution still treats `"koder"` as the canonical name.
- `core/scripts/feishu_announcer.py` — *source evidence* lines 1–262. The
  entire C11 subsystem ships in `core/scripts/`. It is a standalone
  subscriber on `state.db` and runs only when invoked, so the *runtime*
  surface is opt-in (covered under `optional-adapter`), but the **file
  lives in core** today; pulling it out is a structural move, not a flag
  flip.
- `core/scripts/events_watcher.py:11` — *source evidence*. The events bus
  has a documented C11 first subscriber (Feishu announcer), embedding
  the assumption that Feishu is the canonical broadcast surface.
- `core/scripts/reconcile_seat_states.py:85, 96` — *source evidence*.
  Seat-state reconciliation has explicit `frontstage-supervisor → koder`
  alias and `("koder", "koder")` pair.
- `core/scripts/skill_manager.py:69` — *source evidence*. Comment notes
  CI runners will not have gstack/openclaw skills; the skill manager
  silently skips them — already adapter-shaped, but still references
  `openclaw` as a recognised category.
- `core/scripts/agent_admin_session_base.py:131` — *source evidence*.
  Per-seat session inherits `.lark-cli` HOME isolation as a default.
- `core/skill_registry.py:93–94` — *source evidence*. Registry's
  "missing-skill" agent-facing message hard-codes the `openclaw-migrated`
  install hint.
- `core/skill_registry.toml:57–384` — *source evidence*. Top-level
  `lark-shared`, `lark-im` skills are registered as first-class entries;
  the `openclaw-migrated` source group anchors 18+ skill rows that
  depend on `~/.agents/skills` openclaw mirrors.
- `core/launchers/agent-launcher.sh:4` — *source evidence*. Launcher
  documentation comment names `scripts/apply-koder-overlay.sh` as a
  user-facing entry alongside `install.sh`.
- `core/launchers/helpers/sandbox.sh:38, 73–104` — *source evidence*.
  Seat sandbox HOME setup blesses `.lark-cli` and seeds the lark-cli
  HOME-override wrapper so sandbox seats can run `lark-cli` transparently.
  Skipping requires sandbox refactor, not just a flag.
- `core/migration/*` (2 files), `core/schemas/*` (1 file),
  `core/tui/*` (2 files), `core/shell-scripts/*` (2 files) — small
  install/migration helpers that name koder/lark by string. Listed here
  because removing the names requires touching install and TUI flows
  which are core paths.
- `scripts/install/lib/preflight.sh:316–318` — *source evidence*. The
  installer iterates the required machine-state files
  `credentials network openclaw github current_context` — `openclaw` is
  one of the mandatory machine state files at preflight time.
- `scripts/install/lib/skills.sh:100–156` — *source evidence*. Extended
  skill set includes `clawseat-koder`; the installer copies these into
  `~/.openclaw/skills/` only when that directory exists, which is
  already partially adapter-shaped but the skill list still defaults
  to `clawseat-koder` in the extended tier.
- `scripts/install/lib/project.sh:1229` — *source evidence*. Bootstrap
  brief expects `${PRIMARY_SEAT_ID}` to Read `openclaw / binding` files.
- `README.md:3–86, 231, 330, 350` — *source evidence*. Tagline reads
  "OpenClaw × gstack × tmux"; the role table describes memory / planner /
  builder / reviewer / patrol / designer seats as "OpenClaw … agent" by
  default. Listed here because the README is the install entry point —
  it is consumed by the install agent and shapes operator expectations.
  (See also `stale-doc` for the prose-level work.)

### optional-adapter

These are capabilities that should remain — but behind an explicit feature
flag, install opt-in, or adapter subtree. Most already have *graceful*
degradation paths; the gap is that they are still wired into default
install / runtime by convention rather than configuration.

- `scripts/apply-koder-overlay.sh` — *source evidence* lines 3–371. The
  destructive operator-side overlay that converts an OpenClaw agent into
  the `koder` frontstage. Already opt-in (must be run explicitly), but
  lives in the canonical `scripts/` directory next to `install.sh` which
  reinforces the "default" framing.
- `scripts/clean-slate.sh` — *source evidence* lines 15–222. The cleanup
  utility already preserves `~/.lark-cli`, `~/.openclaw/agents`, and
  `~/.openclaw/openclaw.json` — i.e. it already treats OpenClaw state as
  external. Keep, but rename comments to "optional adapter state".
- `scripts/hooks/planner-stop-hook.sh`, `scripts/hooks/memory-stop-hook.sh`
  — *source evidence* `planner-stop-hook.sh:111–149`,
  `memory-stop-hook.sh:188–208`. Both hooks already skip when
  `lark-cli` is absent or `feishu_group_id` is empty. They are the
  textbook adapter pattern; the only change needed is to document the
  skip path and stop treating Feishu push as the default surface.
- `core/scripts/feishu_announcer.py` (runtime surface; file move is
  core-blocking, see above) — *source evidence* lines 1–262. As a daemon
  it is only on when invoked; should live under an `optional-adapter/`
  subtree so a non-OpenClaw install can clearly skip it.
- `core/scripts/heartbeat_beacon.sh` — *source evidence* lines 3, 16–39.
  Standalone sender that pipes `[HEARTBEAT_TICK]` to `lark-cli`. Make
  install conditional: only seed the launchd plist if Feishu enabled.
- `core/skills/clawseat-koder/` — *source evidence* `SKILL.md` plus the
  whole tree. The koder bridge skill (translates decision payloads,
  routes Feishu replies). Needed only when the koder overlay is applied.
- `core/skills/lark-shared/`, `core/skills/lark-im/` — *source evidence*
  `lark-shared/SKILL.md:2–85`, `lark-im/SKILL.md` + 12 reference files.
  CLI helper skills. Should be installed only when Feishu is enabled.
- `core/skills/clawseat-install/scripts/configure_koder_feishu.py`,
  `init_koder.py`, `find_feishu_group_ids.py`,
  `prune_koder_todo_history.py` — *source evidence* their module
  docstrings. Operator-driven installer helpers that only fire on the
  koder-overlay path.
- `core/skills/gstack-harness/scripts/_feishu.py`,
  `core/skills/gstack-harness/scripts/send_delegation_report.py` —
  *source evidence* both files. Delegation-report Feishu sender used
  by completed-task announcers. Already side-effect free unless invoked.
- `core/skills/gstack-harness/references/feishu-delegation-report.md`,
  `core/skills/clawseat-install/references/feishu-bridge-setup.md`,
  `core/skills/clawseat-install/references/feishu-group-no-mention.md`
  — *source evidence* their file titles. Reference docs that describe
  the adapter's wire format and setup. Keep, but move into an
  `optional-adapter/references/` namespace so they do not appear in the
  default "how to set up ClawSeat" reading path.
- `core/references/feishu-message-marker.md` — *source evidence*
  lines 1–102. Operational reference doc for Feishu message markers.
  Reframe as adapter doc.
- `core/templates/koder-workspace-tools/` — *source evidence* all 12
  template files under this subtree (`dispatch.md.tmpl:12–88`,
  `index.md.tmpl:1–17`, `seat.md.tmpl:9–238`, `project.md.tmpl:9–74`).
  The whole subtree is the koder workspace overlay template; it is
  read only by `init_koder.py`. Move alongside that script under
  the adapter subtree.
- `templates/clawseat-solo.toml:45` — *source evidence*. Includes
  `clawseat-koder/SKILL.md` in the memory seat's default skill list.
  Should be a conditional include (e.g. template parameter).
- `templates/clawseat-engineering.toml`, `templates/clawseat-creative.toml`
  — *source evidence* their existence next to `clawseat-solo.toml`.
  Profile templates whose default skill lists pull in optional-adapter
  skills. Same treatment as solo.
- `core/adapter/_adapter_exec.py`, `core/adapter/_adapter_types.py`,
  `core/adapter/clawseat_adapter.py` — *source evidence*
  `_adapter_exec.py:102–234`, `_adapter_types.py:66`,
  `clawseat_adapter.py:591–605`. The escalation adapter uses
  `koder_default_action` and `resolved_by ∈ {koder, user}` as part of
  its payload contract. This is already the right shape (adapter file
  in `core/adapter/`), but the koder vocabulary should become
  `frontstage_default_action` / `{frontstage, user}` so the contract
  generalises beyond koder.
- `core/launchers/README.md:78` — *source evidence*. Documented
  favourites list includes `~/coding/openclaw`. Optional convenience.
- `docs/auth-modes.md`, `docs/GSTACK.md`, `docs/HACKING.md`,
  `docs/INSTALL.md`, `docs/INSTALL.zh-CN.md`,
  `docs/ITERM_TMUX_REFERENCE.md`,
  `docs/schemas/v0.4-layered-model.md`,
  `docs/schemas/memory-bootstrap-brief.md` — *source evidence* each
  file's section that references Feishu / Koder / lark-cli as optional
  install steps. These already use "optional" / "if Feishu enabled"
  framing; they should add a top-level "ClawSeat without OpenClaw"
  table-of-contents so the optional path is the first one a reader
  sees.

### stale-doc

These docs describe OpenClaw / Koder / Feishu as the *default* runtime,
not as adapters. They are not historical archives — they are still on the
main reading path — but their framing predates the decoupling direction
and needs reword. Rewriting them is safe (no code path depends on the
prose), but it has to happen explicitly because operators read these
first.

- `README.md:3–86, 231, 330, 350` — *source evidence*. Top-of-tree tagline,
  role table, "left column = OpenClaw, right column = ClawSeat" framing,
  and "OpenClaw × gstack × tmux" subtitle. Rewrite once the optional
  adapter surfaces are renamed so the README can describe ClawSeat as a
  standalone team-orchestration layer with OpenClaw as one of several
  optional channels.
- `docs/OPENCLAW.md:1–54` — *source evidence*. Opens with "ClawSeat 不是
  一个独立 agent 框架. 它是 OpenClaw 的本地研发前台". That sentence is the
  inverse of the operator-approved direction. Rewrite top section to
  describe OpenClaw as one optional channel; keep the rest as adapter
  reference.
- `docs/ARCHITECTURE.md:18–106` — *source evidence*. Mental model section
  already concedes "koder is an optional reverse channel" but earlier
  paragraphs assume Feishu is always present. Reword the mental model
  to lead with the CLI-only / file-only path; demote Feishu to the
  adapter half.
- `docs/CANONICAL-FLOW.md:6–200` — *source evidence*. Canonical-flow
  doc threads OC_DELEGATION_REPORT_V1, Feishu bridge binding, and
  project-Feishu bind sections through the canonical narrative. Keep
  the protocols documented, but explicitly fence each subsection with
  "applies only when Feishu / koder enabled" callouts and update the
  TOC.
- `docs/INSTALL.md:23–649`, `docs/INSTALL.zh-CN.md:22–470` — *source
  evidence*. Install docs already call phase 4 "optional", but the
  surrounding text assumes Feishu / OpenClaw machine state. Add a
  "Minimum install (no OpenClaw, no Feishu)" path at the top.
- `core/references/skill-catalog.md:18–86` — *source evidence*. Skill
  catalog rows describe core seats as "OpenClaw … agent" by default.
  Reword once optional adapters are physically separated.
- `docs/rfc/RFC-002-architecture-v2.1.md`,
  `docs/rfc/V2-VOCAB-DRIFT-AUDIT.md`,
  `docs/rfc/MULTI_TEAM_MINIMAL_DESIGN.md`,
  `docs/rfc/AUDIT-2026-05-12-CODE-QUALITY.md`,
  `docs/rfc/M1-issues-backlog.md`,
  `docs/rfc/TEST-SUITE-AUDIT-2026-05-14.md` — *source evidence*. These
  are RFC archives. They mention koder / openclaw / feishu freely.
  Leave the historical text **as-is** (do not rewrite history), but
  add a one-line "historical" banner so the file does not look like
  active guidance.
- `templates/README.md:2` — *source evidence*. References deprecated
  `clawseat-creative` template — mentions koder in the migration note.
  Tighten wording but do not rewrite history.

### test-fixture

Tests reference the four tokens for one of three reasons: (1) they
directly exercise a koder / feishu / openclaw / lark code path; (2) they
use the strings only as fixture identifiers (e.g. seat-id "koder"); or
(3) they ratchet behavior that the adapter is allowed to skip when
disabled. None of these block ClawSeat-without-OpenClaw at runtime,
but moving the underlying adapter code will cause them to fail their
import paths, so they must move (or be skipped under a feature flag)
in lockstep with each slice.

Representative inventory of the 141 matching tests under `tests/`:

- Direct adapter coverage — must move with the adapter:
  - `tests/test_scan_openclaw.py`,
    `tests/test_openclaw_migrated_skills_registered.py`,
    `tests/test_openclaw_koder_workspace.py`,
    `tests/test_apply_koder_overlay.py`,
    `tests/test_configure_koder_feishu.py`,
    `tests/test_init_koder_tool_templates.py`,
    `tests/test_init_koder_hardcodes.py`,
    `tests/test_install_mirror_openclaw_skills.py`,
    `tests/test_prune_koder_todo_history.py`,
    `tests/test_complete_handoff_koder_guard.py`,
    `tests/test_memory_reference_openclaw_install_protocol.py`,
    `tests/test_koder_skill_has_routing_quick_reference.py`,
    `tests/test_koder_simplify_split.py`,
    `tests/test_koder_overlay_l2_hint.py`,
    `tests/test_koder_hygiene_bundle.py`,
    `tests/test_koder_bind_group_id.py`,
    `tests/test_feishu_group_resolution_strict.py`,
    `tests/test_feishu_enabled_switch.py`,
    `tests/test_feishu_auth_keepalive.py`,
    `tests/test_feishu_announcer.py`,
    `tests/test_memory_stop_hook_feishu_push_marker.py`,
    `tests/test_lark_cli_wrapper.py`,
    `tests/test_launcher_lark_cli_seed.py`,
    `tests/test_ancestor_skill_larkcli_diagnostic_gate.py`,
    `tests/test_ancestor_skill_lark_cli_cheat_sheet.py`,
    `tests/test_ancestor_skill_feishu_two_layers.py`,
    `tests/test_apply_koder_overlay.py` (lines 10, 65, 95–187: literal
    fixture paths under `~/.openclaw/workspace-*`, koder bind runner
    arg check) — *source evidence*.
- Test-fixture only (string used as seat-id / project name); safe to
  rename when the underlying alias map changes:
  - `tests/conftest.py`, `tests/test_dispatch_*.py`,
    `tests/test_complete_handoff*.py`,
    `tests/test_planner_announce.py`,
    `tests/test_planner_stop_hook.py`,
    `tests/test_patrol_stop_hook.py`,
    `tests/test_announce_planner_event_failure.py`,
    `tests/test_send_and_verify*.py`,
    `tests/test_send_delegation_report_identity.py`,
    `tests/test_correlation_id_plumbing.py`,
    `tests/test_status_md_dispatch_log.py`,
    `tests/test_task_create_status_template.py`,
    `tests/test_state_db.py`,
    `tests/test_smoke_coverage.py`,
    `tests/test_seat_resolver*.py`,
    `tests/test_transport_router.py`,
    `tests/test_modal_detector.py`,
    `tests/test_token_watermark.py`,
    `tests/test_window_open_grid.py`,
    `tests/test_monitor_layout_n_panes.py`, plus ~50 more under
    `tests/test_ancestor_*`, `tests/test_workspace_*`,
    `tests/test_profile_*`, `tests/test_install_*`. These need a
    light rename pass once the canonical seat name is no longer
    `koder` by default — not blocking, but mandatory before deletion.
- Behavioural guards on optional-adapter behavior:
  - `tests/test_install_isolation.py`,
    `tests/test_install_flow_phases.py`,
    `tests/test_install_lazy_panes.py`,
    `tests/test_install_provider_noninteractive.py`,
    `tests/test_machine_config.py`,
    `tests/test_real_user_home_resolution.py`,
    `tests/test_runtime_home_links.py`. These tests bake assumptions
    about `~/.openclaw/`, `~/.lark-cli` paths being present at install
    time. They should grow a "without OpenClaw" variant before any
    install flag flips.

Full file list is reproduced by:

```sh
rg -l "OpenClaw|openclaw|Koder|koder|Feishu|feishu|Lark|lark" tests | sort
```

## First Safe Slices

The five proposed follow-up tasks are each scoped so they do not delete
adapter capability, do not push to remote, and do not touch `main`. Each
is owned by `cartooner-front` planner+builder unit unless escalated.

### Slice S1 — Gate `openclaw_frontstage_agent` behind a profile feature flag

**What to change.** In `core/lib/profile_validator.py` (lines 202–238)
make the `openclaw_frontstage_agent` field optional whenever
`openclaw_tenants` is empty or a new `[features] openclaw = false` flag
is set. Keep the strict path for projects that opt in. Also widen
`_NUMBERED_SEAT_RE` (line 48) to accept `frontstage` (or any
project-declared frontstage seat name) so projects that disable koder
can still pass validation.

**Why it is safe.** Validator-only change. Existing OpenClaw projects
continue to pass under the same rule (the flag defaults to "preserve
current behavior" until decoupling slices flip it). No deletion of
adapter capability.

**What to leave alone.** Do not touch `do_koder_bind` /
`KoderBindError` / `cmd_project_koder_bind` in
`core/scripts/agent_admin_layered.py` (lines 123–355) — keep the koder
overlay path. Do not delete `openclaw_frontstage_agent` field.

**Suggested owner.** `cartooner-front` planner + builder, ClawSeat scope
only. Reviewer escalation only if regression test surface expands.

### Slice S2 — Make `feishu_group_id` / `feishu_*` heartbeat fields tolerant of empty values

**What to change.** In `core/scripts/heartbeat_config.py` (lines 178–280)
allow validation to pass when `feishu_group_id` is empty, with the
heartbeat downgrading to a CLI-only echo / file-only sink. In
`core/lib/state.py` (lines 67–68, 120–121) the columns already default
to `''`; ensure consumers (`list_unsent_feishu_events`,
`mark_feishu_sent`, `feishu_announcer.py`) all no-op when no group is
configured.

**Why it is safe.** All the columns already have empty defaults; this
slice closes the loop on the validators / announcers that error today.
No schema migration is required.

**What to leave alone.** Do not delete the Feishu announcer
(`core/scripts/feishu_announcer.py`) or the wire format. Do not change
the state.db schema.

**Suggested owner.** `cartooner-front` builder; planner self-reviews.

### Slice S3 — Hide the `project koder-bind` / Feishu CLI surface behind `--feature openclaw`

**What to change.** In `core/scripts/agent_admin_parser.py` (lines 78,
282–401), wrap the `project koder-bind` subparser and the
`--feishu-group` / `--feishu-sender-app-id` / `--openclaw-koder-agent` /
`--feishu-bot-account` flags so they only register when an environment
variable or profile flag opts in (e.g. `CLAWSEAT_OPENCLAW=1`). Default
help output for a vanilla install no longer surfaces them.

**Why it is safe.** Pure CLI surface change. The underlying handlers
in `agent_admin_layered.py` remain available; the flag merely controls
parser visibility. Existing operator scripts that pass the flag still
work.

**What to leave alone.** Keep `do_koder_bind`, `KoderBindError`,
`cmd_project_koder_bind`, and all CRUD-validation wiring (`core/scripts/agent_admin_crud_*.py`).

**Suggested owner.** `cartooner-front` builder.

### Slice S4 — Doc reframe: "ClawSeat without OpenClaw" lede in `README.md`, `docs/OPENCLAW.md`, `docs/ARCHITECTURE.md`, `docs/INSTALL.md`, `docs/INSTALL.zh-CN.md`, `docs/CANONICAL-FLOW.md`

**What to change.** Reword the top sections of those six docs so the
default install path is described first (CLI-only, file-only delivery,
review/latest validation, opt-in remote). Move OpenClaw / Feishu /
lark-cli framing into an "Optional adapters" sub-section in each doc.
Update `core/references/skill-catalog.md` skill rows and
`core/references/feishu-message-marker.md` framing to match.

**Why it is safe.** Docs-only. No source paths change. RFC archives in
`docs/rfc/` get a one-line "historical" banner but no rewrites.

**What to leave alone.** Do not rewrite `docs/rfc/*` historical text.
Do not delete `docs/OPENCLAW.md` — it remains the canonical OpenClaw
adapter reference.

**Suggested owner.** `cartooner-front` planner (docs ownership).

### Slice S5 — Physical move of optional adapters into `core/optional-adapters/`

**What to change.** Move (with `git mv`) the following trees under a
new `core/optional-adapters/` namespace:

- `core/skills/clawseat-koder/`,
- `core/skills/lark-shared/`, `core/skills/lark-im/`,
- `core/skills/clawseat-install/scripts/{init_koder.py, configure_koder_feishu.py, find_feishu_group_ids.py, prune_koder_todo_history.py}`,
- `core/templates/koder-workspace-tools/`,
- `core/scripts/feishu_announcer.py`,
- `core/scripts/heartbeat_beacon.sh`,
- `core/skills/gstack-harness/scripts/_feishu.py`,
- `core/skills/gstack-harness/scripts/send_delegation_report.py`,
- the matching references under `core/references/feishu-message-marker.md`
  and `core/skills/clawseat-install/references/feishu-*.md`.

Update import paths and template lookups in the existing callers; keep
behavior identical. Update the matching tests under `tests/` (the
"Direct adapter coverage" sub-list above) to follow the moved paths.

**Why it is safe.** Pure structural move. No deletion. After this slice
a non-OpenClaw install can simply skip the `core/optional-adapters/`
directory at install time (handled in Slice S3 + a follow-up install
slice). Existing OpenClaw projects continue working because every
move is a `git mv` with path-fix in callers.

**What to leave alone.** Do not delete any adapter code. Do not touch
`core/lib/state.py` schema columns (Slice S2 handles validators, not
moves). Do not change `docs/OPENCLAW.md` content here — that is Slice S4.

**Suggested owner.** `cartooner-front` builder + planner; reviewer
escalation recommended because the import-path surface area is wide.

## Risks and Non-Goals

This slice (cf029) explicitly **does not**:

- delete OpenClaw, Koder, Feishu, or Lark adapter capability;
- modify product runtime code anywhere — only the new mapping doc is
  added under `docs/architecture/`;
- modify any file in `/Users/ywf/coding/cartooner` outside
  `apps/web/electron/vendor/clawseat/`;
- push, open a pull request, or trigger CI for either repo;
- touch `main` in either repo (the commit lands on a local working
  branch in `/Users/ywf/coding/ClawSeat`);
- rename, move, or refactor any of the files cited above.

Known risks for follow-up slices:

- **state.db schema dependency.** Several `feishu_*` columns are part of
  the canonical schema and the events bus; any structural decoupling
  must keep the columns (Slice S2) so downstream installations that
  still use Feishu continue to migrate cleanly.
- **profile_validator regex.** Slice S1 must not relax the seat-name
  regex so loosely that arbitrary names pass — that would silently
  break dispatch routing.
- **CLI flag visibility.** Slice S3 hides flags by default; CI fixtures
  that pass `--openclaw-koder-agent` need to set `CLAWSEAT_OPENCLAW=1`
  or be marked as adapter tests.
- **Test path moves.** Slice S5 moves adapter tests in lockstep with
  their adapter code; running the full suite on each move is mandatory.
- **Operator workflow continuity.** `scripts/apply-koder-overlay.sh` and
  its companions remain reachable; the decoupling does not change the
  Feishu reverse-channel flow for projects that need it.

## Appendix: Provenance

The classification and source-evidence references above were generated
from the live ClawSeat tree at `/Users/ywf/coding/ClawSeat` on
2026-05-18, branch `feat/cf029-clawseat-openclaw-decoupling-map`. The
raw rg dump that backs every `path:line` citation is reproducible by
running the canonical evidence command at the top of this document.
