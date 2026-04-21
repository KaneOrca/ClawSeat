# Architect review packet — ancestor Phase 2

> **Author**: TUI engineer
> **Date**: 2026-04-21
> **Scope**: Everything under `docs/design/ancestor-*`, `docs/schemas/ancestor-*`,
> `core/tui/ancestor_brief.py`, `core/skills/clawseat-ancestor/`,
> `core/templates/ancestor-engineer.toml`, `tests/test_ancestor_brief.py`
> **Status**: Provisional. All v0.1 files need architect sign-off before
> Phase 3 (install_entrypoint wiring).
> **Operator decisions already locked** (this packet does NOT re-question):
>   - ancestor owns all seat lifecycle (koder is relieved of this)
>   - ancestor never upgrades to koder, never retires
>   - Feishu sender uses planner's lark-cli identity with `sender_seat: ancestor` header
>   - config-drift-recovery policy: new config wins, loud event (not quiet block)

## 1. What I shipped

| File | Role | LOC |
|------|------|-----|
| `docs/design/ancestor-responsibilities.md` | Responsibility matrix (v0.1) | ~190 |
| `docs/schemas/ancestor-bootstrap-brief.md` | Brief file format spec (v0.1) | ~200 |
| `core/skills/clawseat-ancestor/SKILL.md` | Ancestor skill body draft | ~150 |
| `core/templates/ancestor-engineer.toml` | Engineer template for `~/.agents/engineers/ancestor/engineer.toml` generation | ~70 |
| `core/tui/ancestor_brief.py` | Brief renderer (YAML front-matter + markdown body) | ~260 |
| `tests/test_ancestor_brief.py` | Renderer + context-loader tests (25 cases) | ~280 |

Total delta: **~1,150 lines + 25 tests**. All tests green.

## 2. What I didn't ship (explicitly out of my scope)

- `~/.agents/engineers/ancestor/engineer.toml` — instantiated from the
  template at install time, not checked in as user data.
- Updates to koder's existing `~/.agents/engineers/koder/engineer.toml`
  — operator data, architect decides the lifecycle-relief wording.
- `core/skills/clawseat-koder-frontstage/SKILL.md` changes (if any) —
  same reason; I flag the text that likely needs edits in §5 below.
- `install_entrypoint.py` integration — Phase 3 work; blocked on your
  approval of this packet.

## 3. Decision points requesting your approval

### 3.1 Brief schema format (YAML front-matter + Markdown body)

**Proposed**: Hybrid. Leading `---` YAML block carries machine-readable
fields (project, tenant, seats[], checklists, whitelist); body is human
prose for review. Ancestor skill parses the YAML, operator reads the MD.

**Alternatives**:
- Pure JSON file. Easier to parse, zero ambiguity. Harder for humans.
- Pure TOML. Consistent with profile, but TOML dislikes deeply nested lists.

**Why I chose hybrid**: the brief is read by BOTH humans (on review /
debug) AND the ancestor skill. YAML + MD hits both audiences with one file.

**Sign-off needed**: YAML front-matter OK, or should I migrate to JSON/TOML?

### 3.2 `seats_declared[].state` enum is `alive | pending | dead`

**Proposed**: 3 values. `alive` = tmux has-session rc=0 at render time;
`pending` = not yet launched; `dead` = was alive but has-session rc=1.

**Alternative**: add `dying` for mid-shutdown observability.

**Why I went with 3**: render time is a snapshot; `dying` is a transient
state the brief can't faithfully capture. Patrol loop updates states in
STATUS.md, not in the brief.

**Sign-off needed**: 3 values OK?

### 3.3 Phase-A has 8 steps (B1..B8)

**Proposed**: see `docs/schemas/ancestor-bootstrap-brief.md §Phase-A checklist`.

**Open**: should there be a `B0-preflight` that parses the YAML block
before B1? Currently B1 implicitly parses it. If YAML is malformed we
never reach B2.

**Sign-off needed**: B1 doubles as "validate YAML", OK?

### 3.4 Feishu identity sharing

**Locked by operator**: ancestor uses planner's lark-cli OAuth identity
with `sender_seat: ancestor` header.

**Open for architect review**: should lark-cli / planner surface a
"borrow identity" audit entry when ancestor sends? Current implementation
assumes no — ancestor writes to planner's identity opaquely. If architect
wants audit trail, we need planner's lark-cli wrapper to log `sender_seat`
on each send.

**Sign-off needed**: audit trail on Feishu sends with borrowed identity?

## 4. Koder boundary update — architect action required

The responsibility matrix §7 removes lifecycle ownership from koder.
Existing claim in `~/.agents/engineers/koder/engineer.toml` says (quoted
from a prior read):

> "koder owns all seat lifecycle operations (start, restart, reconfigure,
> stop) at every phase — install, reconfiguration, and self-healing. For
> each seat koder collects configuration from the user and runs
> start_seat.py (or the batch `session start-engineer` + `window
> open-monitor` pair) directly."

**Proposed edit** (architect to apply):

> "koder is the project's frontstage intake router. It classifies user
> intent, frames scope, and dispatches through planner. It does NOT own
> seat lifecycle — the project's `ancestor` seat handles add / remove /
> reconfigure / restart. Lifecycle requests route: user → koder → planner
> → ancestor (not user → koder → start_seat.py as previously)."

I did not make this edit because:

1. `~/.agents/engineers/koder/engineer.toml` is operator data, not
   clawseat source.
2. Koder's skill (if any) at `core/skills/clawseat-koder-frontstage/`
   may need a parallel edit; I haven't read it to avoid scope creep.

**Architect action**:
- Approve wording and edit koder engineer.toml in-place, OR
- Propose different wording and ping me to retrofit.

## 5. Test coverage summary

`tests/test_ancestor_brief.py` locks these invariants:

- **Section A (9 tests)** — context loader: version/project/tenant validation, parallel_instances placement, session naming, tmux state detection
- **Section B (5 tests)** — YAML envelope: delimiters, parseability, checklist ordering, sender identity, whitelist passthrough
- **Section C (3 tests)** — body: mentions ancestor's hard rules (NEVER upgrade/retire), references spec paths
- **Section D (2 tests)** — write path: creates directories, idempotent re-render
- **Section E (3 tests)** — CLI: missing profile → rc=2; dry-run stdout; JSON-context parseable
- **Section F (3 tests)** — schema constants: version string, 8 checklist steps, stable identifiers

Total: **25 tests, 25 passing, 0 skipped** (when PyYAML installed).

## 6. What unblocks once you sign off

After this packet's approval, I will:

1. Write `core/tui/install_entrypoint.py` that:
   - Runs `install_wizard.run_wizard(...)` to produce the v2 profile
   - Calls `ancestor_brief.write_brief(...)` to produce the handoff
   - Invokes `core/launchers/agent-launcher.sh --headless --session
     <project>-ancestor-claude` to spawn ancestor tmux
   - Opens one iTerm pane via `iterm_panes_driver.py` attached to ancestor
   - Exits; control fully handed off
2. Add `tests/test_install_entrypoint.py` with mocked subprocess + driver
3. Instantiate the ancestor-engineer template at install time (substitute
   `{PROJECT}` and `{CLAWSEAT_ROOT}`)
4. Wire `install` CLI: `agent-admin install <project>` as the top-level
   entry

## 7. Known gaps / future work

- Ancestor skill content (`core/skills/clawseat-ancestor/SKILL.md`) is a
  TUI engineer's reasonable draft. A skill-author may want to expand the
  operational recipes (specific tmux probe patterns, timeout values,
  retry logic) in v0.2.
- The 4-day cadence of steady-state patrol may need tuning once we see
  real traffic. Default `30 min` is conservative.
- We don't yet track "which B-step we're on" persistently — ancestor
  infers from STATUS.md + file existence. If it ever crashes between
  B4 launching a seat and that seat going alive, it could re-attempt.
  Acceptable for v0.1; may want a journal file in v0.2.

## 8. Recommended review order

1. **Responsibility matrix** (`docs/design/ancestor-responsibilities.md`) —
   this is the ground truth; everything else derives from it.
2. **Brief schema** (`docs/schemas/ancestor-bootstrap-brief.md`) — confirm
   the file format and checklist token semantics.
3. **Skill body** (`core/skills/clawseat-ancestor/SKILL.md`) — verify
   the operational recipe doesn't drift from the matrix.
4. **Engineer template** (`core/templates/ancestor-engineer.toml`) —
   authority flags + skill list.
5. **Renderer + tests** (`core/tui/ancestor_brief.py` + test file) —
   implementation review; the tests are the contract.
6. **This packet** — sanity check the §3 decision points.

## 9. Diff-ready summary

```
new files (7):
  docs/design/ancestor-responsibilities.md
  docs/schemas/ancestor-bootstrap-brief.md
  core/skills/clawseat-ancestor/SKILL.md
  core/templates/ancestor-engineer.toml
  core/tui/ancestor_brief.py
  tests/test_ancestor_brief.py
  docs/review/ancestor-phase2-review-packet.md  (this file)

modified files (1):
  core/tui/install_wizard.py
    - adapt to Phase 1 profile_validator public API
    - LEGAL_SEAT_ROLES now derived from real LEGAL_SEATS via canonical order
    - handle ProfileValidationError (new class from phase 1)
```

**Ready for your review.**
