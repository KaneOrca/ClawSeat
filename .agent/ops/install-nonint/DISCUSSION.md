# Round-5 Discussion: Matrix / Launcher Reconciliation Blocker

## Why I Stopped Before Coding

`SUPPORTED_RUNTIME_MATRIX` and `agent-launcher.sh --auth` are **not the same layer** today.

- `SUPPORTED_RUNTIME_MATRIX` models **canonical session-level** `(tool, auth_mode, provider)` tuples persisted in engineer/session/template state.
- `agent-launcher.sh --auth` accepts **execution labels** used only at the launcher boundary.
- The translation layer already exists in `core/scripts/agent_admin_session.py::_launcher_auth_for()` and in `scripts/launch_ancestor.sh`.

Because of that, the planner's proposed direct parity policy would change meaning, not just naming.

## Concrete Blockers

### 1. Renaming matrix auth modes to launcher labels is not a safe local change

The recommended policy says:

- `codex/oauth/openai` -> `codex/chatgpt/openai`
- `gemini/api/google-api-key` -> `gemini/primary/google-api-key`

That conflicts with current persisted/session-facing contracts used across the repo:

- `agent_admin_parser.py`
- `agent_admin_runtime.py`
- `agent_admin_store.py`
- `agent_admin_resolve.py`
- `core/templates/gstack-harness/template.toml`
- `core/skills/gstack-harness/references/seat-model.md`
- `core/templates/ancestor-brief.template.md`
- `core/skills/clawseat-install/scripts/init_koder.py`
- legacy/migration code and multiple tests

Current behavior is intentional and working:

- `codex/oauth/openai` is the canonical seat tuple
- launcher translation maps it to `--auth chatgpt`
- `gemini/api/google-api-key` is the canonical seat tuple
- launcher translation maps it to `--auth primary`

Blindly renaming the matrix would require a broader migration of persisted state, CLI semantics, templates, docs, and tests. That is larger than the requested local reconciliation patch.

### 2. `ark` and `ccr` are not actually dead runtime paths

The recommended policy says to remove:

- `claude/api/ark`
- `claude/ccr/ccr-local`

But those combinations are live above the launcher:

- `agent_admin_session.py` maps `claude/api/*` and `claude/ccr/*` to launcher `--auth custom`
- `agent_admin_resolve.py` still has runtime/env handling for `ccr`
- `scripts/install.sh` and `scripts/env_scan.py` still detect/use `ark`
- existing tests cover both

Removing them from the matrix without a broader feature-removal plan would create regressions:

- validation would start rejecting currently supported tuples
- `env_scan.py` could raise on tuples it still emits
- existing install / runtime / migration tests would fail or become misleading

## Safe Alternative Proposal

Instead of forcing literal enum parity, reconcile the layers explicitly:

1. Keep `SUPPORTED_RUNTIME_MATRIX` as the **session-level canonical contract**
2. Add comments/docstrings making the layer split explicit:
   - canonical session auth modes live in the matrix
   - launcher auth labels live in `agent-launcher.sh`
   - translation happens only at the launcher boundary
3. Add a parity test that validates:
   - every matrix tuple can be translated to a launcher auth label accepted by `validate_auth_mode`
   - launcher-only labels such as `chatgpt`, `primary`, `xcode`, `custom` do **not** silently become session-level matrix keys
4. If desired later, do a separate migration task for true canonical auth-mode renames
5. If desired later, do a separate feature-removal task for `ark` / `ccr` that updates:
   - matrix
   - env scan
   - install
   - runtime/session mapping
   - tests

## Requested Decision

Please confirm one of these directions before I code:

- **A. Safe reconciliation**: keep current canonical matrix, add explicit comments + translation parity tests
- **B. True migration**: rename canonical auth modes and update all callers/templates/tests
- **C. Feature removal**: intentionally drop `ark` and/or `ccr` end-to-end, not just from the matrix
