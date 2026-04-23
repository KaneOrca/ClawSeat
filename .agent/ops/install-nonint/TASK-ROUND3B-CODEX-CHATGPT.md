# TASK: Round-3 — fix start-engineer silent failure + seat .claude sandbox isolation

**Assigned to**: codex-chatgpt
**Repo**: `/Users/ywf/ClawSeat` experimental branch

## Part A — Fix #16: `agent_admin session start-engineer` silent failure for codex+api+xcode-best

**Observed**: Planner ran `agent_admin session start-engineer reviewer --project install`. Engineer profile has `tool=codex, auth_mode=api, provider=xcode-best`. start-engineer exited with 0 and printed "install-reviewer-codex" as the session name, but tmux session never appeared.

Direct launcher invocation reveals the bug:
```bash
$ bash agent-launcher.sh --headless --tool codex --auth api --dir ... --session ...
error: unsupported auth 'api' for tool 'codex'
```

Launcher only supports `codex + oauth|xcode|custom|chatgpt`, NOT `codex + api`.

start-engineer's mapping from engineer profile (`auth_mode=api, provider=xcode-best`) to launcher args (`--auth <something>`) is either:
- Not happening at all (passes `--auth api` literally → launcher rejects)
- Happening wrong (maps to unsupported combo)
- Happening correctly but launcher returns non-zero and start-engineer swallows it

Root cause investigation:
1. Read `core/scripts/agent_admin_session.py` (seat start-engineer code path)
2. Find where engineer profile's `auth_mode + provider` → launcher `--auth` mapping happens
3. For `codex+api+xcode-best`, the correct launcher arg is `--auth xcode` (empirically verified — planner ran `--auth xcode` and it launched, just with broken config.toml which is codex-xcode's round-3a task)
4. The mapping likely needs: `(codex, api, xcode-best) → (launcher --auth xcode, env CLAWSEAT_PROVIDER=xcode-best)`
5. ALSO: launcher exit code should propagate through start-engineer so silent failures don't happen

Required:
1. Fix the mapping for `codex + api + xcode-best` → `--auth xcode` (and any similar combos)
2. Make start-engineer print the launcher command it's running (stderr/debug mode) so operator can see what went wrong
3. Make start-engineer return non-zero if launcher returns non-zero
4. New test `tests/test_agent_admin_start_engineer_codex_mapping.py` covering the codex+api+xcode-best mapping

## Part B — Fix #14: seat sandbox `.claude/` isolation broken

**Observed**: memory seat (and all other Claude seats) have sandbox HOME `.claude/` symlinked back to user-level:
```
$SANDBOX_HOME/.claude/settings.json -> /Users/ywf/.claude/settings.json
$SANDBOX_HOME/.claude/skills       -> /Users/ywf/.claude/skills
```

Consequence:
- `install_memory_hook.py --workspace $MEMORY_WORKSPACE` writes to `$MEMORY_WORKSPACE/.claude/settings.json` (a REAL file), but claude-code at runtime reads `$SANDBOX_HOME/.claude/settings.json` (symlink → user's real settings.json which has NO memory hook).
- Seats see user's 60+ daily skills (gstack, qa, cso, agent-reach, ...) instead of their seat-specific role skill.
- qa/designer/reviewer don't know their roles because role skills aren't loaded.

Root cause: launcher's `prepare_claude_home` (or equivalent helper) symlinks `.claude/settings.json` and `.claude/skills` from user home into sandbox home unconditionally. Find this in `core/launchers/agent-launcher.sh` (related function around `prepare_codex_home` line 459 — there's probably similar for claude).

Required:
1. For Claude seats in sandboxed mode: **do NOT symlink `.claude/settings.json` and `.claude/skills` to user-level**. Instead:
   - `.claude/settings.json` — render per-seat with proper hooks (memory seat gets Stop-hook; others get a minimal empty hooks config)
   - `.claude/skills/` — only symlink the role's specific skill (memory seat gets `memory-oracle` only; qa gets `qa`-related skills; designer gets `design-*` skills; etc.) — NOT the user's full 60+ skill collection
2. Make `install_memory_hook.py` target the sandbox HOME path (or teach it to follow symlinks correctly), not the workspace path
3. For the specific seat→skill mapping, read each engineer profile's `skills = [...]` array (already stored in `~/.agents/engineers/<seat>/engineer.toml`) and only link/resolve those
4. Keep backward compatibility: existing user-level skills still work for user's own Claude Code (not seats)

Tests:
1. `test_seat_sandbox_claude_isolation.py` — verify sandbox `.claude/settings.json` is NOT a symlink to user's, verify seat has ONLY its role skills
2. `test_install_memory_hook_lands_in_runtime_home.py` — verify memory Stop-hook ends up at the path claude-code actually reads at runtime

## Deliverable

1. Patches + tests
2. `DELIVERY-ROUND3-START-ENGINEER-AND-SEAT-ISOLATION.md`
3. Send summary to codex-xcode (204444) for review
4. echo `ROUND3B_DONE`

## Constraints
- Experimental branch at `/Users/ywf/ClawSeat`
- Don't end-to-end rerun install.sh (live install in Phase-A)
- Don't touch `wait-for-seat.sh` or launcher `--auth xcode` config.toml logic (those are codex-xcode's round-3a task)
- Don't touch currently-running seat state (memory, planner etc.); just the code paths
