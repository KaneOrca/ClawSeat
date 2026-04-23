# Context Snapshot — ClawSeat v0.7 Full-Chain Install Test (for post-compression continuation)

**Timestamp**: 2026-04-24 ~03:10 AM
**Session**: planner Claude Code running in worktree `/Users/ywf/coding/.claude/worktrees/busy-antonelli`
**Mission**: Run full-chain ClawSeat install, catalog issues, dispatch fixes via TUI/seat workers, verify.

## Repo layout

- `~/clawseat` = git worktree of `/Users/ywf/coding/ClawSeat`, branch `experimental` — **THIS is where code fixes land**
- `/Users/ywf/coding/ClawSeat` = main checkout shared via `.git/worktrees/ClawSeat`. Also on `experimental` (same branch, same worktree gitdir)
- `/Users/ywf/.agents/*` = live install state (Phase-A in progress)
- `/Users/ywf/.agent-runtime/identities/...` = per-seat sandbox HOMEs

**IMPORTANT path quirk**: macOS APFS case-insensitive + Node.js `process.cwd()` returns case-preserved form. `/Users/ywf/clawseat` ≡ `/Users/ywf/ClawSeat` on disk but Node/claude displays uppercase "ClawSeat".

## What we did

1. **Clean-slate**: `bash scripts/clean-slate.sh --yes` + extra symlink cleanup (removed 5 cross-checkout symlinks including `~/.clawseat`). Preserved `~/.lark-cli`, `~/.agent-runtime/secrets`, `~/.openclaw/{agents,openclaw.json}`, `~/.gstack`.
2. **Full-chain install**: `bash scripts/install.sh --provider minimax` (exit 0 with 1 WARN).
3. **Manual kickoff fix**: install.sh's `auto_send_phase_a_kickoff` silently failed (3x, 0 matches in pane history). Planner manually sent via `send-and-verify.sh` — immediately worked.
4. **Phase-A B0→B5.5 driven by user in iTerm ancestor pane** — uncovered many issues.

## The 17 cataloged issues

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | install.sh `auto_send_phase_a_kickoff` silent failure (verification fails on banner repaint) | HIGH | ✅ round 2 (codex-xcode: expanded spinner detection ✶/✻/✢/✳/✽/⏺ + "Read N files") |
| 2 | Claude Code status bar "Not logged in · Run /login" for `ANTHROPIC_AUTH_TOKEN` users | LOW | ✅ gemini diag: upstream Claude Code v2.1.117 UI limitation, `accept_as_is` |
| 3 | `~/Library/LaunchAgents/com.clawseat.*.plist` never installed | HIGH | ✅ round 2 (codex-chatgpt: install.sh Step 6 `install_ancestor_patrol_plist` + tests) |
| 4 | cwd case mismatch `/ClawSeat` vs `/clawseat` | LOW | ✅ gemini diag: macOS+Node.js standard behavior, `cosmetic_accept_as_is` |
| 5 | Step 5.5 "api secrets not provisioned" timing warning | LOW | ⏸ queued |
| 6 | `project-install-monitor` tmux session never launched (semantic unclear) | LOW | ⏸ investigation queued |
| 7 | planner ARCH_VIOLATION on `install-builder-claude → install-builder-codex` rename (false positive) | MEDIUM | ⏸ round 4 |
| 8 | `agent_admin` CLI arg inconsistency | LOW | ⏸ debt |
| 9 | lark-cli user token cleared on re-login (sandbox HOME issue?) | MEDIUM | ⏸ queued |
| 10 | `send_delegation_report.py` uses `lark-cli auth status --as X` but 1.0.18 dropped `--as` on `auth status` subcommand (message-send `--as` still works) | HIGH | ⏸ round 4 |
| 11 | bot `cli_a96abcca2e78dbc2` gets "invalid param" on group API (not in group or no permission) | MEDIUM | ⏸ OpenClaw config |
| 12 | `send_delegation_report.py` requires all 4 args (--task-id --decision-hint --user-gate --next-action), no defaults | LOW | ⏸ |
| 13 | `decision-hint: wait` invalid (valid: hold/proceed/ask_user/retry/escalate/close) | LOW | ⏸ docs |
| 14 | **All Claude seats' sandbox HOME `.claude/{settings.json,skills}` are symlinks → user-level** (memory has no Stop-hook, qa/designer/planner have no role skills — just user's 60+ general skills) | CRITICAL | 🟡 **round 3b codex-chatgpt** |
| 15 | Nested sandbox HOME path for ancestor-spawned seats: `.../custom-install-ancestor/home/.agent-runtime/identities/codex/...` (used ancestor's sandbox HOME not real user HOME) | HIGH | ⏸ round 4 (`Path.home()` / `expanduser` should be `real_user_home()`) |
| 16 | `agent_admin session start-engineer reviewer` for `codex+api+xcode-best` silently fails (launcher rejects `--auth api for codex`; start-engineer swallows error; prints session name but tmux never comes up) | HIGH | 🟡 **round 3b codex-chatgpt** |
| 17 | launcher `--auth xcode` branch doesn't render `config.toml` with `[model_providers.xcodeapi]` + `model_provider=xcodeapi` — codex CLI defaults to `api.openai.com` → 401 | HIGH | 🟡 **round 3a codex-xcode** |

## Dispatch history

| Round | To | Task | Status | DELIVERY file |
|---|---|---|---|---|
| 1 | gemini | UX diag (#2, #4) | ✅ done | `DIAGNOSIS-UX-ISSUES.md` |
| 1 | codex-xcode | (self-initiated) auto-kickoff + wait-for-seat + spinner + docs | ✅ done → review by codex-chatgpt found 2 regressions | — |
| 1 review | codex-chatgpt | review codex-xcode round 1 | ✅ done, flagged HIGH alias ambiguity + MEDIUM fallback removed | — |
| 1 | codex-chatgpt | plist install (#3) | ✅ done | `DELIVERY-CODEX-CHATGPT-PLIST.md` |
| 2 | codex-xcode | round 1 regressions (alias + fallback) | ✅ done (too aggressive: removed fallback entirely) | `DELIVERY-CODEX-XCODE-REGRESSIONS.md` |
| 2 review | codex-chatgpt | review round 2 | ✅ done, flagged MEDIUM wait-for-seat fallback still missing | — |
| 2 | codex-xcode | fallback restore (3 护栏) + Codex YOLO parity | ✅ done | `DELIVERY-ROUND2-FALLBACK-AND-YOLO.md` |
| 2 review | codex-chatgpt | review round 2 v2 | ✅ done, flagged 1 open Q: retire 1-arg wait-for-seat? 3 tests failing | — |
| **3a** | **codex-xcode** | retire 1-arg wait-for-seat + #17 launcher xcode config.toml | 🟡 Working ~1.5m | pending `DELIVERY-ROUND3-XCODE-CONFIG-AND-1ARG-RETIRE.md` |
| **3b** | **codex-chatgpt** | #16 start-engineer silent fail + #14 seat .claude isolation | 🟡 Working ~1.5m | pending `DELIVERY-ROUND3-START-ENGINEER-AND-SEAT-ISOLATION.md` |
| **3c** | **gemini** | SUPPORTED_RUNTIME_MATRIX audit (read-only) | 🟡 Thinking ~1.5m | pending `DIAGNOSIS-MATRIX-AUDIT.md` |

## Live workers (tmux sessions)

**External TUIs**:
- `codex-xcode-api-clawseat-20260423-204444` — Codex gpt-5.4 medium, cwd `/Users/ywf/coding/ClawSeat`, assigned Round-3a
- `agent-launcher-codex-chatgpt-20260423-230652` — Codex gpt-5.4 xhigh, cwd `~/.local/share/.../codex`, assigned Round-3b
- `agent-launcher-gemini-google-oauth-20260424-010752` — Gemini 3 oauth, cwd `~/.local/share/.../gemini`, assigned Round-3c

**ClawSeat seats** (all UP):
- `install-ancestor` (claude api minimax, PID from 01:36 launch) — Phase-A driver, user interacts in iTerm. Paused at B5.5 blocker.
- `install-planner-claude` (claude oauth anthropic, 02:07) — planner, not yet dispatched anything
- `install-builder-codex` (codex oauth openai, 02:18) — WORKS but started BEFORE round 2 YOLO fix. Has default approval mode. Avoid using for heavy edits.
- `install-reviewer-codex` (codex api xcode-best, 03:04) — ✅ WORKS (just verified with smoke "reply OK one word" → "OK"). gpt-5.4 xhigh via xcode.best. **Reserved for reviewing round 3 deliverables.**
- `install-qa-claude` (claude api minimax, 02:25) — WORKS but no qa role skills loaded (#14)
- `install-designer-gemini` (gemini oauth google, 02:25) — WORKS but no designer role skills loaded (#14)
- `machine-memory-claude` (claude api minimax, 01:36) — WORKS but no memory-oracle skill loaded (#14 acute form)

## Critical token update done manually

User provided new xcode-best GPT-capable token: `sk-RUIb1wqja7AzGB2nrcxmpdsONSE8Uq8tRZZUGuBPavfqSQeF` (replaces Claude-only `sk-8aI4w1...`). Written to:
- `/Users/ywf/.agents/secrets/codex/xcode-best/reviewer.env` — engineer profile path
- (Already symlinked from `/Users/ywf/.agent-runtime/secrets/codex/xcode.env` → reviewer.env at ~Apr 23 20:33)

Test: `curl -H "Authorization: Bearer $TOKEN" https://api.xcode.best/v1/chat/completions -d '{"model":"gpt-5.4",...}'` returns 200 with gpt-5.4 response. ✓

## Round 3 poll cadence

Each TUI reports "Working Xm Ys". When they echo `ROUND3A_DONE` / `ROUND3B_DONE` / `MATRIX_AUDIT_DONE` in pane tail, delivery files should be in `/Users/ywf/ClawSeat/.agent/ops/install-nonint/DELIVERY-ROUND3*.md` or `DIAGNOSIS-MATRIX-AUDIT.md`.

Next actions upon deliveries:
1. Read each DELIVERY for substance
2. Dispatch `install-reviewer-codex` (via send-and-verify.sh) to independently review each: confirm patch quality, catch regressions
3. After all 3 + reviewer verdict → compile final full-chain install test report

## Files to re-read after compression

1. This file: `/Users/ywf/ClawSeat/.agent/ops/install-nonint/CONTEXT-COMPRESSION-SNAPSHOT.md`
2. Previous TASK dispatches (for task definitions):
   - `TASK-ROUND3A-CODEX-XCODE.md`
   - `TASK-ROUND3B-CODEX-CHATGPT.md`
   - `TASK-ROUND3C-GEMINI.md`
3. Previous DELIVERY files (for already-landed fixes):
   - `DELIVERY-ROUND2-FALLBACK-AND-YOLO.md`
   - `DELIVERY-CODEX-XCODE-REGRESSIONS.md`
   - `DELIVERY-CODEX-CHATGPT-PLIST.md`
   - `DIAGNOSIS-UX-ISSUES.md`

## User state in Phase-A (pending interaction)

Ancestor in `install-ancestor` tmux pane is waiting at B5.5 blocker summary. User needs to tell ancestor either:
- `skip B5 Feishu, continue CLI-only. 进 B6 / B7 收尾 Phase-A。`
- OR choose a koder overlay tenant from: cartooner / cartooner-web / cc / claude / codex / donk / gemini / koder / legal / mor / scout / warden / yu

ancestor-bootstrap brief is at: `/Users/ywf/.agents/tasks/install/patrol/handoffs/ancestor-bootstrap.md`
STATUS.md (not yet written) would land at: `/Users/ywf/.agents/tasks/install/STATUS.md`

## Pending design decisions surfaced

1. `wait-for-seat.sh` 1-arg form retirement (round 3a is doing this — final decision approved by planner)
2. SUPPORTED_RUNTIME_MATRIX cleanup (round 3c will recommend)
3. Whether `claude-code` / `openai-codex` are valid aliases for `anthropic` / `openai` providers (rejected during B0 — naming convention question)

## Key architectural reminders

- ClawSeat v0.7 is CLI-first, Feishu write-only optional
- L1 entry: `scripts/install.sh`. L2 ops: `agent_admin session/project`. L3: `agent-launcher.sh` (INTERNAL)
- 6-pane iTerm native grid (not nested tmux). `wait-for-seat.sh <project> <seat>` (2-arg, canonical)
- Canonical transport: `send-and-verify.sh --project X <seat> "<msg>"` for ad-hoc, `dispatch_task.py` for structured handoff
- `real_user_home()` helper must be used (not `Path.home()`) when computing user-level paths from inside sandbox HOMEs
