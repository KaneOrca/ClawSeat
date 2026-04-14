# ClawSeat Codex Bundle

This is a thin Codex distribution shell for ClawSeat.

Use it to point Codex at the core ClawSeat runtime while keeping protocol and
seat logic in `core/` and `adapters/`.

Read in this order:

1. `{CLAWSEAT_ROOT}/core/skills/gstack-harness/SKILL.md`
2. project adapter skill when needed
   Example:
   `{CLAWSEAT_ROOT}/adapters/projects/cartooner/skills/cartooner-koder/SKILL.md`
3. `{CLAWSEAT_ROOT}/shells/codex-bundle/adapter_shim.py`

Bundle boundary:

- allowed: agent declaration, bootstrap wiring, adapter loading
- not allowed: dispatch protocol logic, handoff semantics, patrol semantics,
  workspace-contract logic

Runtime note:

- Codex uses the tmux-cli harness adapter from
  `{CLAWSEAT_ROOT}/adapters/harness/tmux-cli/adapter.py`
- adapter contract lives at `{CLAWSEAT_ROOT}/core/harness_adapter.py`
