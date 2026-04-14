# Launch And Layout

`koder` owns:

- engineer launch
- the project operator window / tab layout

Before starting any non-frontstage seat, `koder` must first summarize to the
user:

1. the harness/profile in use
2. the target seat and role
3. the selected tool/runtime
4. the auth mode and provider/model family

Only after user confirmation may `koder` launch that seat. For ClawSeat's
`gstack-harness`, the preferred flow is:

1. run `start_seat.py` without `--confirm-start` to produce the launch summary
2. confirm the choice with the user
3. rerun with `--confirm-start`

If the seat must be reconfigured before launch, do that first:

1. tool/runtime change
   - `python3 {CLAWSEAT_ROOT}/core/scripts/agent_admin.py session switch-harness <seat> <tool> <mode> <provider> --project cartooner`
2. auth/provider-only change on the same tool
   - `python3 {CLAWSEAT_ROOT}/core/scripts/agent_admin.py engineer rebind <seat> --project cartooner <mode> <provider>`

These commands re-render the seat workspace contract. After the seat is
started, `koder` should explicitly make that seat re-read:

- its generated workspace guide (`CLAUDE.md`, `GEMINI.md`, or `AGENTS.md`)
- `WORKSPACE_CONTRACT.toml`
- and, when durable proof is needed, stamp
  `python3 {CLAWSEAT_ROOT}/core/skills/gstack-harness/scripts/ack_contract.py --profile {CLAWSEAT_ROOT}/adapters/projects/cartooner/profiles/cartooner.toml --seat <seat>`

Do not consider the seat ready just because tmux is running. The seat is only
ready once it is on the correct runtime and has re-read the regenerated
contract that contains role focus, project seat map, seat boundary, and
communication protocol.

If a Claude seat used to work and only later stopped, prefer recovery over
fresh start:

1. reuse the original workspace
2. reuse the original Claude runtime home / XDG dirs
3. resume the original Claude session if a session id is available
4. only if that fails, do a fresh start

Do not tell the user a fresh Claude session is the same session just because
the seat id matches. A fresh start may preserve durable docs, but it does not
preserve the old live pane.

After a seat is launched, `koder` also owns the operator layout update:

1. refresh the project window
2. ensure the new seat appears as a tab in the project's canonical order
3. avoid spawning long-lived ad hoc windows when the project already uses the
   one-project-one-window tabs model
