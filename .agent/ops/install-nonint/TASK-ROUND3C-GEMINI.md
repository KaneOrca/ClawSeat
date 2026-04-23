# TASK: Round-3 — SUPPORTED_RUNTIME_MATRIX reality-check audit

**Assigned to**: gemini (read-only investigation)
**Repo**: `/Users/ywf/ClawSeat` experimental branch

## Context

During Phase-A B0 provider clarification, operator got forced into combinations the system's `switch-harness` validator accepted but turned out broken at runtime:

- `planner: claude + oauth + anthropic` — forced (user wanted `claude-code`, rejected)
- `builder: codex + oauth + openai` — forced (user wanted `openai-codex`, rejected)
- `reviewer: codex + api + xcode-best` — forced (user wanted `openai-codex`, rejected). THIS COMBO FAILED AT RUNTIME because xcode.best only serves Claude models by default, and the default Claude-token operator had was Claude-only (no GPT access).
- `qa: claude + api + minimax` — worked
- `designer: gemini + oauth + google` — worked

Root problem: `SUPPORTED_RUNTIME_MATRIX` validator says combos are supported, but launcher / actual runtime disagree for some combos.

## Task (READ-ONLY investigation, no code changes)

1. Find `SUPPORTED_RUNTIME_MATRIX` definition:
   - Likely at `/Users/ywf/ClawSeat/core/scripts/agent_admin_config.py`
   - grep `SUPPORTED_RUNTIME_MATRIX` across codebase
2. List all (tool, auth_mode, provider) combinations declared supported
3. For EACH combination, reality-check by reading `/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh`:
   - Does `run_<tool>_runtime` function support that `auth_mode`? (Look at `case "$auth_mode" in ...` branches)
   - Does the launcher's config.toml / env setup handle that `provider`? (Look at `case "$CLAWSEAT_PROVIDER" in ...`, model_providers sections, base_url logic)
   - What's the mapping from engineer profile `auth_mode + provider` → launcher `--auth <X>` arg? (This is a separate bug #16 — note whether it's clear or ambiguous)
4. Categorize each combo:
   - ✅ **Confirmed working** (launcher path exists + runtime tested in this session)
   - ⚠️ **Matrix says yes, launcher rejects** (e.g. codex + api — launcher only supports `oauth|xcode|custom|chatgpt`)
   - ⚠️ **Matrix says yes, runtime breaks** (e.g. codex + api + xcode-best — launcher routes but config.toml missing model_providers, so codex hits api.openai.com → 401)
   - ❌ **Matrix should NOT include** (combo is fundamentally incompatible)

## Deliverable

Write `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DIAGNOSIS-MATRIX-AUDIT.md`:

```markdown
# SUPPORTED_RUNTIME_MATRIX audit

Source: <file:line>
Declared combinations: <count>

## Summary table

| tool | auth_mode | provider | launcher supports | runtime works | recommendation |
|------|-----------|----------|-------------------|---------------|----------------|
| claude | oauth | anthropic | ✅ | ✅ | keep |
| claude | api | minimax | ✅ | ✅ | keep |
| codex | oauth | openai | ✅ | ✅ | keep |
| codex | api | xcode-best | ⚠️ maps to --auth xcode | ⚠️ requires config.toml fix | keep after #17 fixed |
| codex | api | openai | ❓ | ❓ | investigate |
| ... | ... | ... | ... | ... | ... |

## Detail per combo

### claude + oauth + anthropic
- Evidence: launcher line X, runtime: user-confirmed working
- Verdict: keep

### codex + api + xcode-best
- Evidence: launcher rejects `--auth api`; agent_admin maps to `--auth xcode`; config.toml NOT rendered (bug #17); model_provider defaults to OpenAI → hits api.openai.com → 401
- Verdict: KEEP IN MATRIX but mark as "pending #17 fix" (codex-xcode round-3a)

...

## Recommendations
1. Remove entries for combos that have no launcher path
2. Document naming: `provider=openai` vs `openai-codex` (user's rejected form) — which is canonical?
3. For `claude-code` (user's rejected form for claude+oauth) — same question
```

When done: `echo MATRIX_AUDIT_DONE`

## Constraints
- READ ONLY. No code changes, no commits, no file writes except the DIAGNOSIS-MATRIX-AUDIT.md report.
- Don't run `bash scripts/install.sh` or modify `~/.agents/` state.
- Don't interrupt running seats or codex-xcode/codex-chatgpt tmux sessions.
