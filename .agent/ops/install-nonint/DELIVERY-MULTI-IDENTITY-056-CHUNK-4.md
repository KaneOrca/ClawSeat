# DELIVERY — MULTI-IDENTITY-056 CHUNK 4

## Summary

Threaded the project-scoped tool layer through runtime resolution, seat startup, launcher seeding, and install bootstrap.

This is the wiring chunk that makes `tools_isolation=per-project` actually influence the runtime environment seen by the seat processes.

## Changes

- [core/scripts/agent_admin_resolve.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_resolve.py)
  - `build_runtime()` now publishes `CLAWSEAT_PROJECT`, `CLAWSEAT_TOOLS_ISOLATION`, and `CLAWSEAT_PROJECT_TOOL_ROOT` for per-project bindings.
  - The runtime env still carries `AGENT_HOME` / `AGENTS_ROOT` so shared-real-home remains available as a compatibility path.

- [core/scripts/agent_admin_session.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_session.py)
  - `reseed_sandbox_user_tool_dirs()` now reseeds from the project tool root when the binding is per-project.
  - `start_engineer()` emits the project tool root warning if the project has been marked per-project but the root has not been initialized yet.
  - The launcher env now carries `CLAWSEAT_PROJECT_TOOL_ROOT` when the project is isolated.

- [core/launchers/agent-launcher.sh](/Users/ywf/ClawSeat/core/launchers/agent-launcher.sh)
  - `seed_user_tool_dirs()` now honors `CLAWSEAT_TOOLS_ISOLATION=per-project` and reads from the project tool root.
  - Claude, Codex, and Gemini runtime entrypoints all call the seed helper after the runtime HOME is selected.
  - The shared-real-home path is still preserved when isolation is not set to `per-project`.

- [scripts/install.sh](/Users/ywf/ClawSeat/scripts/install.sh)
  - The seat launch path passes `CLAWSEAT_PROJECT=$PROJECT` through to the launcher so the runtime can resolve the correct project tool layer.

- [tests/test_launcher_project_tool_seed.py](/Users/ywf/ClawSeat/tests/test_launcher_project_tool_seed.py)
  - Verifies that the launcher seeds project-local `.lark-cli`, `.gemini`, `.codex`, and iTerm2 state.

- [tests/test_agent_admin_session_project_tool_seed.py](/Users/ywf/ClawSeat/tests/test_agent_admin_session_project_tool_seed.py)
  - Verifies that session reseeding prefers the project tool root.
  - Verifies the missing-root warning path.

## 顺手修了

- The runtime now fails loudly on missing project-tool initialization instead of silently reusing the wrong identity layer.
- Root cause: a per-project binding without the project-local tool root would otherwise leave seats in a mixed state.
- Risk/impact: moderate but bounded. The behavior change is additive and still leaves shared-real-home as the fallback mode.

## Verification

- `bash -n /Users/ywf/ClawSeat/core/launchers/agent-launcher.sh`
- `python3 -m py_compile /Users/ywf/ClawSeat/core/scripts/agent_admin_resolve.py /Users/ywf/ClawSeat/core/scripts/agent_admin_session.py`
- `pytest /Users/ywf/ClawSeat/tests/test_launcher_project_tool_seed.py /Users/ywf/ClawSeat/tests/test_agent_admin_session_project_tool_seed.py -q` -> covered in the shared verification run

## Patch 历程

- 1st pass: thread project context through resolve and install launch.
- 2nd pass: let the launcher seed from project-local tool roots.
- 3rd pass: add the missing-root warning so migration failures are visible instead of silent.

No commit.
