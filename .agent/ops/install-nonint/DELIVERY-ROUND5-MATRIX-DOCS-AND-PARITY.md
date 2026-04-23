# Round-5 Delivery: Matrix Docs and Launcher Parity

## Decision

Executed planner-approved option A: safe reconciliation.

- `SUPPORTED_RUNTIME_MATRIX` remains the canonical session-level contract.
- Launcher `--auth` values remain execution labels at the process boundary.
- Translation remains in `SessionService._launcher_auth_for()`.
- No auth-mode migration was performed.
- No feature removal was performed.

## Policy Outcome

Kept these matrix tuples unchanged:

- `codex/oauth/openai`
- `gemini/api/google-api-key`
- `claude/api/ark`
- `claude/ccr/ccr-local`

Documented explicitly that:

- `codex/oauth/openai -> --auth chatgpt`
- `gemini/api/google-api-key -> --auth primary`
- `claude/api/ark -> --auth custom` is a live path
- `claude/ccr/ccr-local -> --auth custom` is a live path

Backlog only, not done in this round:

- B: canonical auth-mode migration
- C: end-to-end feature removal for `ark` and/or `ccr`

## Files Changed

- `core/scripts/agent_admin_config.py`
- `tests/test_matrix_launcher_parity.py`
- `.agent/ops/install-nonint/DISCUSSION.md`
- `.agent/ops/install-nonint/DELIVERY-ROUND5-MATRIX-DOCS-AND-PARITY.md`

## Matrix Before / After

- Auth-mode rows before: `8`
- Auth-mode rows after: `8`
- Provider triples before: `11`
- Provider triples after: `11`
- Delta: `0`

## What Changed

### 1. agent_admin_config.py docs/comments

Added a module docstring and matrix-local comments clarifying:

- matrix `auth_mode` values are canonical persisted session values
- launcher `--auth` values are separate execution labels
- the bridge lives in `_launcher_auth_for()`
- `ark` and `ccr` are still live via launcher `--auth custom`

### 2. test_matrix_launcher_parity.py

Added a regex-based parity test that:

- parses launcher `validate_auth_mode()` accepted `(tool, auth)` pairs from `agent-launcher.sh`
- translates every matrix tuple through `SessionService._launcher_auth_for()`
- asserts the translated launcher auth label is actually accepted by `validate_auth_mode()`
- pins the important mappings:
  - `codex/oauth/openai -> chatgpt`
  - `gemini/api/google-api-key -> primary`
  - `claude/api/ark -> custom`
  - `claude/ccr/ccr-local -> custom`
- asserts launcher-only labels remain distinct from canonical matrix auth modes

## Tests

### Targeted

```bash
python3 -m py_compile \
  core/scripts/agent_admin_config.py \
  tests/test_matrix_launcher_parity.py

pytest \
  tests/test_matrix_launcher_parity.py \
  tests/test_agent_admin_session_isolation.py \
  tests/test_provider_validation.py \
  tests/test_auth_mode_oauth_token_and_ccr.py \
  tests/test_ark_provider_support.py \
  tests/test_launchers.py -q
```

Result:

- `84 passed in 7.93s`

### Regression Sweep

```bash
pytest tests/test_agent_admin_*.py tests/test_launcher*.py tests/test_install*.py -q
```

Result:

- `162 passed in 52.09s`

## Open Migrations / Downstream Notes

- If we ever want literal enum parity across matrix and launcher, that must be a separate migration touching persisted session state, CLI contracts, templates, docs, and tests.
- If we want to remove `ark` or `ccr`, that must be an end-to-end removal across validation, env scan, install/runtime mapping, and test coverage.
