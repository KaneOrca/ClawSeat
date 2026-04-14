# Patrol Playbook

Do not invent a new patrol flow. Prefer:

- `{CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/render_console.py`
- `{CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/patrol_loop.py`
- `{CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/verify_handoff.py`
- `{CLAWSEAT_ROOT}/adapters/projects/cartooner/scripts/check-cartooner-status.sh`

For the Cartooner consumer project,
`{CLAWSEAT_ROOT}/adapters/projects/cartooner/scripts/check-cartooner-status.sh`
is the preferred patrol entrypoint. The lower-level fallback is:

- `{CLAWSEAT_ROOT}/core/shell-scripts/check-engineer-status.sh`

Important reminders:

- routine heartbeat stays lightweight: run scripts first, then read docs only
  if the script facts disagree
- routine heartbeat should not begin by re-reading `KODER.md` or the full
  project overview
- routine heartbeat does not enter plan mode or restate the full project
  context
- `check-cartooner-status.sh` is the project patrol entrypoint
- `check-engineer-status.sh` is the generic lower-level script
- reuse the current ClawSeat method, not the old `workspace-warden` topology
- legacy `.tasks/PROTOCOL.md` style material is historical reference only
- the live project truth remains the consumer repo's `.tasks/...` files and
  `cartooner-engineer-*` sessions
