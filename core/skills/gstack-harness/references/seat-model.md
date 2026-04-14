# Seat Model

The harness runtime separates **stable seat identity** from **role semantics**.

## Required seat fields

- `seat_id`
- `role`
- `skills`
- `tool`
- `auth_mode`
- `provider`

## Supported runtime matrix

- `claude` + `oauth`: `anthropic`
- `claude` + `api`: `xcode-best`, `minimax`
- `codex` + `oauth`: `openai`
- `codex` + `api`: `xcode-best`
- `gemini` + `oauth`: `google`

Unsupported combinations should be treated as invalid configuration, not as a
runtime surprise to discover later during launch.

## Provider endpoint rules

- `claude` + `api` + `xcode-best`
  - use `ANTHROPIC_BASE_URL=https://xcode.best`
  - this is the Claude-specific xcode endpoint
- `codex` + `api` + `xcode-best`
  - use `https://api.xcode.best/v1` in the Codex provider config
  - this is the GPT-5.4 / OpenAI-compatible xcode endpoint
- do not assume one `xcode-best` URL works for every CLI; the endpoint is
  tool-specific provider configuration

## Project-local runtime overrides

- seat identity stays stable across projects
- tool, auth mode, and provider may vary by project
- the preferred place to record those differences is the project profile via
  `seat_overrides`, not ad hoc post-bootstrap edits
- recommended heuristic:
  - large / multi-surface projects: `engineer-b = claude`, `engineer-e = gemini`
  - pure frontend projects: `engineer-b = gemini`, `engineer-e` stays optional
    unless design work is active

## Configuration workflow

Frontstage must configure seats through the runtime tooling, not by editing
session files ad hoc.

- if the tool/runtime changes, use `agent-admin session switch-harness`
- if only auth mode or provider changes on the same tool, use
  `agent-admin engineer rebind`
- both paths re-render the seat workspace so the generated guide and
  `WORKSPACE_CONTRACT.toml` match the selected runtime

After the configuration change:

1. start or restart the seat
2. make the seat re-read its workspace guide
3. make the seat re-read `WORKSPACE_CONTRACT.toml`
4. stamp `scripts/ack_contract.py` when you need durable proof that the reread happened

This is how frontstage ensures the seat remembers its role, seat boundary, and
communication protocol after a runtime change.

If you batch-launch with a headless start path such as `--no-open-window` or
`--defer-window-refresh`, the seat is running but not yet visible in the
project tabs. Finish the batch with one project-window refresh before treating
the seat as operator-visible.

## Recovery workflow

When a Claude seat stops unexpectedly, do not jump straight to a fresh start.

Prefer this order:

1. check whether the original workspace still exists
2. check whether the original Claude runtime home still exists
3. check whether a prior Claude session record still exists
4. if all three exist, recover the seat on that same runtime first
5. only if recovery fails, do a fresh start and treat it as a new live session

For Claude recovery, keep these pieces aligned:

- workspace directory
- runtime `HOME`
- runtime `XDG_*` directories
- prior Claude session id, when available

Why this matters:

- a fresh Claude runtime can fall back into onboarding/login prompts even when
  OAuth credentials still exist
- preserving the original runtime home is often what keeps Claude's local seat
  state, trust prompts, and conversation/session memory intact

`ack_contract.py` is also the best future hook target:

- manual operator flow: run it after confirming the seat re-read the contract
- seat self-check flow: let the seat call it after re-reading
- hook flow: attach it to a post-start / post-reread automation once the
  runtime can reliably tell that the contract was actually re-read

## Authority flags

- `human_facing`
- `active_loop_owner`
- `dispatch_authority`
- `patrol_authority`
- `unblock_authority`
- `escalation_authority`
- `remind_active_loop_owner`
- `review_authority`
- `qa_authority`
- `design_authority`

## Canonical roles

- `frontstage-supervisor`
- `planner-dispatcher`
- `builder`
- `reviewer`
- `qa`
- `designer`

## Operating rule

- frontstage-supervisor owns intake, patrol, approvals, confirmations, and
  unblock actions
- frontstage-supervisor also owns seat launch orchestration and operator
  window/tab composition for the project
- planner-dispatcher owns execution decisions and next-hop routing
- specialists do not become ad hoc frontstage agents
- when frontstage is about to launch a specialist/planner seat, it must first
  get user confirmation on the selected harness/runtime and model choice
- default to Simplified Chinese for human-readable task titles, objectives,
  reminders, closeout summaries, and user-facing handoff prose; preserve exact
  protocol keys, commands, file paths, API fields, and code identifiers as-is

## Cartooner mapping

- `koder` -> `frontstage-supervisor`
- `engineer-b` -> `planner-dispatcher`
- `engineer-a` -> `builder`
- `engineer-c` -> `reviewer`
- `engineer-d` -> `qa`
- `engineer-e` -> `designer`
