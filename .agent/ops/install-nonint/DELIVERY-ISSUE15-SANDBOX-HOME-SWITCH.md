task_id: ISSUE15
owner: builder
target: planner
status: completed

# ISSUE15 Delivery

## Files Changed

- `core/scripts/agent_admin_session.py`
- `core/tui/ancestor_brief.py`
- `core/launchers/agent-launcher-discover.py`
- `core/launchers/agent-launcher-fuzzy.py`
- `core/scripts/seat_claude_template.py`
- `core/migration/dynamic_common.py`
- `scripts/install.sh`
- `tests/test_agent_admin_session_real_home_switch.py`
- `tests/test_issue15_real_home_switch.py`
- `tests/test_agent_admin_session_isolation.py`
- `tests/test_agent_admin_session_reseed.py`

## Classification And Patch Notes

### `core/scripts/agent_admin_session.py`

All 3 audited sites are `SWITCH`.

1. `_real_home_for_tool_seeding`
Before:
```py
os.environ.get("CLAWSEAT_REAL_HOME") or os.environ.get("AGENT_HOME") or str(Path.home())
```
After:
```py
real_user_home()
```
Reason: feeds operator-visible state under `~/.agents`, `.lark-cli`, `.codex`, `.gemini`.

2. `_launcher_secret_target`
Before:
```py
operator_home = Path.home()
```
After:
```py
operator_home = real_user_home()
```
Reason: writes launcher secrets under `~/.agents/.env.global` and `~/.agent-runtime/secrets/...`.

3. `_launcher_runtime_dir`
Before:
```py
operator_home = Path.home()
```
After:
```py
operator_home = real_user_home()
```
Reason: constructs runtime identities under `~/.agent-runtime/identities/...`.

### `core/tui/ancestor_brief.py`

Current file had 4 `Path.home()` sites; all 4 are `SWITCH`.

1. `_render_path`: use `real_user_home()` for `~` rendering.
2. `load_context_from_profile`: use real HOME for `.openclaw` and `.agents/tasks/.../PROJECT_BINDING.toml`.
3. `write_brief`: default output path now lands under real `~/.agents/tasks/...`.
4. `main`: default profile and machine-config lookup now use real HOME.

Before:
```py
home = Path.home()
```
After:
```py
home = real_user_home()
```

### `core/launchers/agent-launcher-discover.py`

Audited site is `SWITCH`.

Before:
```py
Path(os.environ.get("AGENT_LAUNCHER_DISCOVER_HOME", str(Path.home()))).expanduser()
```
After:
```py
Path(os.environ.get("AGENT_LAUNCHER_DISCOVER_HOME", str(real_user_home()))).expanduser()
```
Reason: fallback discovery root must search the operator's real home, not the current seat sandbox.

### `core/launchers/agent-launcher-fuzzy.py`

Audited site is `SWITCH`.

Before:
```py
Path(os.environ.get("REAL_HOME", os.environ.get("HOME", str(Path.home())))).expanduser()
```
After:
```py
Path(os.environ.get("REAL_HOME", str(real_user_home()))).expanduser()
```
Reason: launcher favorites/default roots should resolve from the operator's real HOME when running in a seat sandbox.

### `core/scripts/seat_claude_template.py`

Audited site is `SWITCH`.

Before:
```py
DEFAULT_ENGINEERS_ROOT = Path.home() / ".agents" / "engineers"
```
After:
```py
DEFAULT_ENGINEERS_ROOT = real_user_home() / ".agents" / "engineers"
```
Reason: seat templates must populate the real operator-managed engineer root.

### `core/migration/dynamic_common.py`

Audited site is `SWITCH`.

Before:
```py
session_root = Path(str(dynamic.get("session_root", str(Path.home() / ".agents" / "sessions")))).expanduser()
```
After:
```py
session_root = Path(str(dynamic.get("session_root", str(real_user_home() / ".agents" / "sessions")))).expanduser()
```
Reason: dynamic roster default session root must not nest under an ancestor sandbox home.

### `scripts/install.sh`

All audited `$HOME` sites are `KEEP`.

Reasoning:
- script captures incoming shell HOME into `CALLER_HOME` only for diagnostics
- script resolves `REAL_HOME`
- script exports `HOME="$REAL_HOME"` before constructing any persisted path

Added a short top-of-file comment documenting that contract. No `$HOME` site needed switching for ISSUE15.

## Tests

### New / updated ISSUE15 coverage

- `tests/test_agent_admin_session_real_home_switch.py`
  - proves launcher secret target and runtime identity dir resolve under `real_user_home()` even when `Path.home()` is sandboxed
- `tests/test_issue15_real_home_switch.py`
  - covers `ancestor_brief`, launcher discover fallback, launcher fuzzy defaults, `seat_claude_template`, and `dynamic_common`
- updated `tests/test_agent_admin_session_isolation.py`
  - expected runtime dir now anchors under real home, not patched sandbox `Path.home()`
- updated `tests/test_agent_admin_session_reseed.py`
  - expected sandbox runtime home now lives under real-home-based runtime root

### Targeted regression runs

- `pytest -q tests/test_agent_admin_session_real_home_switch.py tests/test_issue15_real_home_switch.py tests/test_ancestor_brief.py tests/test_launchers.py tests/test_seat_template_populated_after_profile_create.py tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py tests/test_memory_target_guard.py tests/test_transport_router.py`
- Result: `105 passed`

- `pytest -q tests/test_agent_admin_session_isolation.py tests/test_agent_admin_session_reseed.py`
- Result: `20 passed`

### Full sweep

- `pytest tests/ -q`
- Result in current branch state: `7 failed, 1875 passed, 2 xfailed`

Observed failing tests after ISSUE15 fixes:
- `tests/test_sandbox_claude_skills_are_real_dirs_not_symlinks.py::test_sandbox_has_only_role_plus_shared_skills`
- `tests/test_scan_project_smoke.py::test_clawseat_shallow_scan`
- `tests/test_scan_project_smoke.py::test_query_integration_dev_env`
- `tests/test_seat_template_populated_after_profile_create.py::test_project_bootstrap_populates_seat_claude_templates`
- `tests/test_send_delegation_report_identity.py::test_send_report_user_mode_passes_user_identity`
- `tests/test_send_delegation_report_identity.py::test_send_report_bot_mode_passes_bot_identity`
- `tests/test_send_delegation_report_identity.py::test_check_auth_uses_requested_identity`

The 4 ISSUE15-caused failures in `test_agent_admin_session_*` were fixed and no longer fail in the full sweep.

## Risks / Open Questions

- `pytest tests/ -q` is still red due to 7 current-branch failures outside the ISSUE15 real-home switch itself.
- `scripts/install.sh` remains intentionally on exported `$HOME`; this is safe only because the script rebases `HOME` to `REAL_HOME` before persisted-path work.
- `agent_admin_session.py` already had unrelated in-flight edits in this branch; ISSUE15 changes were limited to the real-home path anchors and matching regression tests.
