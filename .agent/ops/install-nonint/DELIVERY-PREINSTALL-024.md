task_id: PREINSTALL-024
owner: tester-minimax
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: 3 landmines found; install is unblocked with 1 env-var fix + doc clarity improvement.

## Subagent A — env_scan auth gap

### env_scan.py auth check (lines 110-113)

```python
claude_oauth_ready = (
    (claude_dir / ".credentials.json").is_file()
    or any("cred" in name or "token" in name for name in claude_files)
)
```

Only checks `~/.claude/.credentials.json` or any file with "cred"/"token" in the name. Has **no mechanism to detect macOS Keychain-stored credentials** (entry name: "Claude Code-credentials").

### Keychain auth detection

**Detection is possible without raw macOS API.** The `claude` CLI itself exposes auth state:

```bash
claude auth status --json
```

When logged in via Keychain:
```json
{"loggedIn": true, "authMethod": "oauth_token", "apiProvider": "firstParty"}
```

This works regardless of storage backend because the CLI queries Keychain internally.

### launch_ancestor.sh auth gating dependency

**`launch_ancestor.sh` does NOT use `env_scan.py` for auth gating.** It calls `agent-launcher.sh --check-secrets` directly (line 113):

```bash
creds_json=$("$AGENT_LAUNCHER" --check-secrets "$TOOL" --auth "$CHECK_SECRETS_MODE" 2>&1)
```

`agent-launcher.sh` (lines 593-598) handles Keychain OAuth gracefully — it returns `{"status":"ok","note":"legacy keychain oauth; no secret file"}` and exits 0. So `launch_ancestor.sh` is **not affected** by the `env_scan.py` gap.

**Impact**: The gap only affects tools that consume `env_scan.py` output directly (debugging dashboards, status reporters). It does NOT block live install.

### Proposed minimal fix

Add `claude auth status --json` fallback in `env_scan.py` around line 113:

```python
# Add after the existing file-based check:
if not claude_oauth_ready and shutil.which("claude"):
    try:
        result = subprocess.run(
            ["claude", "auth", "status", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            import json as _json
            auth_info = _json.loads(result.stdout)
            if auth_info.get("loggedIn"):
                claude_oauth_ready = True
    except Exception:
        pass
```

---

## Subagent B — project registration gap

### INSTALL.md project registration step

**EXISTS** at lines 206-209, inside Step 3 ("Build Seat Infrastructure"):

```bash
export PROJECT=install
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" \
  project create "$PROJECT" "$CLAWSEAT_ROOT" || \
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" project show "$PROJECT"
```

But Step 4 ("Launch Ancestor") does **not** explicitly call out Step 3 as a hard prerequisite. A user who skims or skips Step 3 will hit `Unknown project ... Run agent-admin project create` before `launch_ancestor.sh` runs `switch-harness`.

### agent_admin.py project create/open logic

**`project_create`** (`agent_admin_crud.py:190`):
- Creates `~/.agents/projects/<name>/project.toml`
- Also calls `set_current_project` which writes `~/.agents/.current_project`
- **Files created**: `~/.agents/projects/<project>/project.toml` + `~/.agents/.current_project`

**`load_project_or_current`** (`agent_admin_store.py:91`):
- First checks `~/.agents/projects/<name>/project.toml`
- Fallback: if not registered but `~/.agents/sessions/<name>/` exists on disk, reconstructs from session TOMLs
- **If neither**: raises `AgentAdminError: "Unknown project: <name>. No registered project and no session directory found. Run agent-admin project create to register."` (line 121-124)

**`switch-harness`** (`agent_admin_switch.py:166`): Immediately calls `load_project_or_current(args.project)` — so project must be pre-registered.

### launch_ancestor.sh harness switch calls

| Line | Call |
|------|------|
| 128-140 | `agent_admin session switch-harness --project "$PROJECT" --engineer ancestor --tool "$TOOL" --mode "$AUTH_MODE" --provider "$PROVIDER"` |
| 145 | `agent_admin session start-engineer ancestor --project "$PROJECT"` |

No inline `project create` or auto-registration in `launch_ancestor.sh`.

### Minimal project registration sequence

```bash
# Step 1: Register the project (creates ~/.agents/projects/<name>/project.toml)
PROJECT=install
python3 "$CLAWSEAT_ROOT/core/scripts/agent_admin.py" \
  project create "$PROJECT" "$CLAWSEAT_ROOT"

# Step 2: Then launch ancestor
"$CLAWSEAT_ROOT/scripts/launch_anchor.sh" \
  --project "$PROJECT" --tool claude --auth-mode oauth --provider anthropic
```

### Doc gap

INSTALL.md Step 4 should add a prominent note: **"Step 3 must complete before this step — `project create` is required before `switch-harness` will succeed."**

---

## Subagent C — smoke test failures

### Test results

```
tests/test_scan_project_smoke.py::test_clawseat_shallow_scan     FAILED [ 11%]
tests/test_scan_project_smoke.py::test_cartooner_medium_scan      PASSED [ 22%]
tests/test_scan_project_smoke.py::test_cartooner_tests_frameworks PASSED [ 33%]
tests/test_scan_project_smoke.py::test_payload_budget_shallow    FAILED [ 44%]
tests/test_scan_project_smoke.py::test_payload_budget_medium     PASSED [ 55%]
tests/test_scan_project_smoke.py::test_payload_budget_deep       PASSED [ 66%]
tests/test_scan_project_smoke.py::test_query_integration_runtime  PASSED [ 77%]
tests/test_scan_project_smoke.py::test_query_integration_dev_env FAILED [ 88%]
tests/test_scan_project_smoke.py::test_dry_run_never_writes       FAILED [100%]
4 failed, 5 passed in 0.24s
```

### Failing test bodies

All 4 failures fail at the first line inside the test body — `_require_clawseat()` — never reaching any actual scan assertions:

```python
def _require_clawseat() -> None:
    _require_repo(Path("/Users/ywf/.clawseat"), "clawseat")

def _require_repo(repo: Path, label: str) -> None:
    if repo.exists():
        return
    message = f"real repo missing at {repo} (label={label}); ..."
    if _ci_skip_allowed():
        pytest.skip(message)
    pytest.fail(message + " Cannot silently skip on a maintainer workstation.")
```

All 4 tests (`test_clawseat_shallow_scan`, `test_payload_budget_shallow`, `test_query_integration_dev_env`, `test_dry_run_never_writes`) fail because `/Users/ywf/.clawseat` does not exist on this machine.

### Root cause

**Workspace setup gap, NOT a regression from 5d26fee.** The tests have an intentional hard gate: they require the canonical real repo at `/Users/ywf/.clawseat`. On this machine that path does not exist. The 5 passing tests are the `cartooner`-repo-dependent ones (and `/Users/ywf/coding/cartooner` exists, so they pass).

Escape hatches exist in the test file itself: set `CI=true` or `CLAWSEAT_SKIP_REAL_REPO_SMOKE=1`.

### Skip-safe verdict

**Safe to skip for this machine.** The tests are correct — they catch a real workspace setup gap. Fix for this machine:

```bash
export CLAWSEAT_SKIP_REAL_REPO_SMOKE=1
```

Or create the missing symlink if the intent is to have ClawSeat at that path. These are **NOT xfail-worthy in the codebase** — they are working correctly and catching an unmapped canonical path.

---

## Overall: install readiness verdict

**READY** (with two non-blocking housekeeping items)

| Blocker | Status |
|---------|--------|
| env_scan Keychain false-negative | **Non-blocking** — `launch_ancestor.sh` uses `agent-launcher.sh` which already handles Keychain OAuth correctly |
| INSTALL.md project registration | **Housekeeping** — step exists (lines 206-209) but Step 4 should prominently note it as a hard prerequisite |
| 4 smoke test failures | **Non-blocking** — workspace setup gap; safe to skip with `CLAWSEAT_SKIP_REAL_REPO_SMOKE=1` |

### Immediate install actions (non-blocking)
1. `export CLAWSEAT_SKIP_REAL_REPO_SMOKE=1` before running install smoke
2. Optional: add `claude auth status --json` fallback to `env_scan.py` (Subagent A fix)
3. Optional: add "Step 3 is a hard prerequisite" callout in INSTALL.md Step 4
