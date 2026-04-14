# Codex Bundle

This bundle is the Codex distribution shell for ClawSeat.

Contents:

- `AGENTS.md`: Codex-facing bundle declaration
- `adapter_shim.py`: minimal bootstrap wiring to the core adapter contract and
  tmux-cli implementation

Use this bundle to make Codex load ClawSeat as an agent configuration surface
without moving any runtime protocol into `shells/`.

Install/setup conversations should start from
`{CLAWSEAT_ROOT}/core/skills/clawseat-install/SKILL.md` before loading the
runtime harness details. That skill owns the install flow and the user/agent
handoff rules for onboarding, tmux, and first-launch prompts. After install,
the preferred first entry command is `/cs` in runtimes that expose slash
skills, or `$cs` where the runtime invokes skills by name.

Environment:

- set `CLAWSEAT_ROOT=/path/to/ClawSeat`
- optional: `AGENTS_ROOT`, `SESSIONS_ROOT`, `WORKSPACES_ROOT`

Project-specific behavior remains in `core/skills/`, `core/scripts/`, and
`adapters/projects/`.
