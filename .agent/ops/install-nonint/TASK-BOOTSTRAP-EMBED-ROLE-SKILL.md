# TASK: Root-cause fix — embed role SKILL.md into workspace AGENTS.md/CLAUDE.md/GEMINI.md render

**Assigned to**: codex-chatgpt TUI (agent-launcher-codex-chatgpt-20260423-230652)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Source**: planner
**Priority**: HIGH — blocks seat role awareness in install test

---

## Root cause (confirmed)

`core/scripts/agent_admin_template.py:160-237` renders workspace `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` purely from `engineer.toml` fields:

- `engineer.skills`
- `engineer.role_details`
- `engineer.aliases`
- `authority_lines`

But for v0.7 install bootstrap, every `~/.agents/engineers/<seat>/engineer.toml` has:

- `skills = []` (empty)
- `role_details = ["<1-line description>"]`
- no aliases

So rendered workspace files are **10-line stubs** — seats don't actually see the role contract. The real role contract (60-190 lines each: 身份约束 / 工作模式 / anti-patterns / deliver / escalation) lives in `core/skills/<role>/SKILL.md` (planner, builder, reviewer, qa, designer, memory-oracle, clawseat-ancestor). Bootstrap **never reads those**.

This is the design gap. SKILL.md is the canonical source, but the render pipeline doesn't consume it.

## Fix — embed SKILL.md content in render

For each seat whose `engineer.id` maps to a role with `core/skills/<role>/SKILL.md` available, append the file's content (stripped of YAML frontmatter) as a dedicated `## Role SKILL (canonical)` section in the rendered AGENTS.md / CLAUDE.md / GEMINI.md.

Mapping: prefer `core/scripts/seat_skill_mapping.py::role_skill_for_seat(seat_id)` (already exists from round-3b, maps e.g., `planner` → `planner`, `builder` → `builder`, `memory` → `memory-oracle`).

### Implementation

1. In `agent_admin_template.py`, after the existing render sections (around line 209 for claude, 237 for gemini, and whatever is equivalent for AGENTS.md/codex render), add:

```python
def _load_role_skill_content(clawseat_root: Path, seat_id: str) -> str | None:
    """Load core/skills/<role>/SKILL.md content (frontmatter stripped) or None."""
    from seat_skill_mapping import role_skill_for_seat
    role_skill = role_skill_for_seat(seat_id)
    if not role_skill:
        return None
    skill_file = clawseat_root / "core" / "skills" / role_skill / "SKILL.md"
    if not skill_file.exists():
        return None
    text = skill_file.read_text(encoding="utf-8")
    # Strip YAML frontmatter if present (between leading --- and next ---)
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            text = text[end + 4:].lstrip()
    return text
```

2. Extend `claude_lines`, `gemini_lines`, `codex_lines` (the AGENTS.md counterpart) by appending:

```python
skill_content = _load_role_skill_content(clawseat_root, session.engineer_id)
if skill_content:
    claude_lines.extend([
        "",
        "---",
        "",
        "## Role SKILL (canonical)",
        "",
        f"Loaded from `core/skills/{role_skill_for_seat(session.engineer_id)}/SKILL.md`.",
        "",
        skill_content,
    ])
    # same append to gemini_lines and codex_lines
```

3. `clawseat_root` must be in scope; if it's not available in the render function, thread it through from the caller (it's typically `os.environ["CLAWSEAT_ROOT"]` or a derived path; check how other file reads in this module resolve).

4. Handle the case where a seat has no role skill mapping (e.g., a new role not yet defined): skip the append silently — bootstrap stub is the fallback.

### Test coverage

1. `tests/test_workspace_render_embeds_role_skill.py` (NEW):
   - For each canonical seat (planner, builder, reviewer, qa, designer, memory, ancestor):
     - render a synthetic workspace via the template API
     - assert the output contains `## Role SKILL (canonical)`
     - assert it contains a marker string from the corresponding SKILL.md (e.g., for planner, `"我只接 planner 的派单"` or similar identity constraint text)
   - For a seat with unknown role → assert no `## Role SKILL` section, no crash

2. Regression: existing `tests/test_agent_admin_*` + any workspace render tests should still pass; update expectation assertions if they counted exact line count of workspace files.

3. Manual verification: after fix lands, run `agent_admin session start-engineer qa --project install` and inspect `/Users/ywf/.agents/workspaces/install/qa/AGENTS.md`; should contain the full qa SKILL.md content (60+ lines) not the 10-line stub.

---

## Fan-out instruction

This task has 2 lanes that are mostly independent:

- **Lane A**: the `_load_role_skill_content` helper + the 3 render-site appends (AGENTS.md/CLAUDE.md/GEMINI.md) in `agent_admin_template.py`
- **Lane B**: the new test file + any expectation updates to existing tests

Fan-out via Agent tool per `core/skills/gstack-harness/references/sub-agent-fan-out.md`.

---

## Deliverable

1. Patches on experimental branch (do not commit — planner bundles)
2. `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-BOOTSTRAP-EMBED-ROLE-SKILL.md`:
   - Files Changed + diff highlights
   - Tests (new + regression)
   - Before/after sample of qa workspace AGENTS.md (line count + first 20 lines of "Role SKILL" section)
   - Edge cases considered (missing SKILL.md, unknown role, empty skill file)

## Signal completion

`echo BOOTSTRAP_EMBED_DONE`

---

## Constraints

- Do NOT change `core/skills/<role>/SKILL.md` content itself — they're the canonical source
- Do NOT change `engineer.toml` fields (skills/role_details) — they have separate purpose (dynamic roster metadata)
- Don't rebuild running seats during this task — code change only; planner will restart seats post-commit
- If the SKILL.md contains very long content (> 500 lines), still embed it fully — the workspace file is not size-limited; seat tool will read what it needs
- Frontmatter stripping must be idempotent and handle files without frontmatter gracefully

## Why this is the root fix

Prior hot-patches (planner's CLAUDE.md / designer's GEMINI.md manual copies) were overwritten by bootstrap on seat restart. After this fix, bootstrap itself carries the role content — subsequent restarts keep working, no manual patching needed.
