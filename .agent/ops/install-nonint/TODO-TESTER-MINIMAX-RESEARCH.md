# TODO — INST-RESEARCH-022 (deep-audit 12 cleanup candidates)

```
task_id: INST-RESEARCH-022
source: planner (architect)
reply_to: planner (architect)
target: tester-minimax (claude-minimax-coding)
repo: /Users/ywf/ClawSeat (experimental worktree, shared .git with /Users/ywf/coding/ClawSeat)
priority: P0
subagent-mode: REQUIRED — one subagent per candidate, run in parallel
do-not-delete: this is a research task only. Do NOT git rm anything.
```

## Why this is here

Planner tried an aggressive delete sweep based on superficial "这些是
legacy" guesses and broke 35 tests. Reverted. Lesson: every candidate
needs real dependency analysis before touching.

Goal of THIS task: for each of the 12 candidates below, produce a
verdict with evidence so codex's eventual delete commit is safe and
targeted.

## 12 candidates

For EACH candidate below, spawn a subagent to produce a report.

1. `core/migration/` — `complete_handoff_dynamic.py`, `dispatch_task_dynamic.py`, `dynamic_common.py`, `notify_seat_dynamic.py`, `render_console_dynamic.py`
2. `core/tui/` — `machine_view.py` + `ancestor_brief.py` + `__init__.py`
3. `core/adapter/` (9 files) + top-level `adapters/` (7 files) — relationship? both active?
4. `core/engine/` (3 files) — 84K, unknown purpose
5. `core/skills/agent-monitor/` (7 files)
6. `core/skills/socratic-requirements/` (2 files)
7. `core/skills/workflow-architect/` (3 files)
8. `core/skills/lark-im/` (13 files) + `core/skills/lark-shared/` (1 file)
9. `core/skills/clawseat-koder-frontstage/` (2 files)
10. `shells/codex-bundle/` + `shells/claude-bundle/` (5+5 files) + `shells/openclaw_plugin/` (empty)
11. `examples/arena-pretext-ui/` (2 files) + `examples/starter/profiles/legacy/` (5 files)
12. `design/` (4 files) + `docs/design/` (1 file) + `docs/install/` (empty) + `docs/review/` (empty) + `docs/PACKAGING.md` + `docs/TEAM-INSTANTIATION-PLAN.md`

## Per-candidate report template

Each subagent produces a block like:

```
### Candidate N: <path>

**What it is** (1 line):
**Size**: X files, Y lines

**Static references** (grep for imports / path references):
- <file:line> — <context snippet>
- ...
(no hits = LOW confidence; all hits internal = medium; external hits = KEEP)

**Runtime call sites** (where does it actually execute from?):
- Entry via <script/test/skill>:<line>
- ...
or "none found, appears dormant"

**Test dependencies** (tests that import / reference it):
- tests/test_foo.py — what exactly it tests
- ...

**Estimated blast-radius if deleted**:
- tests that would fail: <count + list>
- scripts that would crash at import: <count + list>
- skills that would have broken references: <count + list>

**Verdict**: SAFE_TO_DELETE | DELETE_WITH_TEST_CLEANUP | KEEP | KEEP_BUT_DORMANT (unused but low-cost to retain) | UNKNOWN (need user decision)

**Reason**: <2 lines>
```

## Research tools allowed

- `grep -rn "<pattern>" /Users/ywf/ClawSeat`
- `git log --all --oneline -- <path>` (see its history — if last change is years old + no recent refs → dormant)
- `python3 -c "import <module>"` (verify it still imports clean)
- `python3 -m pytest tests/test_<related>.py -q` (see what passes currently)
- Read files, SKILL.md, CLAUDE.md, docs

## Research tools NOT allowed

- `git rm`, `rm`, `git commit`, any mutation — pure read-only audit

## Subagent fan-out

Spawn **12 subagents in parallel**, one per candidate. Each returns the
block above within ~5 minutes. Main agent collects + composes the
DELIVERY.

Per INST-V051 pattern, use clear subagent names (e.g., "subagent-01-migration",
"subagent-02-tui", ..., "subagent-12-design-docs").

## Deliverable

Write `DELIVERY-INST-RESEARCH-022.md` in `/Users/ywf/ClawSeat/.agent/ops/install-nonint/`:

```
task_id: INST-RESEARCH-022
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <one line> — overall recommendation

## Summary table
| # | Path | Verdict | Blast radius |
|---|------|---------|--------------|
| 1 | core/migration/ | DELETE_WITH_TEST_CLEANUP | 4 tests need deletion too |
| ... |

## Detailed reports
### Candidate 1 — core/migration/
<block per template above>

### Candidate 2 — core/tui/
<block>

... (12 blocks)

## Cross-cutting observations
<e.g. "core/adapter/ and adapters/ are actually unrelated — both active">

## Recommended delete order (lowest risk first)
1. <path> — rationale
2. <path> — rationale
...

## Open questions for user
<things you genuinely can't decide from code alone>
```

Notify planner: "DELIVERY-INST-RESEARCH-022 ready".

## Out of scope

- Actually deleting anything (that's the next TODO to codex)
- Fixing the 4 pre-existing `test_scan_project_smoke.py` failures on experimental (separate investigation)
- Writing or running smoke for v0.5 install flow (that comes AFTER we know what to delete)
