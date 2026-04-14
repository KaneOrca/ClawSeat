## Cartooner Adapter

This adapter packages the ClawSeat-facing pieces needed to run `cartooner`
without moving the full Cartooner product source tree into ClawSeat core.

Contents:

- `profiles/cartooner.toml`
  - adapter profile pointing at the external Cartooner consumer repo
- `skills/cartooner-koder/`
  - project wrapper skill for the Cartooner `koder` seat
- `scripts/check-cartooner-status.sh`
  - adapter-specific patrol entrypoint
- `scripts/patrol_supervisor.py`
  - adapter-specific reminder helper

The consumer repo remains external. In this local setup the adapter assumes
the consumer checkout lives at `~/coding/cartooner` by default. Set
`CARTOONER_REPO_ROOT` to override that location on another machine.
