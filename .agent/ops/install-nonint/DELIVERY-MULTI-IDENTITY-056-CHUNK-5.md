# DELIVERY — MULTI-IDENTITY-056 CHUNK 5

## Summary

Added `agent_admin project switch-identity` so operators can explicitly move a project onto a new Feishu sender identity or a new Gemini / Codex account marker.

The command records the new identity in `PROJECT_BINDING.toml`, forces `tools_isolation=per-project`, and reseeds the active seats so the runtime layer picks up the new project-local identity state.

## Behavioral contract

- `project switch-identity` is a binding metadata update plus sandbox reseed. It is not a credential migration tool.
- It does not call native login CLIs such as `lark-cli auth`.
- It does not mutate per-project credential files such as `.gemini/oauth_creds.json` or `.codex/auth.json`.
- Operator prerequisite: prepare the project tool root first, then ensure the intended credential already exists under `~/.agent-runtime/projects/<project>/...`.
- Recommended workflow:
  1. `agent_admin project init-tools <project> --from real-home` or `--source-project <other-project>`
  2. verify or replace the credential in the project tool root
  3. run `agent_admin project switch-identity <project> --tool ... --identity ...`

## Changes

- [core/scripts/agent_admin_crud.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_crud.py)
  - Added `project_switch_identity()`.
  - Supports `feishu`, `gemini`, and `codex` identity targets.
  - Updates the correct binding field for each tool.
  - Keeps the legacy `feishu_bot_account` alias in sync when the Feishu identity changes.
  - Supports `--dry-run`.
  - Reseeds every engineer seat after a real update.
  - Added an explicit docstring that documents the non-migration contract.

- [core/scripts/agent_admin_parser.py](/Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py)
  - Added the `agent_admin project switch-identity <project>` CLI.
  - Wired the `--tool`, `--identity`, and `--dry-run` arguments.

- [docs/INSTALL.md](/Users/ywf/ClawSeat/docs/INSTALL.md)
  - Added the operator-facing `init-tools -> verify credential -> switch-identity` workflow.
  - Explicitly documents that `switch-identity` does not move credentials or call native auth CLIs.

- [tests/test_agent_admin_project_switch_identity.py](/Users/ywf/ClawSeat/tests/test_agent_admin_project_switch_identity.py)
  - Covers Feishu, Gemini, and Codex updates.
  - Covers the dry-run path.
  - Verifies the binding flips to `per-project` and that reseeding is triggered on write.

## 顺手修了

- Feishu identity updates now keep the legacy account alias consistent with the new sender field.
- Root cause: project identity switching needed a canonical write path, not a manual binding edit, so the runtime could reseed deterministically.
- Risk/impact: moderate. The command mutates project binding state, but only through an explicit operator action.

## Verification

- `python3 -m py_compile /Users/ywf/ClawSeat/core/scripts/agent_admin_crud.py /Users/ywf/ClawSeat/core/scripts/agent_admin_parser.py`
- `pytest /Users/ywf/ClawSeat/tests/test_agent_admin_project_switch_identity.py -q` -> covered in the shared verification run

## Patch 历程

- 1st pass: add the explicit identity-switch command.
- 2nd pass: keep Feishu legacy aliases synchronized.
- 3rd pass: reseed seats so the change becomes visible in the runtime layer immediately.

No commit.
