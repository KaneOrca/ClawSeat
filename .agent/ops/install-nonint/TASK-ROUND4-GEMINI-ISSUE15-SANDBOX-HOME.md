# TASK: Round-4 (parallel) — Investigate #15 nested sandbox HOME leak

**Assigned to**: gemini (read-only investigation, its strength per round-3c success)
**Repo**: `/Users/ywf/ClawSeat` experimental branch
**Type**: read-only audit, no code changes

## Background

Observed during install test: ancestor-spawned seats end up with nested sandbox HOME like:
`.../custom-install-ancestor/home/.agent-runtime/identities/codex/...`

Meaning: scripts called from inside ancestor's sandbox HOME use `Path.home()` or `os.path.expanduser("~")`, which returns the sandbox HOME (not operator's real HOME). When that script then constructs paths for a DIFFERENT seat's identity dir, it builds `<ancestor_sandbox>/.agent-runtime/...` instead of `<real_user_home>/.agent-runtime/...`.

Canonical helper already exists: `core/lib/real_home.py` exports `real_user_home()`, and `gstack-harness/scripts/_common.py` has `_resolve_effective_home()` with documented priority:
1. `CLAWSEAT_REAL_HOME` env override
2. `AGENT_HOME` env (injected by start_seat.py)
3. `pwd.getpwuid(os.getuid()).pw_dir`
4. `Path.home()` (last-resort)

Memory note: "始祖 feishu auth 诊断盲区" documents this class of bug — `real_user_home()` must be used, not `Path.home()`.

## Task — READ-ONLY audit

1. `grep -rn "Path.home()" /Users/ywf/ClawSeat --include="*.py"` — list every call site
2. `grep -rn 'expanduser.*~' /Users/ywf/ClawSeat --include="*.py"` — same for `os.path.expanduser`
3. `grep -rn 'os.environ.get.*HOME\|os.environ\["HOME"\]' /Users/ywf/ClawSeat --include="*.py"` — raw HOME env reads
4. `grep -rn 'os.environ.get.*HOME\|os.environ\["HOME"\]\|\$HOME' /Users/ywf/ClawSeat --include="*.sh"` — shell scripts too
5. For each call site, classify:
   - **KEEP `Path.home()`** — script is ONLY called from user-level (not inside a seat sandbox) — e.g., install.sh preflight before any seat exists
   - **MUST switch to `real_user_home()`** — script is called from inside a seat sandbox AND needs to reach user's real HOME (to find `~/.agents/`, `~/.openclaw/`, `~/.lark-cli/`, etc.)
   - **OK as-is** — script genuinely wants the sandbox HOME (e.g., writing seat-local artifacts)
   - **AMBIGUOUS** — flag for planner review
6. Special attention: any script that constructs paths under `~/.agents/` or `~/.agent-runtime/` from within a seat context

## Deliverable

Write `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DIAGNOSIS-15-SANDBOX-HOME-LEAK.md`:

```markdown
# Sandbox HOME leak audit (#15)

Scanner: gemini session, 2026-04-24
Scope: /Users/ywf/ClawSeat (experimental)

## Call site inventory

| file:line | expr | seat context? | classification | recommendation |
|-----------|------|---------------|----------------|----------------|
| ... | Path.home() | yes/no/?? | KEEP / SWITCH / OK / AMBIGUOUS | ... |

## Summary counts

- Total `Path.home()` / `expanduser` / `$HOME` sites: N
- KEEP (user-level only): K
- SWITCH to real_user_home(): S  ← these are the leaks
- OK as-is (sandbox-intended): O
- AMBIGUOUS (needs planner review): A

## High-risk call sites (top 5-10)

For each, one paragraph explaining:
- where it's invoked from
- what path it constructs
- what happens when called from a seat sandbox vs operator
- the likely symptom (which bug it would produce)

## Recommendation

1. Replace all SWITCH sites with `real_user_home()` (from `core/lib/real_home.py`)
2. Add a pytest guard: `tests/test_no_bare_path_home_in_sandbox_paths.py` (optional, scan-time)
3. Shell scripts: document guidance in `core/skills/gstack-harness/references/sandbox-home.md` or equivalent
```

When done: `echo DIAG_15_DONE`

## Constraints

- READ-ONLY. No code changes, no commits, no file writes except the DIAGNOSIS report
- Don't run install.sh / clean-slate / touch seat state
- Don't spawn sub-agents for patching — this is pure investigation; but DO use sub-agents to fan-out the grep/classification lanes (4 grep types × sections of the codebase) if your agent supports it
- Can run in parallel with codex-chatgpt's round-3b and codex-xcode's round-4 — file sets don't overlap
