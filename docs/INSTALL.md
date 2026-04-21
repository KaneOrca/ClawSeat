# ClawSeat Install Notes

## Path Contract

ClawSeat profile files may contain portable placeholders instead of host-local
absolute paths.

Supported forms:

- `{CLAWSEAT_ROOT}`: absolute path to the ClawSeat repository root
- `~`: the current user's home directory

## Required Environment

Before running profile-driven helpers, export the ClawSeat root:

```sh
export CLAWSEAT_ROOT=/path/to/ClawSeat
```

Typical example:

```sh
export CLAWSEAT_ROOT="/path/to/ClawSeat"
```

## Role-First Bootstrap

New projects should default to role-first seat ids such as `planner`,
`builder-1`, and `reviewer-1`.

Shipped starter profiles now come in five tiers:

- `examples/starter/profiles/starter.toml`
  - frontstage-only bootstrap
  - creates a minimal `koder` entrypoint first
- `examples/starter/profiles/install-with-memory.toml`
  - canonical local `/cs` bootstrap profile
  - creates `memory`, `koder`, `planner`, `builder-1`, and `reviewer-1`
  - intended for the first post-install `install` project
- `examples/starter/profiles/install-openclaw.toml`
  - canonical OpenClaw bootstrap profile
  - binds `koder` to the current OpenClaw agent instead of a tmux session
  - starts backend runtime seats `memory`, `planner`, `builder-1`, and `reviewer-1`
- `examples/starter/profiles/install.toml`
  - legacy local memory-less variant
  - creates `koder`, `planner`, `builder-1`, and `reviewer-1`
- `examples/starter/profiles/full-team.toml`
  - predeclares `koder`, `planner`, `builder-1`, `reviewer-1`, `qa-1`, and `designer-1`
  - creates all six personal workspaces during bootstrap
  - still defaults to `koder` as the only auto-start seat

Recommended first-run path:

1. In OpenClaw or Feishu-facing runtimes, load the `clawseat` skill/plugin and
   let it route through the OpenClaw bootstrap path.
   The canonical `install` bootstrap now auto-seeds
   `~/.agents/profiles/install-profile-dynamic.toml` from the shipped `install-openclaw.toml`
   profile when the machine is starting from a blank state.
2. In Claude Code or Codex local runtimes, install the entry skills with
   `python3.11 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"`
3. Only in those local runtimes, use `/cs` as the convenience alias that
   creates or resumes the canonical `install` project and starts `planner`

Command examples use `python3.11` explicitly. On macOS, `python3` is often 3.9
and lacks `tomllib`, which several install helpers require.

## Heartbeat Modes

`heartbeat_transport` selects how the frontstage `heartbeat_owner` is reached.
`runtime_seats` selects which seats get runtime/session records for the current
profile. Those two fields are what separate the canonical local `/cs` flow from
the canonical OpenClaw overlay flow.

| Profile | `heartbeat_transport` | `runtime_seats` shape | `koder` behavior |
|---|---|---|---|
| `install-with-memory.toml` | `tmux` | local runtime seats include `koder`, `memory`, and the backend seats | `koder` runs as a tmux seat |
| `install-openclaw.toml` | `openclaw` | backend runtime seats exclude `koder`; `memory` and specialist seats still run in tmux | `koder` stays frontstage as the chosen OpenClaw agent |

For dynamic-roster profiles, keep bootstrap minimal:

```toml
[dynamic_roster]
enabled = true
bootstrap_seats = ["koder"]
default_start_seats = ["koder"]
compat_legacy_seats = false
```

This makes fresh bootstraps frontstage-only with role-first naming.
Set `compat_legacy_seats = true` only for migrated projects that still use
legacy `engineer-*` seat names.

## Expansion Rules

- `{CLAWSEAT_ROOT}` is expanded by the profile loader in
  `core/skills/gstack-harness/scripts/_common.py`
- `~` is expanded through Python `Path.expanduser()`
- If `CLAWSEAT_ROOT` is not exported, the loader falls back to the current
  repository root when it is executing inside this checkout

This contract lets shipped `profile.toml` files stay portable across machines
without reintroducing hardcoded developer-home paths.

## Choosing auth mode (claude seats)

B1 replaced the two-choice `oauth`/`api` prompt with six canonical
`(auth_mode, provider)` combinations, resolved by
`core/skills/clawseat-install/scripts/resolve_auth_mode.py`. Pick per
operator intent:

| If you want… | Choose | Secret location |
|---|---|---|
| Share one token across all seats, avoid Keychain popups | `oauth_token` (1) | `~/.agents/.env.global` — `CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-…` |
| Isolate each seat with its own Anthropic Console key | `api` + `anthropic-console` (2) | `~/.agents/secrets/claude/anthropic-console.env` (0o600) |
| Route to MiniMax's Anthropic-compatible endpoint | `api` + `minimax` (3) | `~/.agents/secrets/claude/minimax.env` |
| Route to xcode.best aggregator | `api` + `xcode-best` (4) | `~/.agents/secrets/claude/xcode-best.env` |
| Multiplex providers at runtime via CCR proxy | `ccr` (5) | no seat-side secret; ccr holds keys |
| Legacy Keychain OAuth (only if none of the above fits) | `oauth` (6) | no secret file; warns about Keychain popups |

**Default changed on fresh install (B1):** earlier installs defaulted
`auth_mode="oauth"` silently; B1's interview defaults to `oauth_token`
because it avoids the upstream Keychain-expiry popup
(`anthropics/claude-code#43000`). Existing seats are unaffected — A1's
migration script handles those separately.

### Non-interactive installs

Drop a batch config at `~/.agents/install-config.toml` (see
`examples/starter/install-config.toml.example`) with one block per seat:

```toml
[seats.builder-2]
auth_mode = "api"
provider = "anthropic-console"
```

Then `resolve_auth_mode.py --seat builder-2` resolves without prompting.
For CI / smoke tests, add `--non-interactive` so missing seat blocks
fail fast rather than blocking on a prompt.

### Shape validation

- `oauth_token` → expects `sk-ant-oat01-…`
- `api` + `anthropic-console` → expects `sk-ant-api03-…`
- `api` + `minimax` / `xcode-best` → free-form (vendors publish their own shapes)

On paste failure the resolver re-prompts up to 3× before aborting. Keys
are written with `0o600` and pre-existing files with looser modes are
upgraded in place.

See `docs/auth-modes.md` (A1) for per-mode runtime details.
