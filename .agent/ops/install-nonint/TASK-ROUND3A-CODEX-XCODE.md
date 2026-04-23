# TASK: Round-3 — close round-2 open Q + fix launcher xcode config.toml render

**Assigned to**: codex-xcode
**Repo**: `/Users/ywf/ClawSeat` experimental branch

## Part A — Close round-2 open question: retire 1-arg wait-for-seat.sh interface

Codex-chatgpt's round-2 review flagged:
> "`wait-for-seat.sh:9` still advertises the 1-arg `<project-seat>` interface, but round-2 still leaves that form nonfunctional... 3 tests failing: `test_wait_for_seat_persistent_reattach.py:64`, `test_wait_for_seat_trust_detection.py:40`."

Decision (confirmed by planner): **officially retire the 1-arg form**. Only the 2-arg `<project> <seat>` form is supported going forward.

Required:
1. Update `wait-for-seat.sh` usage() to show only 2-arg form; reject 1-arg with explicit error message pointing operator at the 2-arg form
2. Update any docs (skill.md / ancestor-brief / README) that still reference 1-arg form
3. Update failing tests `test_wait_for_seat_persistent_reattach.py:64` and `test_wait_for_seat_trust_detection.py:40` to use 2-arg form; verify they pass
4. All other 65 round-2 tests still pass

## Part B — Fix #17: launcher `--auth xcode` doesn't render config.toml

**Observed failure**: Planner manually relaunched reviewer with `--auth xcode`. Codex CLI hit `api.openai.com` (default OpenAI endpoint) and 401'd because token is xcode.best-only. Root cause: launcher's xcode branch only sets `OPENAI_BASE_URL` env var, but codex CLI requires `[model_providers.xcodeapi]` section in `config.toml` + `model_provider = "xcodeapi"` top-level.

**Evidence** (`/Users/ywf/clawseat/core/launchers/agent-launcher.sh:768-830`):
- Line 784-799: `custom` auth branch correctly renders config.toml with `[model_providers.customapi]` + `experimental_bearer_token`
- Line 800-813: `xcode` auth branch only sources env + creates `auth.json` via `codex login --with-api-key`. NEVER renders config.toml.
- Line 830: `exec codex --dangerously-bypass-approvals-and-sandbox -C "$workdir"` — no `-c model_provider=xcodeapi`

Working reference config (from codex-xcode's own runtime): `/Users/ywf/.agent-runtime/identities/codex/xcode_api-codex-xcode-api-clawseat-20260423-204444/codex-home/config.toml`:
```toml
model_provider = "xcodeapi"
model = "gpt-5.4"
model_reasoning_effort = "medium"
service_tier = "fast"
approvals_reviewer = "user"

[model_providers.xcodeapi]
name = "xcodeapi"
base_url = "https://xcode.best/v1"
wire_api = "responses"
experimental_bearer_token = "<token from secret file>"
```

Required:
1. Extend launcher xcode branch (around line 800+) to render config.toml with `[model_providers.xcodeapi]` including base_url (from provider_default_base_url) + experimental_bearer_token (from `$OPENAI_API_KEY`)
2. Write `model_provider = "xcodeapi"` top-level OR pass `-c model_provider=xcodeapi` at exec time (either works)
3. Make sure `rm -f "$CODEX_HOME/config.toml"` happens before rendering (so re-symlinked user config is removed)
4. Keep config.toml's project trust_level entries if desirable (optional)

## Tests

New/extended tests:
1. `test_launcher_xcode_config_rendering` — verify launcher writes `[model_providers.xcodeapi]` with correct base_url and token substituted from secret file
2. `test_launcher_xcode_model_provider_selected` — verify either config.toml `model_provider = "xcodeapi"` OR exec cmd contains `-c model_provider=xcodeapi`
3. Round-2 tests still pass (65)
4. 3 wait-for-seat tests updated for 2-arg form pass

## Deliverable

1. Patches to `wait-for-seat.sh`, `agent-launcher.sh`, docs, tests
2. Delivery report `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND3-XCODE-CONFIG-AND-1ARG-RETIRE.md`
3. Send summary via `send-and-verify.sh` to `agent-launcher-codex-chatgpt-20260423-230652` for review
4. echo `ROUND3A_DONE`

## Constraints
- Don't run `bash scripts/install.sh` end-to-end (install state is live with user in Phase-A)
- Don't touch memory/qa/designer/builder seat state; this round doesn't deal with #14 seat isolation (that's codex-chatgpt's round-3b)
