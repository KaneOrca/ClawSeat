# ClawSeat Install Flow

## Decision Tree

1. First check whether there is already a workspace, seat, or TUI for the requested project/seat label.
2. If one exists, reuse it and report that the install is a resume/recovery path, not a fresh bootstrap.
3. If the user wants OpenClaw or Feishu to load ClawSeat, use the `clawseat` product skill or the OpenClaw plugin shell as the entrypoint.
4. If the user wants a local Claude/Codex runtime to load ClawSeat, use the relevant bundle first, then install the entry skills.
5. If the user is following the local first-run shortcut path, have them execute `/cs`.
6. If the user wants a new project outside the canonical install project, bootstrap a starter profile and run the harness.

## Required Environment

```sh
export CLAWSEAT_ROOT="$HOME/coding/ClawSeat"
```

If `CLAWSEAT_ROOT` is unset, check the current checkout before doing anything else.

## Project Bootstrap

```sh
PROJECT=my-project
PROFILE_TEMPLATE="$CLAWSEAT_ROOT/examples/starter/profiles/starter.toml"  # or install.toml / full-team.toml
cp "$PROFILE_TEMPLATE" "/tmp/${PROJECT}-profile-dynamic.toml"
python3 "$CLAWSEAT_ROOT/core/preflight.py" "$PROJECT"
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/bootstrap_harness.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml" \
  --project-name "$PROJECT" \
  --start
python3 "$CLAWSEAT_ROOT/core/skills/gstack-harness/scripts/render_console.py" \
  --profile "/tmp/${PROJECT}-profile-dynamic.toml"
```

- `starter.toml` creates a minimal frontstage entrypoint.
- `install.toml` creates the canonical `install` workspace with `koder`, `planner`, `builder-1`, and `reviewer-1`.
- `full-team.toml` creates `koder`, `planner`, `builder-1`, `reviewer-1`, `qa-1`, and `designer-1` workspaces in one bootstrap.
- Even with `full-team.toml`, `--start` still only auto-starts `koder`; other seats require explicit confirmation and launch.
- `clawseat` is the product path for OpenClaw/Feishu; `/cs` is the local-runtime exception path that counts as explicit approval to bootstrap or resume `install` and start `planner`.
- `qa-1` is not part of the default `/cs` first-launch roster; bring it up only for test / smoke / regression heavy chains, usually after the bridge or implementation lane has started.

## Entry Skill Install

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/install_entry_skills.py"
```

Then, inside OpenClaw/Feishu, invoke `clawseat`. Inside local Claude Code or Codex, you may run:

```text
/cs
```

`/cs` delegates to:

```sh
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/cs_init.py"
```

That wrapper will:

- ensure `/tmp/install-profile-dynamic.toml` exists from `examples/starter/profiles/install.toml`
- run preflight for `install`
- bootstrap or repair the canonical `install` workspace
- ensure every declared seat already has its managed scaffold (`session.toml`,
  isolated `runtime_dir`, workspace guide, `WORKSPACE_CONTRACT.toml`, `repos/`,
  and idle `TODO.md`) before dispatch begins
- start or resume `koder`
- start `planner`
- render the install console state
- then tell frontstage to finish the OpenClaw/Feishu bridge:
  ask the user for the group ID, keep `main` on `requireMention=true`, keep
  the project-facing `koder` account on `requireMention=false` by default,
  require an explicit project-binding confirmation, then delegate the smoke
  test to `planner`, tell the user `收到测试消息即可回复希望完成什么任务`, and
  bring up review in parallel
- after bootstrap, enter a configuration phase before normal task execution:
  finish project binding, Feishu bridge binding, provider/auth selection, API
  key setup, and base URL / endpoint configuration
- configuration should be split into configuration entry and configuration
  verification; do not collapse secret entry and validation into one opaque step
- once the project-group binding exists, planner decision gates and closeouts
  should use that same group through `OC_DELEGATION_REPORT_V1`; do not rely on
  the legacy auto-broadcast path as a control packet

## First-Launch Notes

- Fresh Claude seats may ask for OAuth login, workspace trust, or permission confirmation.
- Those prompts are normal onboarding, not install failures.
- A pre-existing TUI is not "new install" state; do not create a second project when the first seat is already present.
- For non-frontstage seats, require explicit confirmation before launching them.

## User And Agent Interaction Mode

- The agent should auto-run the deterministic setup steps: env check, preflight, starter profile preparation, bootstrap, and console verification.
- The agent should pause only for real user actions: CLI login, workspace trust, permission prompts, or moving to a host terminal that supports PTY/tmux.
- The agent should keep the user informed of which stage is active and whether `koder` is merely bootstrapped or already live.
- The agent must not silently launch `planner` or specialist seats during manual installation.
- `/cs` counts as an explicit user request to launch `planner` for the canonical `install` project.
- once `planner` is up, the agent should proactively ask for the Feishu group ID
  needed for the OpenClaw bridge; do not wait for the user to suggest group
  wiring
- once the user provides the group ID, the agent should first confirm whether
  the group binds the current project, another existing project, or a new
  project; only then should it delegate the bridge smoke test to `planner`,
  tell the user `收到测试消息即可回复希望完成什么任务`, and start
  `reviewer-1` in parallel when that seat exists
- if the current chain is verification-heavy, start `qa-1` in parallel with
  or immediately after `reviewer-1`; `qa-1` owns the smoke/regression lane
  rather than execution planning
- if configuration changes touch Feishu bridge settings, API keys, key
  rotation, base URL / endpoint values, or auth/provider bindings, treat that
  as configuration verification work and prefer launching `qa-1`
- `qa-1` should verify connectivity and behavior, not become the long-term
  owner of plaintext secrets
- when the closeout eventually comes back to frontstage, koder should read the
  linked delivery trail, reconcile the stage result, and update the project
  docs before summarizing to the user

## Common Failures

| Symptom | Meaning | Action |
|---|---|---|
| `Device not configured` | Host PTY/tmux limitation | Tell the user to run in a real terminal session |
| `CLAWSEAT_ROOT` missing | Environment not initialized | Export the repo root and rerun preflight |
| `dynamic profile not found` | Project profile missing | Create `/tmp/{project}-profile-dynamic.toml` from the starter profile |
| `tmux server` absent | tmux not running | Start a tmux server, then rerun preflight |
