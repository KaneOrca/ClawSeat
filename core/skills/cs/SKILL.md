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
- profile template is `{CLAWSEAT_ROOT}/examples/starter/profiles/install.toml`
- the install workspace roster is `koder + planner + builder-1 + reviewer-1`
- `koder` is bootstrapped or resumed first
- `planner` is then explicitly started so it can take over the install chain
- after `planner` is live, `koder` should immediately follow up with the user for the Feishu/OpenClaw bridge:
  ask the user to create or identify the group, report the group ID, confirm whether the group should bind the current project / another existing project / a new project, keep `main` on `requireMention=true`, and keep the project-facing `koder` account on `requireMention=false` by default
- once the user sends the group ID and confirms the project binding, `koder` should immediately ask `planner` to run the bridge smoke test, tell the user `收到测试消息即可回复希望完成什么任务`, and bring up `reviewer-1` in parallel when that seat exists
- after the group is bound, planner should treat that same group as the user-visible bridge for `OC_DELEGATION_REPORT_V1` closeouts; keep the legacy auto-broadcast path disabled unless explicitly opted in

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

- Treat `/cs` itself as the user's explicit approval to create or resume the canonical `install` project and launch `planner`.
- Reuse an existing `install` workspace or live TUI if one already exists.
- Do not create a parallel `install-*` project when the canonical workspace is already present.
- Once `planner` is up, proactively ask the user for the Feishu group setup instead of waiting for them to bring it up:
  main agent 拉群并汇报 group ID；无需 user open_id。
- After the user provides the group ID, require an explicit project-binding confirmation before planner smoke tests begin.
- Treat Claude OAuth, workspace trust, and permissions prompts as normal manual onboarding.
- If tmux or PTY support is unavailable, stop cleanly and hand the next terminal command back to the user.

## References

- `{CLAWSEAT_ROOT}/core/skills/clawseat-install/SKILL.md`
- `{CLAWSEAT_ROOT}/docs/INSTALL_GUIDE.md`
