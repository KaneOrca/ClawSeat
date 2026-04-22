task_id: INST-RESEARCH-022
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 12 candidates audited; 1 is SAFE_TO_DELETE, 6 require test cleanup before deletion, 4 are KEEP, 1 is KEEP_BUT_DORMANT.

## Summary table

| # | Path | Verdict | Blast radius |
|---|------|---------|--------------|
| 1 | core/migration/ | KEEP | 5 tests + transport_router crash |
| 2 | core/tui/ | KEEP_BUT_DORMANT | ancestor_brief live; machine_view dormant but entangled |
| 3 | core/adapter/ + adapters/ | KEEP | Both active in openclaw-plugin; 4 tests |
| 4 | core/engine/ | KEEP | Seat materialization; 2 tests + openclaw-plugin runtime |
| 5 | core/skills/agent-monitor/ | **SAFE_TO_DELETE** | Zero dependencies; symlink to canonical |
| 6 | core/skills/socratic-requirements/ | KEEP | Active intake skill; 3 skill references + routing |
| 7 | core/skills/workflow-architect/ | KEEP_BUT_DORMANT | Registered; zero runtime call sites |
| 8 | core/skills/lark-im/ + lark-shared/ | KEEP | Registered in skill_registry.toml + 2 templates |
| 9 | core/skills/clawseat-koder-frontstage/ | DELETE_WITH_TEST_CLEANUP | 2 text-assertion tests; zero Python imports |
| 10 | shells/codex-bundle/ + claude-bundle/ + openclaw_plugin/ | KEEP | Active runtime entrypoints; 2 tests |
| 11 | examples/arena-pretext-ui/ + examples/starter/profiles/legacy/ | DELETE_WITH_TEST_CLEANUP | 1 portability test; manifest.toml entry |
| 12 | design/ + docs/design/ + docs/install/ + docs/review/ + PACKAGING.md + TEAM-INSTANTIATION-PLAN.md | DELETE_WITH_TEST_CLEANUP | 1 test_ancestor_brief assertion; docs refs |

## Detailed reports

### Candidate 1 — core/migration/

**What it is**: Dynamic-roster siblings for dispatch/notify/handoff/render-console, active runtime entry points routed through `transport_router.py`.

**Size**: 5 files, ~1290 lines

**Static references**:
- `core/transport/transport_router.py:35-47` — routes dynamic-roster calls to `*_dynamic.py` files at import time
- `core/transport/transport_router.py:30` — defines `MIGRATION_ROOT`
- `core/adapter/clawseat_adapter.py:48,671,697` — imports `dynamic_common.py` helpers
- `core/skills/gstack-harness/scripts/notify_seat.py:61` — fork comment referencing `notify_seat_dynamic.py`
- `core/skills/gstack-harness/scripts/_task_io.py:54` — anti-drift comment referencing `notify_seat_dynamic.py`
- `docs/ARCHITECTURE.md:83-84,177,189` — documented as active layer with anti-drift test
- `docs/PACKAGING.md:55` — listed in packaging docs

**Runtime call sites**:
- Entry via `core/transport/transport_router.py:35-47` — dynamically loaded when handling dispatch/notify/complete/render-console for dynamic-roster profiles
- Entry via `core/adapter/clawseat_adapter.py:671,697` — imports helpers from `dynamic_common.py` at runtime

**Test dependencies**:
- `tests/test_transport_router.py` — anti-drift test enforces no fork from `dynamic_common.py`
- `tests/test_memory_target_guard.py` — loads `dispatch_task_dynamic.py` and `notify_seat_dynamic.py` via `_load_module` to test guard behavior
- `tests/test_dispatcher_role_routing.py` — directly references `dispatch_task_dynamic.py` and `complete_handoff_dynamic.py`
- `tests/test_cs_init_openclaw_profile_guard.py` — imports `dynamic_common` from `core/migration/dynamic_common.py`
- `tests/test_smoke_coverage.py:309-312` — lists all 5 `*_dynamic.py` files as covered entry points

**Estimated blast-radius if deleted**:
- tests that would fail: 5
- scripts that would crash at import: 2 (`transport_router.py`, `clawseat_adapter.py`)
- skills that would have broken references: 2 (comments only)

**Verdict**: KEEP

**Reason**: Actively routed as runtime entry points via `transport_router.py` for dynamic-roster profiles; deleting would crash `transport_router.py` and `clawseat_adapter.py` and break 5 tests.

---

### Candidate 2 — core/tui/

**What it is**: TUI utilities for ClawSeat install-time machine profiling (ancestor_brief) and live system view (machine_view).

**Size**: 3 files, 676 lines (`__init__.py` 6L, `ancestor_brief.py` 398L, `machine_view.py` 272L)

**Static references**:
- `core/launchers/agent-launcher.sh:1286` — `python3 -m core.tui.ancestor_brief --project "$_preflight_project"` (runtime call at install)
- `core/skills/clawseat-ancestor/SKILL.md:134` — references `core/tui/ancestor_brief.write_brief(...)`
- `docs/schemas/ancestor-bootstrap-brief.md:6,41` — documents `core/tui/ancestor_brief.py` as producer
- `tests/test_ancestor_brief.py:26` — `from core.tui import ancestor_brief` (50+ usage lines)
- `machine_view.py` — no external imports; only self-referential CLI docstring examples

**Runtime call sites**:
- Entry via `core/launchers/agent-launcher.sh:1286` — called during ancestor agent preflight
- Entry via `python3 -m core.tui.ancestor_brief` (CLI module)
- `machine_view.py` — no runtime call sites found; appears dormant

**Test dependencies**:
- `tests/test_ancestor_brief.py` — comprehensive test suite (418 lines) covering `load_context_from_profile`, `render_brief`, `write_brief`, `main`, constants, and edge cases
- `machine_view.py` — no test coverage found

**Estimated blast-radius if deleted**:
- tests that would fail: 1 (`tests/test_ancestor_brief.py` — entire file, ~418 lines)
- scripts that would crash at import: 1 (`core/launchers/agent-launcher.sh` at line 1286, preflight step)
- skills that would have broken references: 1 (`core/skills/clawseat-ancestor/SKILL.md` step 7)
- docs that would have broken references: `docs/schemas/ancestor-bootstrap-brief.md` (producer label)

**Verdict**: KEEP_BUT_DORMANT

**Reason**: `ancestor_brief.py` is live (launcher + skill + tests), but `machine_view.py` has zero external references and `__init__.py` is trivial. The module as a whole cannot be deleted without breaking the preflight flow and test suite.

---

### Candidate 3 — core/adapter/ + adapters/

**What it is**: Two distinct adapter layers -- `core/adapter/` (project/seat lifecycle) and `adapters/` (harness/tmux session management) -- both actively wired into `shells/openclaw-plugin/`.

**Size**: core/adapter: 4 files, ~1151 lines; adapters/: 2 tracked files (~691 lines + placeholder README); total ~1842 lines

**Static references**:
- `shells/openclaw-plugin/_bridge_adapters.py:44` — loads `TmuxCliAdapter` via importlib from `adapters/harness/tmux-cli/adapter.py`
- `shells/openclaw-plugin/_bridge_adapters.py:17` — imports `ClawseatAdapter` from `core.adapter.clawseat_adapter`
- `shells/openclaw-plugin/_bridge_seats.py:14` — imports `ClawseatAdapter` + `init_tmux_adapter`
- `shells/openclaw-plugin/openclaw_bridge.py:57` — imports `ClawseatAdapter` + `init_tmux_adapter`
- `shells/_shim_base.py:60` — loads `TmuxCliAdapter` via `adapters/harness/tmux-cli/adapter.py`
- `core/preflight.py:283,285` — references both adapter paths
- `.github/workflows/ci.yml:61` — py_compile check on `core/adapter/clawseat_adapter.py`

**Runtime call sites**:
- Entry via `shells/openclaw-plugin/openclaw_bridge.py` — dispatches seat operations via `ClawseatAdapter` and session management via `TmuxCliAdapter`
- Entry via `shells/openclaw-plugin/openclaw_bootstrap.py` — initializes both adapters on startup
- Entry via `shells/openclaw-plugin/_bridge_adapters.py:54` — `init_tmux_adapter()` lazy-loads and returns `TmuxCliAdapter` instance
- Entry via `shells/_shim_base.py:71` — `create_adapter()` returns `TmuxCliAdapter` for shell bundles

**Relationship between core/adapter/ and adapters/**: Completely unrelated codebases; no mutual imports. `core/adapter/clawseat_adapter.py` is the **project/seat orchestration layer**. `adapters/harness/tmux-cli/adapter.py` is the **harness execution layer**. Both are composed inside `shells/openclaw-plugin/` -- the orchestrator calls the session manager.

**Test dependencies**:
- `tests/test_clawseat_adapter.py` — directly tests `ClawseatAdapter`, `AdapterResult`, `PendingProjectOperation`
- `tests/test_round2_bugs.py:32,64,231,259` — imports `ClawseatAdapter`, `AdapterResult`, `PendingProjectOperation`, and `core.adapter._adapter_types`
- `tests/test_polish_batch.py:69,89,155-168` — tests `tmux-cli` adapter module path, `TmuxCliAdapter` class exposure, and smoke test
- `tests/test_hardening_batch.py:251,264` — tests `_get_tmux_adapter_module` lazy-load lock

**Estimated blast-radius if deleted**:
- tests that would fail: 4
- scripts that would crash at import: 2 (`shells/openclaw-plugin/`, `shells/_shim_base.py`)
- skills that would have broken references: 2 (stale doc references)
- CI would fail: `.github/workflows/ci.yml` py_compile step

**Verdict**: KEEP

**Reason**: Both directories are actively composed in `shells/openclaw-plugin/`; deleting either breaks the runtime and 4 tests. `adapters/projects/openclaw/` is the only dormant piece (placeholder README).

---

### Candidate 4 — core/engine/

**What it is**: Seat materialization engine — generates workspace + symlinks + session records + tmux config for multi-seat control plane.

**Size**: 1 Python file, 808 lines (+ `__pycache__`)

**Static references**:
- `manifest.toml:10` — listed as a core module in ClawSeat packaging manifest
- `docs/PACKAGING.md:53` — listed in packaging docs
- `docs/ARCHITECTURE.md:86` — describes purpose: seat materialization
- `shells/openclaw-plugin/_bridge_seats.py:244,259` — calls `clawseat_adapter.instantiate_seat()` which delegates to this engine
- `shells/openclaw-plugin/openclaw_bridge.py:98,377` — imports `instantiate_seat` from adapter, exposes it as a bridge action
- `shells/openclaw-plugin/_bridge_adapters.py:133,143` — references `refac/engine/instantiate_seat.py` path
- `core/adapter/clawseat_adapter.py:63,189` — stores path `core/engine/instantiate_seat.py` and delegates to it
- `tests/test_launch_permissions.py:12,254,281,282` — imports `instantiate_seat`, tests `render_session_record`, `render_tmux_config`
- `tests/test_round2_bugs.py:95,116,135` — imports `create_repo_symlink` from `instantiate_seat`
- `core/skills/clawseat-koder-frontstage/SKILL.md:254` — skill action schema references `adapter.instantiate_seat()`

**Runtime call sites**:
- Entry via `shells/openclaw-plugin/_bridge_seats.py` — openclaw plugin bridge dispatches `instantiate_seat` to `clawseat_adapter`
- Entry via `shells/openclaw-plugin/openclaw_bridge.py` — exposes `instantiate_seat` as a top-level bridge action
- Entry via `core/adapter/clawseat_adapter.py:189` — the adapter's `instantiate_seat()` method invokes the engine script

**Test dependencies**:
- `tests/test_launch_permissions.py` — directly imports `instantiate_seat` module; tests session record and tmux config rendering
- `tests/test_round2_bugs.py` — imports `create_repo_symlink` from `instantiate_seat` (3 call sites)

**Estimated blast-radius if deleted**:
- tests that would fail: 2
- scripts that would crash at import: 2
- skills that would have broken references: 1
- packaging/manifest would be inconsistent

**Verdict**: KEEP

**Reason**: Core seat materialization engine actively invoked by the OpenClaw bridge plugin, the adapter layer, and covered by tests — not dormant.

---

### Candidate 5 — core/skills/agent-monitor/

**What it is**: Skill for observing, contacting, and unblocking ClawSeat tmux seats via tmux send and macOS GUI automation scripts.

**Size**: 7 files, ~540 lines

**Static references**:
- `core/skills/gstack-harness/SKILL.md:52` — soft reference to `agent-monitor` skill for takeover patterns (cosmetic documentation reference, not a functional import)
- `core/skills/agent-monitor/references/tmux-takeover-patterns.md:5,87` — self-references within the candidate
- All other grep hits point to `core/shell-scripts/send-and-verify.sh` (the canonical location, not this skill's symlink)

**Runtime call sites**: None found. The skill's `send-and-verify.sh` is a **symlink** to `core/shell-scripts/send-and-verify.sh` (6846 bytes real file). All runtime callers reference the real file, not this symlink. Other scripts (`msg_focus.sh`, `msg_paste.sh`, `msg_send.sh`, `screenshot-to-feishu.sh`, `tmux-send-delayed.sh`) are self-contained utilities invoked only from within the SKILL.md documented workflows; no external callers found.

**Test dependencies**: None — all tests reference `core/shell-scripts/send-and-verify.sh` directly, not this skill's path.

**Estimated blast-radius if deleted**:
- tests that would fail: 0
- scripts that would crash at import: 0
- skills that would have broken references: 1 (`gstack-harness/SKILL.md` soft-reference, cosmetic only)
- `tmux-takeover-patterns.md` reference doc would be gone (low-value loss)

**Verdict**: SAFE_TO_DELETE

**Reason**: Entirely self-contained; its sole symlink targets the canonical file in `core/shell-scripts/`; none of its scripts are imported or called by any runtime component, test, or adapter outside of itself. Only a documentation cross-reference in `gstack-harness/SKILL.md` would be broken.

---

### Candidate 6 — core/skills/socratic-requirements/

**What it is**: koder intake skill for Socratic requirements elicitation (creative capability-catalog flow + engineering diagnostic flow).

**Size**: 2 files, 730 lines

**Static references**:
- `core/skill_registry.toml:49-52` — registered as a named skill, required=false, roles=["frontstage-supervisor", "planner-dispatcher"]
- `core/skills/workflow-architect/SKILL.md:6,16,23,49,123` — documents dependency on `socratic-requirements` for `summary_contract` brief
- `core/skills/clawseat-koder-frontstage/SKILL.md:39` — explicitly calls `socratic-requirements` step during new-project spawn
- `core/skills/clawseat-install/scripts/init_koder.py:260,275,294,933` — documents routing rule "creative → socratic-requirements catalog flow"
- `core/templates/gstack-harness/template.toml:40,49,84` — referenced as a bundled skill in harness template
- `scripts/clean-slate.sh:16,20,74,79` — listed in CLAWSEAT_OVERLAY_SKILLS and CLAWSEAT_ENTRY_SKILLS arrays

**Runtime call sites**:
- Entry via `clawseat-koder-frontstage/SKILL.md` (line 39) — koder dispatches to socratic-requirements for intake when intent is creative
- Entry via `clawseat-install/scripts/init_koder.py` (line 275) — intake routing logic routes creative requests to socratic-requirements catalog flow
- Consumed by `workflow-architect` as downstream consumer of `summary_contract` output format

**Test dependencies**: None found (grep for `socratic-requirements` across `**/test*.py` returned no hits).

**Estimated blast-radius if deleted**:
- tests that would fail: 0
- scripts that would crash at import: 0
- skills that would have broken references: 3 (workflow-architect, clawseat-koder-frontstage, clawseat-install)
- skill_registry.toml: entry would become dangling
- gstack-harness template: 2 broken references
- clean-slate.sh: script arrays would reference nonexistent skill

**Verdict**: KEEP

**Reason**: Actively referenced as a named intake skill in skill_registry.toml and multiple SKILL.md files; core routing logic in init_koder.py routes creative requests to it; downstream workflow-architect depends on its `summary_contract` output format.

---

### Candidate 7 — core/skills/workflow-architect/

**What it is**: Planner专属skill，接收结构化brief并映射到原子能力（seat/skill/tool），输出可执行workflow spec YAML并dispatch给下游席位。

**Size**: 3 files, ~393 lines

**Static references**:
- `core/skill_registry.toml:57` — skill registration with path
- `core/skills/socratic-requirements/SKILL.md:39,44` — capability-catalog routing logic references `workflow-architect`
- `core/skills/socratic-requirements/references/capability-catalog.yaml:482` — trigger signals for workflow-architect (multi-step / automation requests)
- `core/skills/workflow-architect/references/atomic-capabilities.md:21` — planner role lists "调用 workflow-architect"
- `core/skills/workflow-architect/references/workflow-spec-schema.md:3` — self-reference in doc header

**Runtime call sites**: none found — skill is registered in `skill_registry.toml` and referenced in `capability-catalog.yaml` triggers, but no active invocation found in scripts, tests, or other skill implementations.

**Test dependencies**: none — no test file imports or exercises `workflow-architect`.

**Estimated blast-radius if deleted**:
- tests that would fail: 0
- scripts that would crash at import: 0
- skills that would have broken references: `core/skill_registry.toml` dangling entry, `capability-catalog.yaml` would lose `workflow-architect:` trigger block, `socratic-requirements` routing logic would have dead references, `atomic-capabilities.md` planner doc would lose "调用 workflow-architect" line

**Verdict**: KEEP_BUT_DORMANT

**Reason**: Skill is fully defined, registered, and documented in routing logic, but has zero runtime call sites and no test coverage — appears designed but never wired into actual execution flow. Deleting would leave dangling references in registry + catalog.

---

### Candidate 8 — core/skills/lark-im/ + lark-shared/

**What it is**: Feishu/Lark IM skill (send/receive messages, manage group chats via lark-cli) + shared auth/config identity skill.

**Size**: lark-im: 14 files (1 SKILL.md + 13 reference .md); lark-shared: 1 SKILL.md; total ~2041 lines

**Static references**:
- `core/skill_registry.toml:73-86` — registers both `lark-shared` and `lark-im` as bundled skills with path, assigned to roles `planner-dispatcher`
- `core/templates/ancestor-engineer.toml:64-65,85-86` — hardcoded absolute paths in ancestor-engineer skills array
- `core/templates/gstack-harness/template.toml:85-86` — hardcoded absolute paths in gstack-harness skills array
- `scripts/clean-slate.sh:73,78` — comment listing `lark-im lark-shared` as bundled skills to install
- All other hits are internal self-references within the skill directories

**Runtime call sites**: none found — skills are loaded by the agent framework at boot via skill_registry.toml and template skill lists; no Python/JS code imports or invokes these.

**Test dependencies**: none — no test files reference lark-im or lark-shared.

**Estimated blast-radius if deleted**:
- tests that would fail: 0
- scripts that would crash at import: 0
- skill_registry.toml entries would point to non-existent files (would cause boot failures or skipped skills for `planner-dispatcher` role agents)
- ancestor-engineer and gstack-harness templates would have broken skill references

**Verdict**: KEEP

**Reason**: Both skills are registered in `skill_registry.toml` and referenced by absolute path in two agent templates; they are live configuration entries for the `planner-dispatcher` role, not dormant code.

---

### Candidate 9 — core/skills/clawseat-koder-frontstage/

**What it is**: Wrapper skill defining the protocol behavior for the user-facing `koder` frontstage seat -- reads PLANNER_BRIEF, handles disposition-driven routing, project switching, heartbeat reception, and Feishu delegation receipts.

**Size**: 2 files, 437 lines (SKILL.md 432 lines + agents/openai.yaml 5 lines)

**Static references**:
- `docs/PACKAGING.md:36` — listed in packaging manifest
- `docs/ARCHITECTURE.md:133,144,443` — architecture table entry and boundary rule; heartbeat flow step referencing koder-frontstage
- `docs/design/ancestor-responsibilities.md:153` — architect note referencing SKILL.md
- `core/skills/clawseat-install/scripts/init_koder.py:476` — table mentions `koder(frontstage)` template
- `core/skills/clawseat-install/scripts/init_specialist.py:219` — comment mentions koder/frontstage routing
- `core/scripts/agent_admin_session.py:324` — comment about skipping frontstage engineers
- `core/lib/bootstrap_completeness.py:22` — comment about koder frontstage skill
- `core/lib/bridge_preflight.py:5` — comment about koder/frontstage in OpenClaw mode
- `core/skills/gstack-harness/scripts/_common.py:676` — comment mentioning koder/frontstage
- `shells/openclaw-plugin/openclaw_bootstrap.py:79` — comment about koder frontstage skill after user config
- `tests/test_heartbeat.py:429,438` — two tests that read SKILL.md as text and assert on section presence
- `tests/test_monitor_layout_n_panes.py:380` — comment about koder/frontstage sessions (unrelated logic test)

**Runtime call sites**: None found. The skill has no Python imports from anywhere in the codebase. The `agents/openai.yaml` defines an OpenClaw agent interface (`allow_implicit_invocation: true`), but it is not invoked via code in this worktree. OpenClaw itself (upstream Node.js repo) is not present in this worktree.

**Test dependencies**:
- `tests/test_heartbeat.py::test_skill_md_has_heartbeat_section` — asserts SKILL.md contains "## Heartbeat reception" section
- `tests/test_heartbeat.py::test_skill_md_heartbeat_has_five_steps` — asserts heartbeat section contains 5 numbered steps

**Estimated blast-radius if deleted**:
- tests that would fail: 2 (both are text-assertion tests on SKILL.md content)
- scripts that would crash at import: 0
- skills that would have broken references: 0 (all references are comments or documentation)
- docs that would have broken cross-references: 2 (`docs/PACKAGING.md`, `docs/ARCHITECTURE.md`)

**Verdict**: DELETE_WITH_TEST_CLEANUP

**Reason**: Core product skill defining the koder frontstage protocol, but it has zero runtime Python imports and zero executable call sites in this worktree. The only tests that depend on it read the SKILL.md file as text and assert on section headings — these tests would need updating or removal before deletion.

---

### Candidate 10 — shells/codex-bundle/ + claude-bundle/ + openclaw_plugin/

**What it is**: Three ClawSeat distribution shells — `codex-bundle` (Codex CLI entry), `claude-bundle` (Claude Code entry), `openclaw_plugin` (symlink to `openclaw-plugin/` — OpenClaw plugin bundle with full bridge implementation).

**Size**: codex-bundle: 4 files, ~113 lines; claude-bundle: 4 files, ~182 lines; openclaw_plugin: symlink to openclaw-plugin (10 files, ~1550 lines); total ~1823 lines

**Static references**:
- `manifest.toml:21` — declares all three as `[modules]` entries; `manifest.toml:37` names `openclaw_bootstrap.py` as `bootstrap` entrypoint
- `shells/_shim_base.py:3-4` — docstring describes the deduplication history for these three bundles
- `tests/test_polish_batch.py:23,61,62,74,93,177,181,184,186` — tests shim behavior for all three bundles
- `tests/test_hardening_batch.py:255` — imports `shells.openclaw_plugin._bridge_adapters`
- `shells/openclaw-plugin/openclaw_bootstrap.py:45` — imports and calls `openclaw_bridge.bootstrap/init_tmux_adapter/list_team_sessions`
- `shells/openclaw-plugin/__init__.py:30` — imports `adapter_shim` at module load
- `core/skills/clawseat-install/references/interaction-mode.md:19` — docs mention bundle type names
- `docs/ARCHITECTURE.md:181,190` — architecture docs reference shell bundles

**Runtime call sites**:
- Entry via `manifest.toml` `bootstrap = "shells/openclaw-plugin/openclaw_bootstrap.py"` — the OpenClaw plugin bootstrap entrypoint
- `openclaw_bootstrap.py` imports and calls `openclaw_bridge` functions at runtime when OpenClaw initializes the plugin
- `openclaw-plugin/__init__.py` calls `adapter_shim.create_adapter()` at module import time (lines 29-55)

**Test dependencies**:
- `tests/test_polish_batch.py` — M1 dedup test: verifies all three shims delegate to `_shim_base.py` and report correct shell names, metadata, and surface asymmetries
- `tests/test_hardening_batch.py` — L8 test: imports `shells.openclaw_plugin._bridge_adapters` to verify thread lock usage

**Estimated blast-radius if deleted**:
- tests that would fail: 2
- scripts that would crash at import: 1 (`openclaw_bootstrap.py` entrypoint breaks; `openclaw-plugin/__init__.py` breaks)
- skills that would have broken references: `manifest.toml` module list would be invalid (3 declared shells gone)
- `shells/_shim_base.py` depends on these bundles for its existence

**Verdict**: KEEP

**Reason**: `openclaw_plugin` is a production entrypoint registered in `manifest.toml` with real runtime bridge code (bootstrap, seat ops, binding management). `codex-bundle` and `claude-bundle` are tested distribution shells. All three are referenced by tests and the manifest. Note: `openclaw_plugin/` is a symlink to `openclaw-plugin/` and is not empty.

---

### Candidate 11 — examples/arena-pretext-ui/ + examples/starter/profiles/legacy/

**What it is**: Legacy v0.3-era TOML profile templates; arena-pretext-ui is a bundled example profile for a specific project.

**Size**: arena-pretext-ui: 2 files (.gitkeep + profiles/arena-pretext-ui.toml), 56 lines; legacy profiles: 6 files (~372 lines); combined ~428 lines

**Static references**:
- `manifest.toml:26` — `"examples/arena-pretext-ui"` (bundled file list entry)
- `tests/test_portability.py:83` — `profile_path = _EXAMPLES / "arena-pretext-ui" / "profiles" / "arena-pretext-ui.toml"` (test reads this file)
- `docs/PACKAGING.md:84` — `examples/arena-pretext-ui/`
- `docs/ARCHITECTURE.md:104,170` — archived under `examples/starter/profiles/legacy/`
- `README.md:5,60,135,169` — disclaims it is not arena-pretext-ui, references legacy as migration reference
- `design/memory-seat-v3/SPEC.md:102`, `design/memory-seat-v3/M2-SPEC.md:51`, `core/skills/memory-oracle/scripts/_memory_schema.py:10` — `arena-pretext-ui` appears as an **example string value** for the `project` field in schema docs; not a file path reference
- `docs/schemas/v0.4-layered-model.md:266,389` — references `migrate_profile_to_v2.py` migration docs mentioning legacy profiles

**Runtime call sites**:
- Entry via `tests/test_portability.py:test_arena_profile_is_canonical_layout:83` — the test loads and parses `arena-pretext-ui.toml` at line 83-88, asserting its `tasks_root` and `workspace_root` fields use `~/.agents/` prefix. This is the only live runtime import.

**Test dependencies**:
- `tests/test_portability.py::test_arena_profile_is_canonical_layout` — reads `arena-pretext-ui/profiles/arena-pretext-ui.toml` via `tomllib` and asserts canonical path format; **would fail with FileNotFoundError** if the profile is deleted.

**Estimated blast-radius if deleted**:
- tests that would fail: 1 — `test_portability.py::test_arena_profile_is_canonical_layout` (FileNotFoundError)
- scripts that would crash at import: 0
- skills that would have broken references: 0 (memory-oracle uses "arena-pretext-ui" as a string literal example, not a file path)
- docs that would have dangling prose references: `docs/PACKAGING.md`, `docs/ARCHITECTURE.md`, `ClawSeat/README.md`, `docs/schemas/v0.4-layered-model.md`

**Verdict**: DELETE_WITH_TEST_CLEANUP

**Reason**: Only `test_arena_profile_is_canonical_layout` has a concrete runtime dependency on `arena-pretext-ui/profiles/arena-pretext-ui.toml`. The legacy profiles have zero live imports and are documented as archived fixtures. Deletion requires: (1) updating the portability test to skip or mock the profile, (2) removing the entry from `manifest.toml`, and (3) cleaning up prose references in docs.

---

### Candidate 12 — design/ + docs/design/ + docs/install/ + docs/review/ + PACKAGING.md + TEAM-INSTANTIATION-PLAN.md

**What it is**: Historical design artifacts (Phase 7 retrospective, ancestor responsibility matrix, packaging spec, team instantiation plan) from the ClawSeat project.

**Size**: design/: 3 files + memory-seat-v3/ subdir (2 SPEC files); docs/design/: 1 file; docs/install/: does not exist; docs/review/: does not exist; + PACKAGING.md (117 lines), TEAM-INSTANTIATION-PLAN.md (122 lines); total ~1519 lines

**Static references**:
- `core/tui/ancestor_brief.py:4,301` — docstring comment and hyperlink referencing `docs/design/ancestor-responsibilities.md` (runtime dependency)
- `core/templates/ancestor-engineer.toml:4,70` — comments citing `docs/design/ancestor-responsibilities.md` (must-match authority flags)
- `core/skills/clawseat-ancestor/SKILL.md:9` — `spec_documents` field lists `docs/design/ancestor-responsibilities.md`
- `README.md:198` — links to `docs/PACKAGING.md`
- `design/phase-7-retire.md:50,62,68` — self-references to `design/followups-after-m1.md`
- `tests/test_ancestor_brief.py:330` — asserts `docs/design/ancestor-responsibilities.md` appears in rendered output
- `tests/test_complete_handoff_koder_guard.py:5` — comment string referencing `design/followups-after-m1.md` (not functional)
- `core/launchers/agent-launcher.sh:1286` — calls `ancestor_brief.py` which embeds ancestor-responsibilities.md (runtime via ancestor_brief.py)

**Runtime call sites**:
- Entry via `agent-launcher.sh:1286` → `python3 -m core.tui.ancestor_brief` (Phase-A bootstrap for ancestor seat); `ancestor_brief.py` renders `ancestor-responsibilities.md` content into `ANCESTOR_BOOTSTRAP.md`
- `core/skills/clawseat-ancestor/SKILL.md` loaded by ancestor seat at boot; spec_documents field references `ancestor-responsibilities.md`

**Test dependencies**:
- `tests/test_ancestor_brief.py:330` — asserts rendered brief contains `docs/design/ancestor-responsibilities.md` hyperlink; if file deleted, this assertion fails
- `tests/test_complete_handoff_koder_guard.py` — uses `design/followups-after-m1.md` only in a comment, not a functional dependency

**Estimated blast-radius if deleted**:
- tests that would fail: 1 (`tests/test_ancestor_brief.py` — line 330 assertion)
- scripts that would crash at import: 0
- skills that would have broken references: 1 (`core/skills/clawseat-ancestor/SKILL.md` spec_documents field)
- `design/followups-after-m1.md` and `design/phase-7-retire.md`: zero code/test/runtime references outside their own content
- `docs/PACKAGING.md`: only README.md link; no runtime or test references
- `docs/TEAM-INSTANTIATION-PLAN.md`: no references found outside the self-referential audit task file

**Verdict**: DELETE_WITH_TEST_CLEANUP

**Reason**: `docs/design/ancestor-responsibilities.md` is the only live reference (loaded by ancestor seat SKILL.md and rendered by ancestor_brief.py); deleting it breaks `test_ancestor_brief.py:330`. `design/followups-after-m1.md` and `design/phase-7-retire.md` are purely historical Phase 7 artifacts with zero runtime dependencies. `docs/PACKAGING.md` and `docs/TEAM-INSTANTIATION-PLAN.md` are dormant. Delete the 4 dormant files and 2 historical design docs, but update `test_ancestor_brief.py` and `clawseat-ancestor/SKILL.md` before removing `ancestor-responsibilities.md`.

---

## Cross-cutting observations

1. **core/adapter/ and adapters/ are completely unrelated**: They share no code; `core/adapter/` handles project/seat orchestration while `adapters/` handles tmux session management. Both composed inside `shells/openclaw-plugin/`. Neither is a legacy version of the other.

2. **Symlink trick in Candidate 5**: `core/skills/agent-monitor/send-and-verify.sh` is a symlink to `core/shell-scripts/send-and-verify.sh`. All real runtime callers use the canonical path. This is the only candidate with zero blast radius.

3. **Dormant-but-registered skills (Candidates 7, 8)**: `workflow-architect` and `lark-im` are both registered in `skill_registry.toml` with zero runtime call sites, but deleting them would break template skill arrays and registry boot. They appear to be scaffolding for future capability.

4. **SKILL.md as protocol contract (Candidate 9)**: `clawseat-koder-frontstage/SKILL.md` is referenced as a text file in tests (`test_heartbeat.py` assertions on heading presence), not as a Python import. This is a fragile pattern — the skill has no actual Python entry point but its documentation shape is tested.

5. **Tests that read docs as text**: Candidates 9 and 12 both have tests that assert on the presence/content of `.md` files rather than importing code. This creates a coupling that grep-based audits miss.

---

## Recommended delete order (lowest risk first)

1. **`core/skills/agent-monitor/`** — SAFE_TO_DELETE. Zero dependencies, zero tests. No coordination needed.
2. **`docs/PACKAGING.md` + `docs/TEAM-INSTANTIATION-PLAN.md`** — Both are purely prose, no test coupling. Just remove from README.md link and done.
3. **`design/followups-after-m1.md` + `design/phase-7-retire.md`** — Historical Phase 7 artifacts with zero runtime references. Safe to delete; `test_complete_handoff_koder_guard.py` only references the filename in a comment.
4. **`examples/starter/profiles/legacy/`** — All dormant TOML profiles. Delete + remove from `docs/ARCHITECTURE.md` prose references.
5. **`examples/arena-pretext-ui/`** — Requires: (a) update `manifest.toml` to remove the entry, (b) update `test_portability.py` to skip the now-absent profile (or remove the test), (c) clean prose refs in `docs/ARCHITECTURE.md`, `README.md`, `docs/schemas/v0.4-layered-model.md`.
6. **`docs/design/ancestor-responsibilities.md`** — Requires: (a) update `tests/test_ancestor_brief.py:330` to remove the assertion, (b) update `core/skills/clawseat-ancestor/SKILL.md` spec_documents field, (c) update `core/templates/ancestor-engineer.toml` comments. After those 3 reference sites are cleaned, safe to delete.
7. **`core/skills/clawseat-koder-frontstage/`** — Requires: update `test_heartbeat.py` two text-assertion tests to either remove SKILL.md shape checks or mock the file. All other references are doc-comment only.

---

## Open questions for user

1. **`openclaw_plugin/` is a symlink to `openclaw-plugin/`** — The candidate list counted `openclaw_plugin/` as "empty" but it is a symlink pointing to a live directory. Does the delete plan intend to remove the actual `openclaw-plugin/` directory (which would break the manifest entry and openclaw bootstrap), or was this a mistaken entry assuming it was an empty placeholder?

2. **`docs/install/` and `docs/review/` are listed as candidates but do not exist** — Should these be treated as already deleted (nothing to do) or as a signal that the directory structure was never populated as planned?

3. **`core/skills/workflow-architect/` has zero runtime call sites but is fully registered** — Is this intentionally left as scaffolding for future use, or should the dangling registration entries be cleaned up as part of this audit?

4. **`test_heartbeat.py` tests `clawseat-koder-frontstage/SKILL.md` as text** — Should these two tests be updated to not depend on SKILL.md shape, or should they be removed entirely since they test documentation rather than behavior?
