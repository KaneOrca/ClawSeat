# TASK: Round-3b (REVISED) — start-engineer exit code + seat template copy architecture

**Assigned to**: codex-chatgpt
**Replaces**: `TASK-ROUND3B-CODEX-CHATGPT.md` (operator interrupted previous run)
**Repo**: `/Users/ywf/ClawSeat` experimental branch

---

## Why this revision

Previous task's Part B asked you to fix the seat `.claude/` sandbox isolation by:
- NOT symlinking `.claude/settings.json` and `.claude/skills` to user-level
- Instead, reading each engineer profile's `skills = [...]` array and symlinking only those role-specific skills

**Problem discovered mid-task**:
```
$ for seat in planner builder reviewer qa designer memory; do
    cat ~/.agents/engineers/$seat/engineer.toml | grep '^skills'
  done
skills = []
skills = []
skills = []
skills = []
skills = []
# (memory seat is missing engineer.toml entirely)
```
**All 6 engineer profiles have `skills = []` (empty).** So "read profile's skills array and resolve to skill paths" yields nothing. The fix would produce seats with ZERO skills loaded, which is worse than the current state (too many skills).

Also: the `planner` seat is symptomatic of this too — operator observed planner doesn't know its role in the 6-pane grid, same as qa/designer/reviewer.

**New architecture** (decided by planner Claude):

> Copy the role template directly into each seat's workspace at creation time.
> Launcher then `cp`s from the per-seat prepared template into the sandbox `.claude/`.
> No runtime symlink games, no dynamic lookup from empty arrays.

---

## Part A — UNCHANGED: Fix #16 `agent_admin session start-engineer` silent failure for codex+api+xcode-best

**Observed**: Planner ran `agent_admin session start-engineer reviewer --project install`. Engineer profile has `tool=codex, auth_mode=api, provider=xcode-best`. `start-engineer` exited with 0 and printed "install-reviewer-codex" as the session name, but tmux session never appeared.

Direct launcher invocation reveals the bug:
```bash
$ bash agent-launcher.sh --headless --tool codex --auth api --dir ... --session ...
error: unsupported auth 'api' for tool 'codex'
```

Launcher only supports `codex + oauth|xcode|custom|chatgpt`, NOT `codex + api`.

`start-engineer`'s mapping from engineer profile (`auth_mode=api, provider=xcode-best`) to launcher args (`--auth <something>`) is either:
- Not happening at all (passes `--auth api` literally → launcher rejects)
- Happening wrong (maps to unsupported combo)
- Happening correctly but launcher returns non-zero and start-engineer swallows it

Root cause investigation:
1. Read `core/scripts/agent_admin_session.py` (seat start-engineer code path)
2. Find where engineer profile's `auth_mode + provider` → launcher `--auth` mapping happens
3. For `codex+api+xcode-best`, the correct launcher arg is `--auth xcode` (empirically verified — planner ran `--auth xcode` and it launched)
4. The mapping likely needs: `(codex, api, xcode-best) → (launcher --auth xcode, env CLAWSEAT_PROVIDER=xcode-best)`
5. ALSO: launcher exit code should propagate through start-engineer so silent failures don't happen

Required:
1. Fix the mapping for `codex + api + xcode-best` → `--auth xcode` (and any similar combos)
2. Make start-engineer print the launcher command it's running (stderr/debug mode) so operator can see what went wrong
3. Make start-engineer return non-zero if launcher returns non-zero
4. New test `tests/test_agent_admin_start_engineer_codex_mapping.py` covering the codex+api+xcode-best mapping

---

## Part B — NEW: Template-copy architecture (replaces old symlink approach)

### B.1 Define the seat → skill template mapping

Canonical mapping (planner's decision):

| seat | role skill template (in `core/skills/`) |
|------|------------------------------------------|
| ancestor | `clawseat-ancestor` |
| planner | `planner` |
| memory | `memory-oracle` |
| builder | `clawseat` (placeholder — dedicated skill to be added in round-4) |
| reviewer | `clawseat` (placeholder — dedicated skill to be added in round-4) |
| qa | `clawseat` (placeholder — dedicated skill to be added in round-4) |
| designer | `clawseat` (placeholder — dedicated skill to be added in round-4) |

Shared skills **every seat** gets (in addition to role skill):
- `clawseat` (framework basics)
- `gstack-harness` (dispatch/send-and-verify/heartbeat protocol — seats need this to communicate)
- `tmux-basics`

Store this mapping in one place — recommended: `core/scripts/seat_skill_mapping.py` as a small module exporting `SEAT_SKILL_MAP` and `SHARED_SKILLS`. Or extend `core/skill_registry.py` if a natural home exists.

### B.2 Prepare template at engineer profile creation time

Find where engineer profiles get created. Candidates:
- `scripts/install.sh` bootstrap phase (creates `~/.agents/engineers/<seat>/engineer.toml`)
- `core/scripts/agent_admin_profile.py` (if there's a `profile create` subcommand)
- Some helper during `install.sh` Step 6-ish

At that creation point, for each seat:
1. Look up `SEAT_SKILL_MAP[<seat>]` + `SHARED_SKILLS`
2. For each resolved skill name, `cp -r /Users/ywf/ClawSeat/core/skills/<skill_name>/` → `~/.agents/engineers/<seat>/.claude-template/skills/<skill_name>/`
3. Render `~/.agents/engineers/<seat>/.claude-template/settings.json`:
   - **Memory seat**: includes Stop-hook pointing to `install_memory_hook.py` output (reuse existing logic, just target the template path instead of user's HOME)
   - **All other seats**: minimal config, no user-level hooks. Example:
     ```json
     {
       "hooks": {},
       "permissions": {}
     }
     ```
4. Template is now a self-contained per-seat kit, ready for launcher consumption.

### B.3 Launcher copies from per-seat template (not user-level symlink)

In `core/launchers/agent-launcher.sh`, find where Claude runtime prepares the sandbox HOME. Look for functions/sections that:
- Symlink `$HOME/.claude/settings.json` → `$SANDBOX_HOME/.claude/settings.json`
- Symlink `$HOME/.claude/skills` → `$SANDBOX_HOME/.claude/skills`

Replace that logic with:
1. `mkdir -p $SANDBOX_HOME/.claude/skills`
2. `cp -r ~/.agents/engineers/<seat>/.claude-template/skills/* $SANDBOX_HOME/.claude/skills/`
3. `cp ~/.agents/engineers/<seat>/.claude-template/settings.json $SANDBOX_HOME/.claude/settings.json`
4. Ensure both are **real files**, not symlinks (verify with `test -L` negation in tests).

The engineer seat name can be derived from the launcher's `--dir` or the identity session name — however, a cleaner approach is to pass `--seat <name>` or `CLAWSEAT_SEAT` env from start-engineer into the launcher so the launcher knows which `.claude-template` dir to source from.

### B.4 Make `install_memory_hook.py` work with new template location

Since memory seat's `settings.json` is now prepared at template time (under `~/.agents/engineers/memory/.claude-template/settings.json`) and then copied into sandbox HOME by the launcher, `install_memory_hook.py` should:
- Either render the template's `settings.json` at profile creation time (preferred — one-shot)
- Or post-launch, be aware that the sandbox HOME `.claude/settings.json` is now a real file and writeable

Preferred: render at profile creation. Document clearly in commit message.

### B.5 Backward compatibility

- User's own Claude Code (not seats) must continue working — user still has their 60+ skills at `~/.claude/skills` and their `~/.claude/settings.json`. The fix only changes **seat sandbox** behavior, not user-level.
- Ancestor seat: ancestor is a Claude Code driven by the operator in an iTerm pane — should it get the template too, or does ancestor keep user-level? **Recommendation**: ancestor gets `clawseat-ancestor` + shared skills in its sandbox (same as other seats). Operator's normal Claude Code sessions outside ClawSeat still see user-level.

---

## Tests

1. `test_seat_template_populated_after_profile_create.py` — after profile creation, verify `~/.agents/engineers/<seat>/.claude-template/skills/` contains only the mapped skills (role + shared), verify `.claude-template/settings.json` exists and is valid JSON
2. `test_sandbox_claude_skills_are_real_dirs_not_symlinks.py` — after seat launch, verify `$SANDBOX_HOME/.claude/skills` and `$SANDBOX_HOME/.claude/settings.json` are NOT symlinks
3. `test_sandbox_has_only_role_plus_shared_skills.py` — verify sandbox has exactly the mapped skills, not user's 60+
4. `test_memory_seat_has_stop_hook_in_sandbox.py` — verify memory seat's sandbox `.claude/settings.json` contains the Stop-hook
5. `test_non_memory_seats_lack_stop_hook_in_sandbox.py` — verify other seats' sandbox `.claude/settings.json` has no Stop-hook
6. `test_planner_seat_has_planner_skill.py` — verify planner seat's sandbox contains `planner` skill dir
7. `test_agent_admin_start_engineer_codex_mapping.py` (Part A test)

All 65+ previously-passing round-2 tests must still pass.

---

## Deliverable

1. Patches + tests (all on experimental branch)
2. `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND3B-TEMPLATE-COPY-AND-START-ENGINEER.md` summarizing what changed, test results, and any open questions
3. Send brief summary via `send-and-verify.sh` to codex-xcode session `codex-xcode-api-clawseat-20260423-204444` for cross-review
4. When fully complete, echo `ROUND3B_DONE`

---

## Constraints

- Experimental branch at `/Users/ywf/ClawSeat`
- Don't end-to-end rerun `install.sh` (live install state in Phase-A)
- Don't touch currently-running seat tmux sessions (memory, planner, etc.); just the code paths
- Don't touch `wait-for-seat.sh` or launcher `--auth xcode` config.toml rendering — those are codex-xcode's round-3a task
- Keep backward compatibility: user's own Claude Code (not seats) still uses user-level skills
- Don't create role-specific skills for builder/reviewer/qa/designer in this round — use `clawseat` as placeholder (planner handles dedicated skills in round-4)

---

## Context on why we pivoted

The previous symlink-based approach tried to be clever by reading profile metadata and symlinking select skills. Operator's architectural call: **copy templates at workspace creation** is simpler, cleaner, and doesn't depend on metadata that isn't being populated correctly yet. We trade a bit of disk space (each seat gets its own copy of a few small skill dirs) for immutability and predictability.

If you disagree with the approach or find a blocker, WRITE IT IN THE DELIVERY FILE rather than improvising.
