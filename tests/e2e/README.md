# tests/e2e — End-to-End Smoke Tests

Standalone scripts (not pytest) that validate full lifecycle flows.
Each script outputs structured JSON: `{"all_passed": bool, "stages": [...]}`.

## memory_smoke.py — Memory Oracle Smoke Test

Validates the full memory lifecycle without the MiniMax LLM API:

```
scan_env → write_fixture → query (key/file/search) → verify_claims (pass + mismatch) → ask_dry_run
```

### Dry-run mode (default, CI-safe)

```bash
python3 tests/e2e/memory_smoke.py
# or explicitly:
python3 tests/e2e/memory_smoke.py --dry-run
```

No external calls. Uses a tmp directory; cleans up after itself.
Exit 0 = all stages passed. Output is valid JSON.

### Live mode (requires minimax.env)

```bash
python3 tests/e2e/memory_smoke.py --live
```

Requires `~/.agents/secrets/claude/minimax/memory.env` containing `MINIMAX_API_KEY`.
Dispatches a real query to the Memory CC TUI via `dispatch_task.py`.
Do not run in CI unless the secret is available.

## Dependencies

| Dependency | Required for |
|---|---|
| Python ≥ 3.11 | All scripts |
| `query_memory.py` (in-repo) | memory_smoke.py |
| `scan_environment.py` (in-repo) | memory_smoke.py |
| MiniMax API key | `--live` only |

No third-party pip packages required for dry-run mode.

## Adding New Smoke Tests

- Place scripts in this directory.
- Output structured JSON: `{"smoke_test": "<name>", "all_passed": bool, "stages": [...]}`
- Support `--dry-run` (default) and optional `--live`.
- Document dependencies in this README.
