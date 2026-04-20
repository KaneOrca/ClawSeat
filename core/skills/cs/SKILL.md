---
name: cs
description: Local post-install ClawSeat convenience entrypoint. Use `/cs` only in local Claude/Codex runtimes after ClawSeat is already installed to bootstrap or resume the canonical `install` project and start `planner`.
---

# ClawSeat Init

`/cs` is the thin local shortcut after ClawSeat is installed.

It is not the canonical cross-runtime product entry. In OpenClaw or Feishu
environments, the preferred entry is `clawseat`, not `/cs`.

Keep it thin. This skill does not define a second bootstrap flow. It delegates to
`clawseat-install` and uses the canonical install profile.

## Default Behavior

- project name is fixed to `install`
- profile template is `{CLAWSEAT_ROOT}/examples/starter/profiles/install-with-memory.toml`
- the local `/cs` profile uses `heartbeat_transport = "tmux"`
- the install workspace roster is `memory + koder + planner + builder-1 + reviewer-1`
- `koder` is bootstrapped or resumed first
- `planner` is then explicitly started so it can take over the install chain
- after `planner` is live, follow the Feishu bridge setup and seat launch flow
  described in `clawseat-install/SKILL.md` and
  `clawseat-install/references/feishu-bridge-setup.md`

## Run

1. Confirm `CLAWSEAT_ROOT` points at the ClawSeat checkout.
2. Run:

   ```bash
   python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/cs_init.py"
   ```

3. Report whether the result was:
   - a fresh bootstrap
   - a resume of an existing `install` workspace/TUI
   - a normal manual onboarding stop such as OAuth or workspace trust

## Interaction Rules

- Treat `/cs` itself as the user's explicit approval to create or resume the
  canonical `install` project and launch `planner`.
- Reuse an existing `install` workspace or live TUI if one already exists.
- Do not create a parallel `install-*` project when the canonical workspace is
  already present.
- Treat Claude OAuth, workspace trust, and permissions prompts as normal manual
  onboarding.
- If tmux or PTY support is unavailable, stop cleanly and hand the next terminal
  command back to the user.
- For all post-planner steps (Feishu bridge, seat config, specialist launch),
  follow the rules in `clawseat-install/SKILL.md`.

## References

- `{CLAWSEAT_ROOT}/core/skills/clawseat-install/SKILL.md`
- `{CLAWSEAT_ROOT}/core/skills/clawseat-install/references/feishu-bridge-setup.md`
- `{CLAWSEAT_ROOT}/docs/INSTALL_GUIDE.md`
