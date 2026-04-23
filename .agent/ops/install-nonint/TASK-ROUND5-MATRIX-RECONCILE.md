# TASK: Round-5 — SUPPORTED_RUNTIME_MATRIX reconciliation with launcher reality

**Assigned to**: codex-chatgpt TUI (idle, fresh from round-3b pivot; has relevant context)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Type**: policy + code fix (not docs-only)

---

## Background

Gemini's round-3c audit (`/Users/ywf/coding/ClawSeat/.agent/ops/install-nonint/DIAGNOSIS-MATRIX-AUDIT.md` — note: main checkout, not worktree) found significant drift between:

- `SUPPORTED_RUNTIME_MATRIX` in `core/scripts/agent_admin_config.py` (Python-side declared supported combinations)
- `core/launchers/agent-launcher.sh` (shell-side actual implementation with `case $auth_mode in ...` branches)

Concrete drift categories:

1. **Zombie matrix entries** — `claude+ccr+ccr-local` and `claude+api+ark` are in the matrix but launcher has NO `ccr` or `ark` branch (startup would fail)
2. **Zombie launcher branches** — launcher supports `--auth oauth` for claude (legacy keychain) and `--auth custom` for every tool, but these are NOT in the matrix (orphaned code paths)
3. **Naming inconsistencies** — the matrix lists:
   - `gemini+api+google-api-key` but launcher case is `--auth primary`
   - `codex+oauth+openai` but launcher case is `--auth chatgpt`
4. **The `api` family confusion** — matrix groups many providers under `auth_mode=api`, but launcher's case branches are the PROVIDER NAMES directly (`--auth minimax`, `--auth xcode`, `--auth anthropic-console`, etc.). This means `auth_mode` field doesn't map 1:1 to launcher `--auth` argument.

## Recommended policy (planner's call — execute unless you find a blocker)

| Drift | Policy | Rationale |
|-------|--------|-----------|
| `ccr` zombie | REMOVE from matrix | Not implemented, no user has asked |
| `ark` zombie | REMOVE from matrix (or verify if `claude+api+ark` should map to a launcher branch) | Same reasoning |
| `oauth` orphan (claude) | ADD to matrix as a documented legacy mode, marked `deprecated=true` | Launcher still supports it; let's not silently expose |
| `custom` orphan | ADD to matrix for each tool that supports it | Widely usable, should be discoverable |
| Naming (`gemini api` → shell `primary`; `codex oauth` → shell `chatgpt`) | **Rename the matrix's auth_mode strings to match launcher case labels** | Launcher is ground truth (user-observable failures); matrix is documentation |
| `api` family confusion | Document clearly in code comment + `agent_admin_config.py` module docstring that `auth_mode=api` + `provider=<X>` maps to launcher `--auth <X>` | Don't change architecture; clarify |

**If you disagree with any of these, STOP and write your alternative proposal in a DISCUSSION.md before coding — DO NOT improvise.**

---

## Fan-out instruction (MANDATORY)

This task has 3 independent lanes. **Use your Agent tool to fan-out**.

See `core/skills/gstack-harness/references/sub-agent-fan-out.md` (just landed round-4) for the pattern.

---

## Lane A — Remove zombie matrix entries

File: `core/scripts/agent_admin_config.py`

1. `grep -n "SUPPORTED_RUNTIME_MATRIX" core/scripts/agent_admin_config.py` — locate definition
2. Remove `(claude, ccr, ccr-local)` entry (if present)
3. Remove `(claude, api, ark)` entry UNLESS you find evidence in launcher that `ark` is a live branch (grep agent-launcher.sh for `ark`)
4. Test: `pytest tests/test_agent_admin_config*.py -q` should still pass

## Lane B — Add orphan launcher branches to matrix

File: `core/scripts/agent_admin_config.py`

1. Add `(claude, oauth, anthropic)` — legacy keychain; mark with `deprecated=True` if matrix schema supports flags, or add a comment
2. Add `(claude, custom, <provider>)`, `(codex, custom, <provider>)`, `(gemini, custom, <provider>)` — custom mode for all tools
3. Grep launcher for other orphan branches (`grep -n 'case "$auth_mode"' core/launchers/agent-launcher.sh -A 30`) and add any missed combos
4. Tests: extend `tests/test_agent_admin_config*.py` or add new one verifying the added entries

## Lane C — Rename matrix auth_mode strings to match launcher case labels

File: `core/scripts/agent_admin_config.py`

Per gemini audit:

- `(gemini, api, google-api-key)` → `(gemini, primary, google-api-key)` (launcher case is `primary`, not `api`)
- `(codex, oauth, openai)` → `(codex, chatgpt, openai)` (launcher case is `chatgpt`, not `oauth`)

Also verify and align any other `api` entries where the real launcher case label differs (this is where audit's "api family confusion" comment applies).

Add a docstring to `agent_admin_config.py` at top of `SUPPORTED_RUNTIME_MATRIX`:

```python
"""
auth_mode values are the EXACT strings the launcher accepts as --auth.
The launcher is ground truth. Matrix entries must match launcher case labels.
When auth_mode == 'api' or a provider-specific label like 'minimax' / 'xcode',
the launcher routes to that provider's config rendering path.
"""
```

Migration: any callers of the matrix that previously received `auth_mode='api'` for gemini or `auth_mode='oauth'` for codex need to keep working. Check `agent_admin_session.py` and any start-engineer paths — if they translate engineer profile values before looking up the matrix, make sure the translation still hits a valid matrix row.

---

## Tests

1. Extend `tests/test_agent_admin_config*.py`:
   - zombie `ccr`/`ark` entries absent
   - orphan `oauth`/`custom` entries present
   - renamed entries use launcher-canonical strings
2. Add `tests/test_matrix_launcher_parity.py` — cross-check that every matrix entry's `auth_mode` has a matching case branch in launcher (regex parse)
3. Regression sweep: `pytest tests/test_agent_admin_*.py tests/test_launcher*.py tests/test_install*.py -q`

---

## Deliverable

1. Patches applied on experimental branch
2. All new + regression tests pass
3. Write `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND5-MATRIX-RECONCILE.md`:
   - Policy decisions (if you deviated from recommended)
   - Files Changed
   - Matrix before/after (row counts + delta)
   - Tests: new + regression
   - Open migrations / downstream call sites that may break

## Signal completion

`echo ROUND5_MATRIX_DONE`

---

## Constraints

- Parallel-safe with ongoing reviewer's review of round-3b agent-launcher.sh edits: Matrix work touches `agent_admin_config.py` NOT `agent-launcher.sh`; and zero overlap with #15 builder task
- No commit — planner commits after reviewer verdict
- If you have to alter `agent-launcher.sh` to implement ccr/ark instead of removing them, treat that as a scope increase — WRITE A PLAN FIRST in DELIVERY, do NOT just plow ahead
