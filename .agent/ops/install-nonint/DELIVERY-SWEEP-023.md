task_id: SWEEP-023
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: Experimental branch completed the targeted legacy sweep, removed the audited dead paths, and brought test fallout back down to the known 4-fail baseline.

## Deleted paths (with line counts)

- `core/skills/agent-monitor/` — 379 lines removed across 8 files
- `docs/PACKAGING.md` — 117 lines removed
- `docs/TEAM-INSTANTIATION-PLAN.md` — 122 lines removed
- `design/followups-after-m1.md` — 415 lines removed
- `design/phase-7-retire.md` — 108 lines removed
- `design/memory-seat-v3/` — 591 lines removed across 2 files
- `examples/starter/profiles/legacy/` — 372 lines removed across 6 files
- `examples/arena-pretext-ui/` — 57 lines removed across 2 files
- `docs/design/ancestor-responsibilities.md` — 166 lines removed
- `core/skills/clawseat-koder-frontstage/` — 437 lines removed across 2 files

## Test/ref cleanups applied

- Removed dead skill/path references from:
  - `README.md`
  - `docs/ARCHITECTURE.md`
  - `core/skills/gstack-harness/SKILL.md`
  - `core/skill_registry.toml`
  - `core/templates/gstack-harness/template.toml`
  - `core/templates/ancestor-engineer.toml`
  - `core/skills/clawseat-ancestor/SKILL.md`
  - `core/tui/ancestor_brief.py`
  - `manifest.toml`
  - `scripts/clean-slate.sh`
  - `core/skills/memory-oracle/scripts/_memory_schema.py`
- Removed obsolete doc-shape / legacy-fixture tests:
  - deleted `tests/test_cs_init_openclaw_profile_guard.py`
  - deleted heartbeat assertions for `clawseat-koder-frontstage` from `tests/test_heartbeat.py`
  - deleted arena portability assertion from `tests/test_portability.py`
  - deleted legacy-profile assertions from `tests/test_install_flow_phases.py`
- Updated surviving tests to stop asserting deleted design docs:
  - `tests/test_ancestor_brief.py`
  - `tests/test_complete_handoff_koder_guard.py`

## Verification output (pytest tail + grep results)

Deleted-path checks:

```text
ls: core/skills/agent-monitor/: No such file or directory
ls: examples/arena-pretext-ui/: No such file or directory
ls: examples/starter/profiles/legacy/: No such file or directory
ls: design/memory-seat-v3/: No such file or directory
ls: core/skills/clawseat-koder-frontstage/: No such file or directory
ls: docs/PACKAGING.md: No such file or directory
ls: docs/design/ancestor-responsibilities.md: No such file or directory
```

Repo grep, exact command from TODO:

```text
./.agent/ops/install-nonint/TODO-TESTER-MINIMAX-RESEARCH.md:32:5. `core/skills/agent-monitor/` (7 files)
./.agent/ops/install-nonint/TODO-TESTER-MINIMAX-RESEARCH.md:36:9. `core/skills/clawseat-koder-frontstage/` (2 files)
./.agent/ops/install-nonint/TODO-TESTER-MINIMAX-RESEARCH.md:38:11. `examples/arena-pretext-ui/` (2 files) + `examples/starter/profiles/legacy/` (5 files)
./.agent/ops/install-nonint/TODO-TESTER-MINIMAX-RESEARCH.md:39:12. `design/` (4 files) + `docs/design/` (1 file) + `docs/install/` (empty) + `docs/review/` (empty) + `docs/PACKAGING.md` + `docs/TEAM-INSTANTIATION-PLAN.md`
```

Live repo grep (same command, excluding `./.agent/` planning artifacts):

```text
<no output>
```

Full pytest tail:

```text
    _require_repo(CLAWSEAT_REPO, "clawseat")
tests/test_scan_project_smoke.py:64: in _require_repo
    pytest.fail(message + " Cannot silently skip on a maintainer workstation.")
E   Failed: real repo missing at /Users/ywf/.clawseat (label=clawseat); SPEC §5.3.1/§5.3.2 mandates this as hard gate for local runs. Cannot silently skip on a maintainer workstation.
=========================== short test summary info ============================
FAILED tests/test_scan_project_smoke.py::test_clawseat_shallow_scan - Failed:...
FAILED tests/test_scan_project_smoke.py::test_payload_budget_shallow - Failed:...
FAILED tests/test_scan_project_smoke.py::test_query_integration_dev_env - Failed:...
FAILED tests/test_scan_project_smoke.py::test_dry_run_never_writes - Failed: ...
4 failed, 1632 passed, 2 xfailed in 97.59s (0:01:37)
```

## Notes / follow-ups

- The exact grep command only hits `.agent/ops/install-nonint/TODO-TESTER-MINIMAX-RESEARCH.md`, which is a planner/tester research artifact, not a live repo/runtime reference.
- The remaining 4 pytest failures are unchanged baseline failures tied to the local hard gate in `tests/test_scan_project_smoke.py` expecting `/Users/ywf/.clawseat` to exist.
- Commit landed on `experimental` only; nothing was merged to `main`.
