# DELIVERY — MULTI-IDENTITY-056 CHUNK 1

## Summary

Upgraded `PROJECT_BINDING.toml` from schema v2 to schema v3 and locked the new fields down with dedicated schema tests.

The v3 binding now carries the per-project tool isolation metadata needed by the later chunks:

- `tools_isolation`
- `gemini_account_email`
- `codex_account_email`

Legacy `feishu_bot_account` remains readable for compatibility and is still mapped onto the new v3 sender fields during rewrite.

## Changes

- [core/lib/project_binding.py](/Users/ywf/ClawSeat/core/lib/project_binding.py)
  - Updated the schema docstring from `Schema (v2)` to `Schema (v3)`.
  - Bumped `BINDING_SCHEMA_VERSION` to `3`.
  - Added `tools_isolation`, `gemini_account_email`, and `codex_account_email` to the dataclass and TOML serializer.
  - Added `_normalize_tools_isolation()` with a hard validation gate for `shared-real-home` vs `per-project`.
  - Kept legacy `feishu_bot_account` compatibility intact.

- [tests/test_project_binding_schema_v3.py](/Users/ywf/ClawSeat/tests/test_project_binding_schema_v3.py)
  - Added coverage for normal v3 serialization.
  - Added coverage for v2 compatibility loading.
  - Added coverage for invalid `tools_isolation` rejection.

## 顺手修了

- `PROJECT_BINDING.toml` was still documented as `Schema (v2)` even though the binding now carries three new fields.
- Root cause: the schema bump had landed in code, but the top-of-file contract comment was stale.
- Risk/impact: only schema-level metadata changed; legacy bindings still load and rewrite as before.

## Verification

- `python -m pytest /Users/ywf/ClawSeat/tests/test_project_binding_schema_v3.py -q` -> `5 passed`
- `python -m py_compile /Users/ywf/ClawSeat/core/lib/project_binding.py`

## Patch 历程

- 1st pass: upgraded the binding model and serializer to v3.
- 2nd pass: added schema tests for normal and compatibility loading.
- 3rd pass: added the invalid `tools_isolation` guard to lock the new field contract.

No commit.
