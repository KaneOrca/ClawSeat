# Auth modes for Claude seats

ClawSeat supports four `auth_mode` values for `tool=claude`. Each maps to
a different credential source; choose based on the seat's risk profile and
operational constraints.

## Modes

### `oauth` (legacy)

The default Anthropic OAuth flow. Credentials are stored in the macOS
Keychain. **Problem:** each seat runs in an isolated sandbox HOME, so
every seat has its own Keychain slot. When the session expires, an
interactive popup blocks the seat until the operator clicks through — not
dismissable from automation.

**Avoid for new seats.** Existing `oauth` seats should be migrated to
`oauth_token` or `api/anthropic-console`.

### `oauth_token`

Long-lived (~1 year) token obtained via `claude setup-token` on the
operator host. Stored in a secret file as `CLAUDE_CODE_OAUTH_TOKEN`.
Bypasses the Keychain entirely — no popup on restart.

**Secret file** must contain:
```
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
```

Obtain via:
```
claude setup-token
# Copy the printed token, then:
echo 'export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...' >> ~/.agents/.env.global
```

### `api` + `anthropic-console` provider

Direct call to `api.anthropic.com` using an `ANTHROPIC_API_KEY` created
in the Anthropic Console UI under the "Claude Code" scoped-role. Distinct
from Developer API keys — this key is not subject to Keychain or OAuth
expiry.

**Secret file** (`~/.agents/secrets/claude/anthropic-console.env`) must contain:
```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Create via Anthropic Console → API Keys → New key (scoped role: Claude Code):
```
mkdir -p ~/.agents/secrets/claude
echo 'ANTHROPIC_API_KEY=sk-ant-api03-...' > ~/.agents/secrets/claude/anthropic-console.env
chmod 600 ~/.agents/secrets/claude/anthropic-console.env
```

### `ccr` + `ccr-local` provider

Routes through a local Claude Code Router proxy (`ccr start`). The proxy
holds all upstream provider keys and multiplexes them per-request. The
seat injects `ANTHROPIC_BASE_URL=http://127.0.0.1:3456` and a dummy auth
token — no secret file required on the seat side.

Use for seats that need provider diversity or when upstream API keys are
managed centrally by CCR.

## Decision guide

| Situation | Recommended mode |
|-----------|-----------------|
| New claude seat, Anthropic direct | `oauth_token` |
| Seat needs isolation / diversity | `api/anthropic-console` |
| Multi-provider routing via CCR | `ccr/ccr-local` |
| Legacy seat (pre-A1) | Migrate with `migrate-seat-auth` |

## Migration guide (A1)

To migrate existing `oauth` seats, use `migrate-seat-auth`:

```bash
# Step 1: set up secrets
claude setup-token
echo 'export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...' >> ~/.agents/.env.global

# For anthropic-console seats:
mkdir -p ~/.agents/secrets/claude
echo 'ANTHROPIC_API_KEY=sk-ant-api03-...' > ~/.agents/secrets/claude/anthropic-console.env
chmod 600 ~/.agents/secrets/claude/anthropic-console.env

# Step 2: preview
python3.11 core/scripts/migrate_seat_auth.py plan
python3.11 core/scripts/migrate_seat_auth.py apply --dry-run

# Step 3: apply
python3.11 core/scripts/migrate_seat_auth.py apply

# Step 4: restart seats to pick up new env
tmux kill-session -t install-koder-claude   # repeat for each seat
```

See also `docs/ARCHITECTURE.md §3j`.
